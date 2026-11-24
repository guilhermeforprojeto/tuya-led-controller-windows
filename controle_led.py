"""Controle pessoal de fita Tuya RGB+CCT para Windows."""
import colorsys
import hashlib
import hmac
import json
import os
import sys
import queue
import threading
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

ENDPOINT = 'https://openapi.tuyaus.com'
DEVICE = ''


def colour_value(hex_colour, brightness):
    rgb = tuple(int(hex_colour[i:i+2], 16) / 255 for i in (1, 3, 5))
    h, s, _ = colorsys.rgb_to_hsv(*rgb)
    return json.dumps({'h': round(h*360), 's': round(s*1000),
                       'v': max(10, min(1000, round(brightness*10)))}, separators=(',', ':'))


def make_headers(client, secret, method, path, body, token='', timestamp=None):
    t = str(timestamp if timestamp is not None else int(time.time()*1000))
    to_sign = method + '\n' + hashlib.sha256(body).hexdigest() + '\n\n' + path
    signature = hmac.new(secret.encode(), (client+token+t+to_sign).encode(), hashlib.sha256).hexdigest().upper()
    headers = {'client_id': client, 't': t, 'sign': signature,
               'sign_method': 'HMAC-SHA256', 'Content-Type': 'application/json'}
    if token:
        headers['access_token'] = token
    return headers


class Tuya:
    def __init__(self, config):
        self.config = dict(config)
        self.token = ''
        self.expires = 0
        self.timeout = 15

    def raw(self, method, path, payload=None, token=''):
        body = b'' if payload is None else json.dumps(payload, separators=(',', ':')).encode()
        headers = make_headers(self.config['client_id'], self.config['secret'], method, path, body, token)
        req = urllib.request.Request(ENDPOINT+path, data=body if payload is not None else None,
                                     headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'Erro HTTP {exc.code}. Confira a conexão e as permissões da Tuya.') from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError('Não foi possível acessar a Tuya. Confira sua internet.') from None
        if not data.get('success'):
            code = str(data.get('code', '?'))
            hints = {'1004': 'Confira Access ID e Secret do projeto atual.',
                     '1010': 'Token inválido. Tente novamente.',
                     '1106': 'Confira região, APIs autorizadas e permissão de controle.',
                     '28841002': 'Confira a validade do serviço IoT Core na Tuya.'}
            raise RuntimeError(f"Tuya {code}: {data.get('msg', 'Falha na API')}. {hints.get(code, '')}")
        return data.get('result')

    def request(self, method, suffix, payload=None):
        if time.time() >= self.expires:
            auth = self.raw('GET', '/v1.0/token?grant_type=1')
            self.token = auth['access_token']
            self.expires = time.time() + max(0, int(auth.get('expire_time', 7200))-60)
        device = urllib.parse.quote(self.config['device_id'], safe='')
        try:
            return self.raw(method, f'/v1.0/iot-03/devices/{device}/{suffix}', payload, self.token)
        except RuntimeError as exc:
            if 'Tuya 1010:' in str(exc):
                self.expires = 0
            raise

    def send(self, commands):
        result = self.request('POST', 'commands', {'commands': commands})
        if result is False:
            raise RuntimeError('A Tuya não aceitou o comando.')
        return result


def command(code, value):
    return {'code': code, 'value': value}


def main():
    import tkinter as tk
    from tkinter import ttk, colorchooser, messagebox
    import pystray
    from windows_integration import SessionListener, startup_enabled, set_startup
    from pc_rgb import PcLighting, find_openrgb, launch_openrgb
    startup_launch = '--startup' in sys.argv
    mutex = None
    if os.name == 'nt':
        import win32api, win32event, winerror
        mutex = win32event.CreateMutex(None, False, r'Local\ControleLED-Pessoal')
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            messagebox.showinfo('Controle LED', 'O aplicativo já está aberto. Procure o ícone perto do relógio.')
            return
    from PIL import ImageTk
    from icon_art import draw_icon, icon_for
    from conflicts import (find_conflicts, stop_now, remove_programs, open_apps_settings,
                           alerts as conflict_alerts)
    from dialogs import ConflictsWindow, AutomationWindow
    from flyout import TrayFlyout, tray_icon_class
    from dialogs import StickOrderWindow
    from fx import is_animated, led_hex, rgb_to_hex, single as fx_single
    from pc_rgb import stick_colours
    from colour_picker import ColourPicker
    from palettes import remember as remember_colour
    from automation import due_routines, pick_profile, ProfileSwitcher
    from winproc import process_names, foreground_process, windowed_apps
    from datetime import datetime

    folder = Path(os.environ.get('APPDATA', str(Path.home()))) / 'ControleLED'
    folder.mkdir(parents=True, exist_ok=True)
    config_path = folder / 'config.json'
    config = {'client_id': '', 'secret': '', 'device_id': DEVICE, 'led_on_start': False,
              'led_off_shutdown': False, 'pc_sync': False, 'last': {}}
    try:
        config.update(json.loads(config_path.read_text(encoding='utf-8')))
    except (OSError, ValueError):
        pass

    def tuya_ready():
        return all(config.get(k) for k in ('client_id', 'secret', 'device_id'))

    def save_config(data):
        temp = config_path.with_suffix('.tmp')
        temp.write_text(json.dumps(data, indent=2), encoding='utf-8')
        temp.replace(config_path)

    def log(message):
        try:
            with (folder / 'eventos.log').open('a', encoding='utf-8') as f:
                f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + message + '\n')
        except OSError:
            pass

    def shutdown_off():
        if config.get('pc_sync'):
            try:
                state['pc'].off((0, 1))  # local e rápido: vem antes da nuvem
                log('Desligamento: LEDs do PC apagados.')
            except Exception as exc:
                log('Desligamento: falha no OpenRGB: ' + str(exc))
        if not tuya_ready():
            return
        try:
            api = Tuya(config)
            api.timeout = 1
            # Reutiliza o token já obtido para reduzir o tempo no encerramento.
            current = state['api']
            api.token, api.expires = current.token, current.expires
            api.send([command('switch_led', False)])
            log('Desligamento: comando aceito pela Tuya.')
        except Exception as exc:
            log('Desligamento: falha ao enviar comando: ' + str(exc))

    listener = SessionListener(lambda: config.get('led_off_shutdown', False), shutdown_off, log)
    root = tk.Tk()
    root.title('Controle LED · PC')
    from interface import setup_theme, build_panel, build_menu
    setup_theme(root)
    frame = ttk.Frame(root, padding=18)
    frame.pack(fill='both', expand=True)
    tasks, results = queue.Queue(), queue.Queue()
    def openrgb_launcher():
        exe = find_openrgb(config.get('openrgb_path'))
        if not exe:
            raise OSError('OpenRGB.exe não encontrado')
        log('Abrindo OpenRGB: ' + exe)
        launch_openrgb(exe)

    from types import SimpleNamespace
    from effects import EFFECTS, SPEEDS, tuya_scene

    # Seleção salva por aba: cor, branco ou efeito, com brilho e velocidade.
    last = config.get('last') or {}
    default = {'mode': last.get('mode', 'colour'), 'colour': last.get('colour', '#a020f0'),
               'brightness': last.get('brightness', 50), 'temperature': last.get('temperature', 500),
               'effect': 'breathing', 'speed': 'medium', 'white': 0}
    selections = {key: dict(default, **(config.get('selections') or {}).get(key, {}))
                  for key in ('all', 'strip', 'board', 'ram')}
    state = {'api': Tuya(config), 'pc': PcLighting(launcher=openrgb_launcher), 'busy': False,
             'loading': False}
    # Memórias: ordem dos pentes e o estado de cada um (cor/efeito ou desligado).
    state['pc'].ram.order = list(config.get('ram_order') or [])
    ready = tuya_ready() or config.get('pc_sync')
    v = SimpleNamespace(
        target=tk.StringVar(value='all'),
        mode=tk.StringVar(), colour=tk.StringVar(), brightness=tk.IntVar(),
        temperature=tk.IntVar(), effect=tk.StringVar(), speed=tk.StringVar(), white=tk.IntVar(),
        pc_sync=tk.BooleanVar(value=config.get('pc_sync', False)),
        power=tk.StringVar(value='Fita: estado não consultado'),
        warning_short=tk.StringVar(value=''),
        sticks=tk.StringVar(value=config.get('ram_selected') or '1234'),
        stick_count=tk.IntVar(value=int(config.get('ram_count') or 4)),
        stick_on=tk.StringVar(value='1111'),
        status=tk.StringVar(value='Escolha a aba, a cor ou o efeito e clique em Aplicar.' if ready
                            else 'Configure as credenciais para começar.'))
    status, power = v.status, v.power
    SEL_KEYS = ('mode', 'colour', 'brightness', 'temperature', 'effect', 'speed', 'white')

    def load_selection(*_):
        state['loading'] = True
        sel = selections[v.target.get()]
        for key in SEL_KEYS:  # seleções antigas (rotinas, perfis) podem não ter 'white'
            getattr(v, key).set(sel.get(key, default[key]))
        state['loading'] = False

    def store_selection(*_):
        if not state['loading']:
            selections[v.target.get()] = {key: getattr(v, key).get() for key in SEL_KEYS}

    load_selection()
    v.target.trace_add('write', load_selection)
    for key in SEL_KEYS:
        getattr(v, key).trace_add('write', store_selection)

    def worker():
        while True:
            item = tasks.get()
            if item is None:
                return
            func, callback = item
            try:
                results.put((callback, func(), None))
            except Exception as exc:
                results.put((callback, None, str(exc)))

    threading.Thread(target=worker, daemon=True).start()

    def submit(func, callback=None, needs_tuya=False):
        if state['busy']:
            return
        if not tuya_ready() and (needs_tuya or not config.get('pc_sync')):
            settings()
            return
        state['busy'] = True
        status.set('Enviando comando…')
        tasks.put((func, callback))

    PARTS = {'all': ('strip', 'board', 'ram'), 'strip': ('strip',),
             'board': ('board',), 'ram': ('ram',)}
    PC_TYPES = {'board': 0, 'ram': 1}
    NAMES = {'strip': 'fita', 'board': 'placa-mãe', 'ram': 'memórias'}

    def active_parts(target):
        return [part for part in PARTS[target]
                if (part == 'strip' and tuya_ready()) or (part != 'strip' and config.get('pc_sync'))]

    def tuya_commands(sel):
        mode = sel['mode']
        if mode == 'effect' and sel['effect'] != 'static':
            return [command('switch_led', True), command('work_mode', 'scene'),
                    command('scene_data_v2', tuya_scene(sel['effect'], led_hex(sel),
                                                        sel['brightness'], sel['speed']))]
        if mode == 'white':
            return [command('switch_led', True), command('work_mode', 'white'),
                    command('bright_value_v2', max(10, sel['brightness']*10)),
                    command('temp_value_v2', sel['temperature'])]
        return [command('switch_led', True), command('work_mode', 'colour'),
                command('colour_data_v2', colour_value(led_hex(sel), sel['brightness']))]

    def stick_positions():
        return [int(c) for c in v.sticks.get() if c.isdigit()] or None

    def make_job(parts, sel_for, power_on=None, sticks_only=False):
        """Monta o trabalho do worker. sel_for(part) devolve a seleção da parte.
        Os dados são copiados aqui, na thread da interface."""
        steps = []
        if 'strip' in parts:
            cmds = ([command('switch_led', power_on)] if power_on is not None
                    else tuya_commands(sel_for('strip')))
            steps.append(('fita', lambda c=cmds: state['api'].send(c)))
        if 'board' in parts:
            if power_on is False:
                steps.append((NAMES['board'], lambda: state['pc'].off((0,))))
            else:
                sel = dict(sel_for('board'))
                steps.append((NAMES['board'], lambda s=sel: state['pc'].apply_selection(s, (0,))))
        if 'ram' in parts:
            # Na aba Memórias, só os pentes escolhidos; nas outras, todos.
            positions = stick_positions() if sticks_only else None
            sel = dict(sel_for('ram'))
            if power_on is None:
                steps.append((NAMES['ram'], lambda s=sel, p=positions:
                              state['pc'].apply_selection(s, (1,), p)))
            else:
                steps.append((NAMES['ram'], lambda on=power_on, s=sel, p=positions:
                              state['pc'].ram_power(on, p, fallback=s)))

        def job():
            done, errors = [], []
            for name, step in steps:
                try:
                    step()
                    done.append(name)
                except Exception as exc:
                    errors.append(f'{name}: {exc}')
            if errors and not done:
                raise RuntimeError('\n'.join(errors))
            return done, errors
        return job

    def report(result):
        done, errors = result
        text = 'Aplicado: ' + ', '.join(done) + '.'
        if errors:
            text += ' Aviso: ' + ' '.join(errors)
            log(text)
        status.set(text)
        if 'memórias' in done:
            save_ram_state()
        if any(name != 'fita' for name in done):
            check_conflicts()

    def sync_stick_on():
        states = state['pc'].ram.position_states()
        if states:
            v.stick_on.set(''.join('1' if on else '0' for on in states))

    def stick_power(on_for, label):
        """on_for(posição) → True/False/None (None = não mexe)."""
        count = v.stick_count.get()
        plan = {p: on_for(p) for p in range(1, count + 1)}
        plan = {p: on for p, on in plan.items() if on is not None}
        sel = dict(selections['ram'])

        def job():
            for on in (True, False):
                chosen = [p for p, value in plan.items() if value is on]
                if chosen:
                    state['pc'].ram_power(on, chosen, fallback=sel)
            return [NAMES['ram']], []

        def done(result):
            report(result)
            status.set(label)
        submit(job, done)

    def toggle_stick(position):
        current = v.stick_on.get()[position - 1:position] != '0'
        stick_power(lambda p: (not current) if p == position else None,
                    f"Pente {position} {'desligado' if current else 'ligado'}.")

    def only_selected():
        chosen = set(stick_positions() or [])
        stick_power(lambda p: None if p in chosen else False,
                    'Pentes não marcados apagados.')

    def save_ram_state():
        """Guarda o estado de cada pente para restaurar ao abrir o app."""
        sync_stick_on()
        config['ram_sticks'] = state['pc'].ram.snapshot()
        config['ram_selected'] = v.sticks.get()
        try:
            save_config(config)
        except OSError:
            pass

    def poll():
        try:
            while True:
                cb, value, error = results.get_nowait()
                if cb == 'startup_done':
                    state['busy'] = False
                    if error:
                        status.set('Falha ao ligar na inicialização. Use Ligar para tentar novamente.')
                        log('Inicialização: ' + error)
                    else:
                        report(value)
                    continue
                if cb == 'show':
                    show()
                    continue
                if cb == 'quit':
                    quit_app()
                    return
                if cb == 'power':
                    set_power(value, 'all')
                    continue
                if cb == 'quick':
                    quick_apply(value)
                    continue
                if cb == 'conflicts':
                    show_conflicts(value)
                    continue
                if cb == 'fix':
                    open_conflicts()
                    continue
                if cb == 'auto':
                    open_automation()
                    continue
                if cb == 'flyout':
                    state['flyout'].toggle()
                    continue
                if cb == 'removed':
                    state['fixing'] = False
                    if error:
                        set_conflict_status(error)
                        log('Remover programas: ' + error)
                    elif value:
                        log('Remoção de programas de RGB concluída; verificando de novo.')
                        set_conflict_status('Remoção concluída. Verificando de novo…')
                        reapply_pc()
                        check_conflicts()
                    else:
                        set_conflict_status('Cancelado no pedido de permissão.')
                    continue
                if cb == 'fixed':
                    state['fixing'] = False
                    if error:
                        set_conflict_status(error)
                        log('Parar programas: ' + error)
                    elif value:
                        log('Programas de RGB parados; reaplicando as cores do PC.')
                        set_conflict_status('Programas parados e cores reaplicadas. Para não '
                                            'voltarem ao reiniciar, desinstale-os.')
                        reapply_pc()
                    else:
                        set_conflict_status('Cancelado no pedido de permissão.')
                    check_conflicts()
                    continue
                state['busy'] = False
                if error:
                    status.set(error)
                    messagebox.showerror('Controle LED', error, parent=root)
                else:
                    status.set('Comando aceito.' if cb is None else 'Estado atualizado.')
                    if cb:
                        cb(value)
        except queue.Empty:
            pass
        root.after(100, poll)

    def nothing_to_control():
        status.set('Nada para controlar nesta aba. Configure a Tuya ou ative a placa-mãe e memórias.')

    def set_power(value, target=None):
        target = target or v.target.get()
        parts = active_parts(target)
        if not parts:
            return nothing_to_control()

        def done(result):
            if 'strip' in parts:
                power.set('Fita: ligada' if value else 'Fita: desligada')
            report(result)
        # Ligar no PC restaura a seleção salva de cada parte (e de cada pente).
        submit(make_job(parts, lambda part: selections[part], value, sticks_only=target == 'ram'), done)

    def remember():
        config['selections'] = selections
        try:
            save_config(config)
        except OSError:
            pass

    def apply():
        target = v.target.get()
        parts = active_parts(target)
        if not parts:
            return nothing_to_control()
        sel = dict(selections[target])
        if target == 'all':
            # O Geral vira a seleção de todas as abas.
            for part in ('strip', 'board', 'ram'):
                selections[part] = dict(sel)
            paint_icon(sel)
        remember()

        def done(result):
            if 'strip' in parts:
                power.set('Fita: ligada')
            report(result)
        submit(make_job(parts, lambda part: sel, sticks_only=target == 'ram'), done)

    def quick_apply(changes):
        """Atalho da bandeja: aplica a mudança em tudo (aba Geral)."""
        if state['busy']:
            # Envio em andamento: guarda o último pedido e manda em seguida.
            state['pending'] = lambda c=changes: not state['busy'] and (quick_apply(c) or True)
            return
        parts = active_parts('all')
        if not parts:
            return nothing_to_control()
        sel = dict(selections['all'], **changes)
        for key in ('all', 'strip', 'board', 'ram'):
            selections[key] = dict(sel)
        load_selection()
        remember()
        paint_icon(sel)

        def done(result):
            if 'strip' in parts:
                power.set('Fita: ligada')
            report(result)
        submit(make_job(parts, lambda part: sel), done)

    # Conflitos: outros programas que trocam as cores da placa e das memórias.
    state['conflicts'] = []
    state['alerts'] = []
    state['fixing'] = False

    state['conflict_win'] = None
    state['notified'] = set()

    def check_conflicts():
        if os.name != 'nt':
            return
        if not config.get('pc_sync'):
            # Sem placa/memórias no app, os outros programas não atrapalham.
            show_conflicts([])
            return

        def run():
            try:
                found = find_conflicts()
            except Exception as exc:
                log('Verificação de conflitos falhou: ' + str(exc))
                found = []
            results.put(('conflicts', found, None))
        threading.Thread(target=run, daemon=True).start()

    def notify(title, message):
        try:
            icon.notify(message, title)
        except Exception:
            pass

    def show_conflicts(found):
        # Aviso só para o que muda as cores; restos inativos ficam só na janela.
        serious = conflict_alerts(found)
        new = [f for f in serious if f['key'] not in state['notified']]
        if new:
            log('Interferindo nos LEDs: ' + ', '.join(f['name'] for f in serious))
            notify('Programas interferindo nos LEDs',
                   ', '.join(f['name'] for f in new) + '. Abra o Controle LED e clique em Resolver.')
        if state['alerts'] and not serious:
            log('Nenhum programa interferindo nos LEDs.')
        state['notified'] = {f['key'] for f in serious}
        state['conflicts'] = found
        state['alerts'] = serious
        if len(serious) == 1:
            v.warning_short.set(f"{serious[0]['name']} está mudando as cores dos LEDs.")
        elif serious:
            v.warning_short.set(f'{len(serious)} programas estão mudando as cores dos LEDs.')
        else:
            v.warning_short.set('')
        win = state['conflict_win']
        if win and win.win.winfo_exists():
            win.refresh(found)
        try:
            icon.title = ('⚠ Programas interferindo · ' if serious else '') + 'Controle LED · PC'
            icon.update_menu()
        except Exception:
            pass

    def set_conflict_status(text):
        status.set(text)
        win = state['conflict_win']
        if win:
            win.set_status(text)

    def open_conflicts():
        show()
        win = state['conflict_win']
        if win and win.win.winfo_exists():
            win.win.lift()
        else:
            win = state['conflict_win'] = ConflictsWindow(root, {
                'stop': stop_conflicts, 'remove': remove_selected,
                'settings': open_apps_settings, 'recheck': recheck_conflicts})
        win.refresh(state['conflicts'])
        check_conflicts()

    def stop_conflicts():
        if state['fixing']:
            return
        if not any(f['active'] for f in state['conflicts']):
            return set_conflict_status('Nada rodando para parar: nenhum serviço ou processo de '
                                       'RGB está ativo agora.')
        state['fixing'] = True
        set_conflict_status('Parando os programas… confirme o pedido de permissão do Windows.')
        found = list(state['conflicts'])

        def run():
            try:
                results.put(('fixed', stop_now(found, folder), None))
            except Exception as exc:
                results.put(('fixed', None, str(exc)))
        threading.Thread(target=run, daemon=True).start()

    def remove_selected(commands, found):
        if state['fixing']:
            return set_conflict_status('Aguarde a ação anterior terminar.')
        state['fixing'] = True
        set_conflict_status('Removendo… confirme o pedido de permissão do Windows. '
                            'Pode levar alguns minutos.')

        def run():
            try:
                results.put(('removed', remove_programs(commands, folder, found), None))
            except Exception as exc:
                results.put(('removed', None, str(exc)))
        threading.Thread(target=run, daemon=True).start()

    def recheck_conflicts():
        set_conflict_status('Verificando…')
        check_conflicts()

    def reapply_pc():
        parts = [p for p in active_parts('all') if p != 'strip']
        if parts:
            submit(make_job(parts, lambda part: selections[part]), report)

    def periodic_check():
        # A cada minuto: o aviso some assim que o programa é removido e volta se ele voltar.
        check_conflicts()
        root.after(60 * 1000, periodic_check)

    # Rotinas por horário e perfis por jogo/app.
    auto = {'routines': config.get('routines') or [], 'profiles': config.get('profiles') or []}
    switcher = ProfileSwitcher()
    state['last_run'] = {}
    state['pending'] = None  # ação que esperou o envio anterior terminar
    state['auto_win'] = None
    state['profile_label'] = ''

    def save_automation():
        config['routines'], config['profiles'] = auto['routines'], auto['profiles']
        try:
            save_config(config)
        except OSError:
            pass

    def send_all(sel_for, prefix):
        """Envia para tudo. False se já há um envio em andamento (tenta depois)."""
        parts = active_parts('all')
        if not parts:
            return True
        if state['busy']:
            return False

        def done(result):
            if 'strip' in parts:
                power.set('Fita: ligada')
            report(result)
            status.set(prefix + ' ' + status.get())
        submit(make_job(parts, sel_for), done)
        return True

    def run_routine(r):
        if r['action'] == 'apply':
            sel = dict(r['selection'])
            for key in ('all', 'strip', 'board', 'ram'):
                selections[key] = dict(sel)
            load_selection()
            remember()
            if switcher.active:
                # Jogo/app aberto: a cor da rotina entra quando ele fechar.
                return True
            paint_icon(sel)
            return send_all(lambda part: sel, f"Rotina {r['time']}:")
        if state['busy']:
            return False
        set_power(r['action'] == 'on', 'all')
        return True

    def automation_tick():
        try:
            if state['pending'] and state['pending']():
                state['pending'] = None
            for r in due_routines(auto['routines'], datetime.now(), state['last_run']):
                log(f"Rotina {r['time']}: {r['action']}")
                if not run_routine(r):
                    state['pending'] = lambda r=r: run_routine(r)
            if auto['profiles'] or switcher.active:
                profile = pick_profile(auto['profiles'], process_names(), foreground_process())
                decision = switcher.decide(profile)
                if decision:
                    kind, p = decision
                    if kind == 'apply':
                        sel = dict(p['selection'])
                        state['profile_label'] = p.get('label') or p['process']
                        log('Perfil ativado: ' + state['profile_label'])
                        paint_icon(sel)
                        action = lambda: send_all(lambda part: sel, f"Perfil {state['profile_label']}:")
                    else:
                        log('Perfil encerrado; voltando às cores salvas.')
                        state['profile_label'] = ''
                        paint_icon(selections['all'])
                        action = lambda: send_all(lambda part: selections[part], 'Cores restauradas.')
                    if not action():
                        state['pending'] = action
                    try:
                        icon.update_menu()
                    except Exception:
                        pass
        except Exception as exc:
            log('Automação: ' + str(exc))
        root.after(3000, automation_tick)

    def open_automation():
        show()
        win = state['auto_win']
        if win and win.win.winfo_exists():
            win.win.lift()
            return
        state['auto_win'] = AutomationWindow(root, auto, EFFECTS, lambda: dict(selections['all']),
                                             windowed_apps, save_automation)

    def open_picker(initial, on_pick):
        def picked(colour):
            config['recent_colours'] = remember_colour(config.get('recent_colours') or [], colour)
            try:
                save_config(config)
            except OSError:
                pass
            on_pick(colour)
        ColourPicker(root, initial, picked, config.get('recent_colours') or [])

    def pick():
        def chosen(colour):
            v.colour.set(colour)
            if v.mode.get() == 'white':
                v.mode.set('colour')
        open_picker(v.colour.get(), chosen)

    def loaded(items):
        values = {item['code']: item['value'] for item in items}
        if 'switch_led' in values:
            power.set('Fita: ligada' if values['switch_led'] else 'Fita: desligada')
        sel = selections['strip']
        current = values.get('work_mode')
        if current in ('white', 'colour'):
            sel['mode'] = current
        if current == 'colour':
            c = values.get('colour_data_v2', {})
            if isinstance(c, str):
                c = json.loads(c) if c else {}
            if c:
                sel['brightness'] = max(1, round(c['v']/10))
                rgb = colorsys.hsv_to_rgb(c['h']/360, c['s']/1000, 1)
                sel['colour'] = '#' + ''.join(f'{round(x*255):02x}' for x in rgb)
        elif current == 'white':
            sel['brightness'] = max(1, round(values.get('bright_value_v2', 500)/10))
        sel['temperature'] = values.get('temp_value_v2', sel['temperature'])
        if v.target.get() == 'strip':
            load_selection()

    def refresh():
        api = state['api']
        submit(lambda: api.request('GET', 'status'), loaded, needs_tuya=True)

    def settings():
        win = tk.Toplevel(root)
        win.title('Configuração Tuya')
        win.resizable(False, False)
        win.transient(root)
        win.grab_set()
        box = ttk.Frame(win, padding=18)
        box.pack()
        ttk.Label(box, text='Use as chaves do projeto vinculado à fita.\nRegião: Western America.', justify='left').pack(anchor='w', pady=(0, 12))
        entries = {}
        for key, label in [('client_id', 'Access ID / Client ID'), ('secret', 'Access Secret'), ('device_id', 'Device ID')]:
            ttk.Label(box, text=label).pack(anchor='w')
            var = tk.StringVar(value=config[key])
            ttk.Entry(box, textvariable=var, width=43, show='*' if key == 'secret' else '').pack(pady=(2, 9))
            entries[key] = var
        ttk.Separator(box).pack(fill='x', pady=10)
        auto = tk.BooleanVar(value=startup_enabled())
        led_start = tk.BooleanVar(value=config.get('led_on_start', False))
        led_stop = tk.BooleanVar(value=config.get('led_off_shutdown', False))
        ttk.Checkbutton(box, text='Iniciar aplicativo com o Windows', variable=auto).pack(anchor='w')
        ttk.Checkbutton(box, text='Ligar LEDs ao iniciar com o Windows', variable=led_start).pack(anchor='w')
        ttk.Checkbutton(box, text='Desligar LEDs ao desligar/reiniciar o PC', variable=led_stop).pack(anchor='w')
        ttk.Separator(box).pack(fill='x', pady=10)
        pc_sync = tk.BooleanVar(value=v.pc_sync.get())
        ttk.Checkbutton(box, text='Sincronizar placa-mãe e memórias (OpenRGB)', variable=pc_sync).pack(anchor='w')
        pc_info = tk.StringVar(value='Requer o OpenRGB aberto com o servidor SDK ativo.')
        def test_pc():
            pc_info.set('Procurando dispositivos…')
            win.update_idletasks()
            try:
                names = state['pc'].devices((0, 1))
                pc_info.set('Encontrados: ' + ', '.join(names) if names else
                            'Nenhuma placa-mãe ou memória RGB. Abra o OpenRGB como administrador.')
            except RuntimeError as exc:
                pc_info.set(str(exc))
        ttk.Button(box, text='Testar OpenRGB', command=test_pc).pack(fill='x', pady=(6, 0))
        ttk.Label(box, textvariable=pc_info, wraplength=320, justify='left').pack(anchor='w', pady=(4, 0))
        ttk.Label(box, text='Inicia após entrar na sua conta, na bandeja.\nDesligamento requer app aberto e internet.\nFechar a janela mantém o app ativo; Sair encerra.',
                  wraplength=320).pack(anchor='w', pady=8)
        def save():
            if state['busy']:
                messagebox.showinfo('Aguarde', 'Espere o comando atual terminar.', parent=win)
                return
            new = {k: v.get().strip() for k, v in entries.items()}
            filled = [bool(v) for v in new.values()]
            if not all(filled) and (any(filled) or not pc_sync.get()):
                messagebox.showerror('Configuração', 'Preencha os três campos da Tuya.', parent=win)
                return
            new.update(led_on_start=led_start.get(), led_off_shutdown=led_stop.get(),
                       pc_sync=pc_sync.get())
            previous_startup = startup_enabled()
            try:
                set_startup(auto.get())
                save_config({**config, **new})
            except OSError:
                try:
                    set_startup(previous_startup)
                except OSError:
                    pass
                messagebox.showerror('Configuração', 'Não foi possível salvar. Confira as permissões do Windows.', parent=win)
                return
            config.update(new)
            state['api'] = Tuya(config)
            win.destroy()
            if v.pc_sync.get() != new['pc_sync']:
                v.pc_sync.set(new['pc_sync'])
            if tuya_ready():
                refresh()
            else:
                status.set('Configuração salva. Escolha a cor e clique em Aplicar.')
        ttk.Button(box, text='Salvar e testar conexão', command=save).pack(fill='x')
        ttk.Label(box, text='As chaves ficam em um arquivo local no seu perfil.').pack(pady=(10, 0))

    def pc_sync_changed(*_):
        config['pc_sync'] = v.pc_sync.get()
        try:
            save_config(config)
        except OSError:
            pass
        check_conflicts()
        if config['pc_sync']:
            status.set('Placa-mãe e memórias ativadas. Use as abas para escolher cada uma.')
        elif not tuya_ready():
            settings()
    v.pc_sync.trace_add('write', pc_sync_changed)

    def ram_preview(t, sel, positions):
        """Prévia dos pentes: os escolhidos com a seleção da tela, os outros como estão."""
        count = v.stick_count.get()
        names = [f'p{i}' for i in range(1, count + 1)]
        saved = state['pc'].ram.snapshot()
        order = state['pc'].ram.known or state['pc'].ram.order_known(list(saved))
        sticks = {}
        for i, name in enumerate(names):
            address = order[i] if i < len(order) else None
            st = saved.get(address) if address else None
            sticks[name] = st or {'sel': dict(selections['ram']), 'on': True, 'group': -1}
        for p in positions:
            if 0 < p <= count:
                sticks[names[p - 1]] = {'sel': dict(sel), 'on': True, 'group': -2}
        colours = stick_colours(sticks, names, t)
        return [colours.get(n, [(0, 0, 0)] * 5) for n in names]

    def open_stick_order():
        show()
        StickOrderWindow(root, state['pc'], on_order_saved, fallback=dict(selections['ram']))

    def on_order_saved(order):
        config['ram_order'] = list(order)
        config['ram_count'] = len(order)
        v.stick_count.set(len(order))
        state['pc'].ram.order = list(order)
        state['pc'].ram.order_known(list(order))
        sync_stick_on()
        save_ram_state()
        status.set('Ordem dos pentes salva.')

    panel = build_panel(frame, v, pick, apply, set_power, EFFECTS, SPEEDS,
                        lambda: results.put(('fix', None, None)),
                        SimpleNamespace(preview=ram_preview, open_order=open_stick_order,
                                        toggle=toggle_stick, only_selected=only_selected))
    set_header_icon = panel.set_icon

    def show():
        root.deiconify()
        root.lift()
        root.focus_force()

    def quit_app():
        listener.stop()
        state['pc'].close()
        icon.stop()
        tasks.put(None)
        root.destroy()

    build_menu(root, settings, refresh, root.withdraw, quit_app,
               [('Rotinas e perfis por jogo/app…', open_automation),
                ('Programas que interferem nos LEDs…', open_conflicts)])

    def live_art(sel, t=None):
        """Desenho do ícone no instante t: mesma cor que o efeito mostra agora."""
        if is_animated(sel):
            return dict(colour=rgb_to_hex(fx_single(sel, time.time() if t is None else t)))
        return icon_for(sel)

    def paint_window_icon(sel, t=None):
        art = live_art(sel, t)
        window_icon = ImageTk.PhotoImage(draw_icon(size=64, **art))
        root.iconphoto(True, window_icon)
        set_header_icon(ImageTk.PhotoImage(draw_icon(size=44, **art)))
        state['window_icon'] = window_icon

    def paint_icon(sel, t=None, menu=True):
        paint_window_icon(sel, t)
        try:
            icon.icon = draw_icon(size=64, **live_art(sel, t))
            if menu:
                icon.update_menu()  # no Windows o menu não se refaz sozinho
        except Exception:
            pass

    def animation_tick():
        """Relógio único: prévia (30 fps) e ícones (8 fps) seguem o mesmo efeito
        e o mesmo instante que as memórias."""
        t = time.time()
        try:
            if root.state() == 'normal':
                panel.tick(t)
            state['icon_frame'] = state.get('icon_frame', 0) + 1
            sel = selections['all']
            if is_animated(sel) and state['icon_frame'] % 4 == 0:
                paint_icon(sel, t, menu=False)
                if state['flyout'].visible:
                    state['flyout'].refresh_icon()
            elif not is_animated(sel) and state.get('icon_was_animated'):
                paint_icon(sel)  # efeito parou: volta ao desenho fixo
            state['icon_was_animated'] = is_animated(sel)
        except Exception as exc:
            log('Animação: ' + str(exc))
        root.after(33, animation_tick)

    from effects import QUICK_COLOURS, QUICK_BRIGHTNESS

    def quick(changes):
        return lambda *_: results.put(('quick', changes, None))

    def is_current(test):
        return lambda _item: test(selections['all'])

    colour_items = [pystray.MenuItem(
        name, quick({'mode': 'colour', 'colour': hex_}),
        checked=is_current(lambda s, h=hex_: s['mode'] == 'colour' and s['colour'].lower() == h),
        radio=True) for name, hex_ in QUICK_COLOURS]
    white_items = [pystray.MenuItem(
        name, quick({'mode': 'white', 'temperature': temp}),
        checked=is_current(lambda s, t=temp: s['mode'] == 'white' and s['temperature'] == t),
        radio=True) for name, temp in (('Branco quente', 0), ('Branco neutro', 500), ('Branco frio', 1000))]
    effect_items = [pystray.MenuItem(
        label, quick({'mode': 'effect', 'effect': key}),
        checked=is_current(lambda s, k=key: s['mode'] == 'effect' and s['effect'] == k),
        radio=True) for key, label, *_ in EFFECTS if key != 'static']
    speed_items = [pystray.MenuItem(
        label, quick({'speed': key}),
        checked=is_current(lambda s, k=key: s['speed'] == k),
        radio=True) for key, label in SPEEDS]
    bright_items = [pystray.MenuItem(
        f'{value}%', quick({'brightness': value}),
        checked=is_current(lambda s, b=value: s['brightness'] == b),
        radio=True) for value in QUICK_BRIGHTNESS]

    paint_window_icon(selections['all'])

    # Botão direito no ícone: painel no visual do app em vez do menu nativo.
    def flyout_quick(changes):
        quick_apply(changes)
        flyout.refresh()

    def flyout_pick():
        show()
        open_picker(selections['all'].get('colour'),
                    lambda c: quick_apply({'mode': 'colour', 'colour': c}))

    flyout = TrayFlyout(root, SimpleNamespace(
        selection=lambda: dict(selections['all']),
        quick=flyout_quick, pick_colour=flyout_pick,
        power=lambda on: set_power(on, 'all'),
        open_main=show, open_auto=open_automation, open_conflicts=open_conflicts,
        quit=quit_app, warning=v.warning_short, status=status,
        subtitle=lambda: power.get() + (' · Perfil: ' + state['profile_label']
                                        if state['profile_label'] else ''),
        icon_image=lambda size: ImageTk.PhotoImage(draw_icon(size=size, **live_art(selections['all'])))))
    state['flyout'] = flyout
    IconClass = (tray_icon_class(lambda: results.put(('flyout', None, None)))
                 if os.name == 'nt' else pystray.Icon)
    icon = IconClass('ControleLED', draw_icon(size=64, **icon_for(selections['all'])),
                        'Controle LED · PC', menu=pystray.Menu(
        pystray.MenuItem('Abrir controles', lambda *_: results.put(('show', None, None)), default=True),
        pystray.MenuItem('⚠ Programas interferindo nos LEDs…', lambda *_: results.put(('fix', None, None)),
                         visible=lambda _item: bool(state['alerts'])),
        pystray.MenuItem(lambda _item: 'Perfil ativo: ' + state['profile_label'], None,
                         enabled=False, visible=lambda _item: bool(state['profile_label'])),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Cores', pystray.Menu(*colour_items, pystray.Menu.SEPARATOR, *white_items)),
        pystray.MenuItem('Efeitos', pystray.Menu(*effect_items, pystray.Menu.SEPARATOR,
                                                 pystray.MenuItem('Velocidade', pystray.Menu(*speed_items)))),
        pystray.MenuItem('Brilho', pystray.Menu(*bright_items)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Ligar', lambda *_: results.put(('power', True, None))),
        pystray.MenuItem('Desligar', lambda *_: results.put(('power', False, None))),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Rotinas e perfis…', lambda *_: results.put(('auto', None, None))),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Sair', lambda *_: results.put(('quit', None, None)))))
    threading.Thread(target=icon.run, daemon=True).start()
    root.protocol('WM_DELETE_WINDOW', root.withdraw)
    try:
        listener.start()
    except RuntimeError as exc:
        status.set(str(exc))
        messagebox.showwarning('Integração Windows', str(exc), parent=root)
    root.after(100, poll)
    root.after(1500, periodic_check)
    root.after(4000, automation_tick)
    root.after(2500, flyout.prepare)
    root.after(500, animation_tick)
    if config.get('pc_sync') and config.get('ram_sticks'):
        # Efeitos das memórias são animados pelo app: retoma o estado salvo de cada pente.
        def restore_sticks():
            ram = state['pc'].ram
            ram.restore(config['ram_sticks'])
            ram.order_known([a for a in (config.get('ram_order') or sorted(config['ram_sticks']))])
            sync_stick_on()
        root.after(2000, restore_sticks)
    if not ready:
        root.after(200, settings)
    if startup_launch and ready:
        root.withdraw()
        if config.get('led_on_start', False):
            def startup_on(job):
                last_error = None
                for attempt in range(6):
                    try:
                        done, errors = job()
                        if errors and attempt < 5:
                            raise RuntimeError(' '.join(errors))
                        return done, errors
                    except Exception as exc:
                        last_error = exc
                        if attempt < 5:
                            time.sleep(5)
                raise last_error
            def begin_startup():
                if state['busy']:
                    root.after(500, begin_startup)
                    return
                state['busy'] = True
                # Fita: só liga (mantém a cor dela). PC: restaura a seleção salva
                # de cada parte, pois a placa volta ao padrão após reiniciar.
                job = make_job(active_parts('all'), lambda part: selections[part], True)
                tasks.put((lambda: startup_on(job), 'startup_done'))
            root.after(3000, begin_startup)
    root.mainloop()


if __name__ == '__main__':
    main()

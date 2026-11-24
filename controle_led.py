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
    from conflicts import find_conflicts, run_fix

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
               'effect': 'breathing', 'speed': 'medium'}
    selections = {key: dict(default, **(config.get('selections') or {}).get(key, {}))
                  for key in ('all', 'strip', 'board', 'ram')}
    state = {'api': Tuya(config), 'pc': PcLighting(launcher=openrgb_launcher), 'busy': False,
             'loading': False}
    ready = tuya_ready() or config.get('pc_sync')
    v = SimpleNamespace(
        target=tk.StringVar(value='all'),
        mode=tk.StringVar(), colour=tk.StringVar(), brightness=tk.IntVar(),
        temperature=tk.IntVar(), effect=tk.StringVar(), speed=tk.StringVar(),
        pc_sync=tk.BooleanVar(value=config.get('pc_sync', False)),
        power=tk.StringVar(value='Fita: estado não consultado'),
        warning=tk.StringVar(value=''),
        status=tk.StringVar(value='Escolha a aba, a cor ou o efeito e clique em Aplicar.' if ready
                            else 'Configure as credenciais para começar.'))
    status, power = v.status, v.power
    SEL_KEYS = ('mode', 'colour', 'brightness', 'temperature', 'effect', 'speed')

    def load_selection(*_):
        state['loading'] = True
        sel = selections[v.target.get()]
        for key in SEL_KEYS:
            getattr(v, key).set(sel[key])
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
                    command('scene_data_v2', tuya_scene(sel['effect'], sel['colour'],
                                                        sel['brightness'], sel['speed']))]
        if mode == 'white':
            return [command('switch_led', True), command('work_mode', 'white'),
                    command('bright_value_v2', max(10, sel['brightness']*10)),
                    command('temp_value_v2', sel['temperature'])]
        return [command('switch_led', True), command('work_mode', 'colour'),
                command('colour_data_v2', colour_value(sel['colour'], sel['brightness']))]

    def make_job(parts, sel_for, power_on=None):
        """Monta o trabalho do worker. sel_for(part) devolve a seleção da parte.
        Os dados são copiados aqui, na thread da interface."""
        steps = []
        if 'strip' in parts:
            cmds = ([command('switch_led', power_on)] if power_on is not None
                    else tuya_commands(sel_for('strip')))
            steps.append(('fita', lambda c=cmds: state['api'].send(c)))
        for part in ('board', 'ram'):
            if part in parts:
                types = (PC_TYPES[part],)
                if power_on is False:
                    steps.append((NAMES[part], lambda t=types: state['pc'].off(t)))
                else:
                    sel = dict(sel_for(part))
                    steps.append((NAMES[part], lambda t=types, s=sel: state['pc'].apply_selection(s, t)))

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
        if any(name != 'fita' for name in done):
            check_conflicts()

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
                    fix_conflicts()
                    continue
                if cb == 'fixed':
                    state['fixing'] = False
                    if error:
                        status.set(error)
                        log('Correção de conflitos: ' + error)
                    elif value:
                        log('Conflitos corrigidos; reaplicando as cores do PC.')
                        status.set('Conflitos corrigidos. Reaplicando as cores…')
                        reapply_pc()
                    else:
                        status.set('Correção cancelada.')
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
        # Ligar no PC restaura a seleção salva de cada parte.
        submit(make_job(parts, lambda part: selections[part], value), done)

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
        submit(make_job(parts, lambda part: sel), done)

    def quick_apply(changes):
        """Atalho da bandeja: aplica a mudança em tudo (aba Geral)."""
        if state['busy']:
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
    state['fixing'] = False

    def check_conflicts():
        if not config.get('pc_sync') or os.name != 'nt':
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

    def show_conflicts(found):
        keys = [key for key, _ in found]
        if keys and keys != [k for k, _ in state['conflicts']]:
            log('Conflitos encontrados: ' + ', '.join(keys))
        state['conflicts'] = found
        v.warning.set(' '.join(text for _, text in found))
        try:
            icon.update_menu()
        except Exception:
            pass

    def fix_conflicts():
        if state['fixing'] or not state['conflicts']:
            return
        state['fixing'] = True
        status.set('Corrigindo conflitos… confirme o pedido de permissão do Windows.')

        def run():
            try:
                results.put(('fixed', run_fix(folder), None))
            except Exception as exc:
                results.put(('fixed', None, str(exc)))
        threading.Thread(target=run, daemon=True).start()

    def reapply_pc():
        parts = [p for p in active_parts('all') if p != 'strip']
        if parts:
            submit(make_job(parts, lambda part: selections[part]), report)

    def periodic_check():
        check_conflicts()
        root.after(5 * 60 * 1000, periodic_check)

    def pick():
        selected = colorchooser.askcolor(v.colour.get(), parent=root)[1]
        if selected:
            v.colour.set(selected)
            if v.mode.get() == 'white':
                v.mode.set('colour')

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

    set_header_icon = build_panel(frame, v, pick, apply, set_power, EFFECTS, SPEEDS,
                                  lambda: results.put(('fix', None, None)))

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

    build_menu(root, settings, refresh, root.withdraw, quit_app)

    def paint_window_icon(sel):
        art = icon_for(sel)
        window_icon = ImageTk.PhotoImage(draw_icon(size=64, **art))
        root.iconphoto(True, window_icon)
        set_header_icon(ImageTk.PhotoImage(draw_icon(size=44, **art)))
        state['window_icon'] = window_icon

    def paint_icon(sel):
        paint_window_icon(sel)
        try:
            icon.icon = draw_icon(size=64, **icon_for(sel))
            icon.update_menu()  # no Windows o menu não se refaz sozinho
        except Exception:
            pass

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
    icon = pystray.Icon('ControleLED', draw_icon(size=64, **icon_for(selections['all'])),
                        'Controle LED · PC', menu=pystray.Menu(
        pystray.MenuItem('Abrir controles', lambda *_: results.put(('show', None, None)), default=True),
        pystray.MenuItem('⚠ Corrigir conflitos de cores', lambda *_: results.put(('fix', None, None)),
                         visible=lambda _item: bool(state['conflicts'])),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Cores', pystray.Menu(*colour_items, pystray.Menu.SEPARATOR, *white_items)),
        pystray.MenuItem('Efeitos', pystray.Menu(*effect_items, pystray.Menu.SEPARATOR,
                                                 pystray.MenuItem('Velocidade', pystray.Menu(*speed_items)))),
        pystray.MenuItem('Brilho', pystray.Menu(*bright_items)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Ligar', lambda *_: results.put(('power', True, None))),
        pystray.MenuItem('Desligar', lambda *_: results.put(('power', False, None))),
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

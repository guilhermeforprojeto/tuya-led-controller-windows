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
    startup_launch = '--startup' in sys.argv
    mutex = None
    if os.name == 'nt':
        import win32api, win32event, winerror
        mutex = win32event.CreateMutex(None, False, r'Local\ControleLED-Pessoal')
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            messagebox.showinfo('Controle LED', 'O aplicativo já está aberto. Procure o ícone perto do relógio.')
            return
    from PIL import Image, ImageDraw

    folder = Path(os.environ.get('APPDATA', str(Path.home()))) / 'ControleLED'
    folder.mkdir(parents=True, exist_ok=True)
    config_path = folder / 'config.json'
    config = {'client_id': '', 'secret': '', 'device_id': DEVICE, 'led_on_start': False, 'led_off_shutdown': False}
    try:
        config.update(json.loads(config_path.read_text(encoding='utf-8')))
    except (OSError, ValueError):
        pass
    def log(message):
        try:
            with (folder / 'eventos.log').open('a', encoding='utf-8') as f:
                f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + message + '\n')
        except OSError:
            pass

    def shutdown_off():
        if not all(config.get(k) for k in ('client_id', 'secret', 'device_id')):
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
    root.geometry('390x510')
    root.resizable(False, False)
    root.configure(bg='#f5f6f8')
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TButton', padding=7)
    frame = ttk.Frame(root, padding=18)
    frame.pack(fill='both', expand=True)
    tasks, results = queue.Queue(), queue.Queue()
    state = {'api': Tuya(config), 'colour': '#a020f0', 'busy': False}
    status = tk.StringVar(value='Configure as credenciais para começar.' if not config['client_id'] else 'Pronto. Clique em Atualizar estado.')
    brightness = tk.IntVar(value=50)
    temperature = tk.IntVar(value=500)
    mode = tk.StringVar(value='colour')
    power = tk.StringVar(value='Estado ainda não consultado')

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

    def submit(func, callback=None):
        if state['busy']:
            return
        if not config['client_id'] or not config['secret'] or not config['device_id']:
            settings()
            return
        state['busy'] = True
        status.set('Comunicando com a Tuya…')
        tasks.put((func, callback))

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
                        power.set('Ligada')
                        status.set('Fita ligada na inicialização.')
                    continue
                if cb == 'show':
                    show()
                    continue
                if cb == 'quit':
                    quit_app()
                    return
                if cb == 'power':
                    set_power(value)
                    continue
                state['busy'] = False
                if error:
                    status.set(error)
                    messagebox.showerror('Controle LED', error, parent=root)
                else:
                    status.set('Comando aceito pela Tuya.' if cb is None else 'Estado atualizado.')
                    if cb:
                        cb(value)
        except queue.Empty:
            pass
        root.after(100, poll)

    def set_power(value):
        api = state['api']
        submit(lambda: api.send([command('switch_led', value)]),
               lambda _: power.set('Ligada' if value else 'Desligada'))

    def apply():
        cmds = [command('switch_led', True), command('work_mode', mode.get())]
        if mode.get() == 'colour':
            cmds.append(command('colour_data_v2', colour_value(state['colour'], brightness.get())))
        else:
            cmds.extend([command('bright_value_v2', max(10, brightness.get()*10)),
                         command('temp_value_v2', temperature.get())])
        api = state['api']
        submit(lambda: api.send(cmds), lambda _: power.set('Ligada'))

    def pick():
        selected = colorchooser.askcolor(state['colour'], parent=root)[1]
        if selected:
            state['colour'] = selected
            swatch.configure(bg=selected)
            mode.set('colour')

    def loaded(items):
        values = {item['code']: item['value'] for item in items}
        if 'switch_led' in values:
            power.set('Ligada' if values['switch_led'] else 'Desligada')
        current = values.get('work_mode')
        if current in ('white', 'colour'):
            mode.set(current)
        if current == 'colour':
            c = values.get('colour_data_v2', {})
            if isinstance(c, str):
                c = json.loads(c)
            if c:
                brightness.set(max(1, round(c['v']/10)))
                rgb = colorsys.hsv_to_rgb(c['h']/360, c['s']/1000, 1)
                state['colour'] = '#' + ''.join(f'{round(x*255):02x}' for x in rgb)
                swatch.configure(bg=state['colour'])
        elif current == 'white':
            brightness.set(max(1, round(values.get('bright_value_v2', 500)/10)))
        temperature.set(values.get('temp_value_v2', 500))

    def refresh():
        api = state['api']
        submit(lambda: api.request('GET', 'status'), loaded)

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
        ttk.Label(box, text='Inicia após entrar na sua conta, na bandeja.\nDesligamento requer app aberto e internet.\nFechar a janela mantém o app ativo; Sair encerra.',
                  wraplength=320).pack(anchor='w', pady=8)
        def save():
            if state['busy']:
                messagebox.showinfo('Aguarde', 'Espere o comando atual terminar.', parent=win)
                return
            new = {k: v.get().strip() for k, v in entries.items()}
            if not all(new.values()):
                messagebox.showerror('Configuração', 'Preencha os três campos.', parent=win)
                return
            new.update(led_on_start=led_start.get(), led_off_shutdown=led_stop.get())
            previous_startup = startup_enabled()
            try:
                set_startup(auto.get())
                temp = config_path.with_suffix('.tmp')
                temp.write_text(json.dumps(new, indent=2), encoding='utf-8')
                temp.replace(config_path)
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
            refresh()
        ttk.Button(box, text='Salvar e testar conexão', command=save).pack(fill='x')
        ttk.Label(box, text='As chaves ficam em um arquivo local no seu perfil.').pack(pady=(10, 0))

    ttk.Label(frame, text='Controle LED', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
    ttk.Label(frame, textvariable=power).pack(anchor='w', pady=(0, 12))
    row = ttk.Frame(frame)
    row.pack(fill='x')
    ttk.Button(row, text='Ligar', command=lambda: set_power(True)).pack(side='left', expand=True, fill='x')
    ttk.Button(row, text='Desligar', command=lambda: set_power(False)).pack(side='left', expand=True, fill='x', padx=(8, 0))
    row = ttk.Frame(frame)
    row.pack(fill='x', pady=12)
    ttk.Radiobutton(row, text='Cor RGB', variable=mode, value='colour').pack(side='left')
    ttk.Radiobutton(row, text='Branco', variable=mode, value='white').pack(side='left', padx=15)
    swatch = tk.Button(row, text='Escolher cor', bg=state['colour'], fg='white', command=pick)
    swatch.pack(side='right')
    ttk.Label(frame, text='Brilho').pack(anchor='w')
    tk.Scale(frame, from_=1, to=100, orient='horizontal', variable=brightness, relief='flat').pack(fill='x')
    ttk.Label(frame, text='Branco: quente → frio').pack(anchor='w', pady=(8, 0))
    tk.Scale(frame, from_=0, to=1000, orient='horizontal', variable=temperature, relief='flat').pack(fill='x')
    ttk.Button(frame, text='Aplicar cor / branco e brilho', command=apply).pack(fill='x', pady=(10, 8))
    row = ttk.Frame(frame)
    row.pack(fill='x')
    ttk.Button(row, text='Atualizar estado', command=refresh).pack(side='left')
    ttk.Button(row, text='Configuração', command=settings).pack(side='right')
    ttk.Label(frame, textvariable=status, wraplength=350).pack(anchor='w', pady=(10, 0))

    def show():
        root.deiconify()
        root.lift()
        root.focus_force()

    def quit_app():
        listener.stop()
        icon.stop()
        tasks.put(None)
        root.destroy()

    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((8, 4, 56, 52), fill='#a020f0')
    draw.rounded_rectangle((23, 45, 41, 61), radius=4, fill='#667085')
    icon = pystray.Icon('ControleLED', img, 'Controle LED · PC', menu=pystray.Menu(
        pystray.MenuItem('Abrir controles', lambda *_: results.put(('show', None, None)), default=True),
        pystray.MenuItem('Ligar', lambda *_: results.put(('power', True, None))),
        pystray.MenuItem('Desligar', lambda *_: results.put(('power', False, None))),
        pystray.MenuItem('Sair', lambda *_: results.put(('quit', None, None)))))
    threading.Thread(target=icon.run, daemon=True).start()
    root.protocol('WM_DELETE_WINDOW', root.withdraw)
    try:
        listener.start()
    except RuntimeError as exc:
        status.set(str(exc))
        messagebox.showwarning('Integração Windows', str(exc), parent=root)
    root.after(100, poll)
    if not config['client_id']:
        root.after(200, settings)
    if startup_launch and config['client_id'] and config['secret']:
        root.withdraw()
        if config.get('led_on_start', False):
            def startup_on():
                last_error = None
                for attempt in range(6):
                    try:
                        state['api'].send([command('switch_led', True)])
                        return True
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
                tasks.put((startup_on, 'startup_done'))
            root.after(3000, begin_startup)
    root.mainloop()


if __name__ == '__main__':
    main()

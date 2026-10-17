"""Integração com a sessão do Windows; importável em testes sem Windows."""
import os
import subprocess
import sys
import threading
from pathlib import Path

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME = 'ControleLED'


def startup_command():
    if getattr(sys, 'frozen', False):
        args = [sys.executable, '--startup']
    else:
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        args = [str(pythonw if pythonw.exists() else sys.executable),
                str(Path(__file__).with_name('controle_led.py').resolve()), '--startup']
    return subprocess.list2cmdline(args)


def startup_enabled():
    if os.name != 'nt':
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_NAME)
        return True
    except FileNotFoundError:
        return False


def set_startup(enabled):
    if os.name != 'nt':
        raise OSError('Esta configuração requer Windows.')
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError:
                pass


class SessionListener:
    def __init__(self, should_switch_off, switch_off, log):
        self.should_switch_off = should_switch_off
        self.switch_off = switch_off
        self.log = log
        self.hwnd = None
        self.ready = threading.Event()
        self.error = None

    def handle(self, msg, wparam, lparam):
        if msg == 0x0011:  # WM_QUERYENDSESSION: não impedir encerramento
            return 1
        if msg == 0x0016:  # WM_ENDSESSION: só quando confirmado
            # ENDSESSION_LOGOFF: sair da conta não é desligar/reiniciar.
            if wparam and not (lparam & 0x80000000) and self.should_switch_off():
                task = threading.Thread(target=self.switch_off, daemon=True)
                task.start()
                task.join(3)  # limite total; nunca bloquear desligamento indefinidamente
            return 0
        return None

    def start(self):
        if os.name != 'nt':
            return
        threading.Thread(target=self._run, daemon=True).start()
        self.ready.wait(2)
        if self.error:
            raise RuntimeError(self.error)
        if not self.ready.is_set():
            raise RuntimeError('Não foi possível registrar o encerramento do Windows.')

    def _run(self):
        try:
            import win32api
            import win32con
            import win32gui
            def proc(hwnd, msg, wp, lp):
                handled = self.handle(msg, wp, lp)
                if handled is not None:
                    return handled
                if msg == win32con.WM_CLOSE:
                    win32gui.DestroyWindow(hwnd)
                    return 0
                if msg == win32con.WM_DESTROY:
                    win32gui.PostQuitMessage(0)
                    return 0
                return win32gui.DefWindowProc(hwnd, msg, wp, lp)
            cls = win32gui.WNDCLASS()
            cls.hInstance = win32api.GetModuleHandle(None)
            cls.lpszClassName = 'ControleLEDSessionListener'
            cls.lpfnWndProc = proc
            atom = win32gui.RegisterClass(cls)
            # Janela top-level oculta: recebe mensagens de encerramento.
            self.hwnd = win32gui.CreateWindow(atom, 'ControleLED Session', 0,
                0, 0, 0, 0, 0, 0, cls.hInstance, None)
            self.ready.set()
            win32gui.PumpMessages()
        except Exception as exc:
            self.error = str(exc)
            self.log('Falha na integração com Windows: ' + str(exc))
            self.ready.set()

    def stop(self):
        if self.hwnd:
            import win32gui
            win32gui.PostMessage(self.hwnd, 0x0010, 0, 0)

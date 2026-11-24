"""Consultas leves ao Windows: processos, janela em foco e programas instalados.

Usa ctypes (Toolhelp32) para listar processos sem abrir outro programa,
o que permite checar a cada poucos segundos sem pesar no PC.
"""
import ctypes
import os
from ctypes import wintypes

TH32CS_SNAPPROCESS = 0x2
MAX_PATH = 260


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
                ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', ctypes.c_long),
                ('dwFlags', wintypes.DWORD), ('szExeFile', ctypes.c_wchar * MAX_PATH)]


def processes():
    """{pid: nome.exe} de todos os processos (sem precisar de administrador)."""
    if os.name != 'nt':
        return {}
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap in (None, wintypes.HANDLE(-1).value):
        return {}
    found = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            found[entry.th32ProcessID] = entry.szExeFile
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    return found


def process_names():
    return {name.lower() for name in processes().values()}


def foreground_process():
    """Nome do executável da janela em primeiro plano (minúsculo) ou ''."""
    if os.name != 'nt':
        return ''
    user32 = ctypes.WinDLL('user32')
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ''
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return processes().get(pid.value, '').lower()


def windowed_apps():
    """Programas com janela visível e título, para escolher um jogo/app.
    Devolve [(nome.exe, título)] sem repetir executável."""
    if os.name != 'nt':
        return []
    user32 = ctypes.WinDLL('user32')
    names = processes()
    seen, apps = set(), []
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, 4):  # 4 = GW_OWNER
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if not length:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        name = names.get(pid.value, '')
        if name and name.lower() not in seen and name.lower() not in IGNORED_APPS:
            seen.add(name.lower())
            apps.append((name, buf.value))
        return True
    user32.EnumWindows(proto(callback), 0)
    return sorted(apps, key=lambda a: a[0].lower())


IGNORED_APPS = {'explorer.exe', 'textinputhost.exe', 'applicationframehost.exe',
                'systemsettings.exe', 'shellexperiencehost.exe', 'searchhost.exe',
                'startmenuexperiencehost.exe', 'controleled.exe', 'lockapp.exe'}

UNINSTALL_KEYS = [r'Software\Microsoft\Windows\CurrentVersion\Uninstall',
                  r'Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall']
APPX_KEY = (r'Software\Classes\Local Settings\Software\Microsoft\Windows'
            r'\CurrentVersion\AppModel\Repository\Packages')


def installed_programs():
    """[(nome, comando_de_desinstalação)] dos programas instalados."""
    if os.name != 'nt':
        return []
    import winreg
    found, seen = [], set()
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for path in UNINSTALL_KEYS:
            try:
                root = winreg.OpenKey(hive, path)
            except OSError:
                continue
            with root:
                for i in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        with winreg.OpenKey(root, winreg.EnumKey(root, i)) as key:
                            name = winreg.QueryValueEx(key, 'DisplayName')[0]
                            try:
                                cmd = winreg.QueryValueEx(key, 'UninstallString')[0]
                            except OSError:
                                cmd = ''
                    except OSError:
                        continue
                    if name and name not in seen:
                        seen.add(name)
                        found.append((name, cmd))
    return found


def store_apps():
    """Nomes de pacotes da Microsoft Store instalados para o usuário."""
    if os.name != 'nt':
        return []
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPX_KEY) as root:
            return [winreg.EnumKey(root, i) for i in range(winreg.QueryInfoKey(root)[0])]
    except OSError:
        return []

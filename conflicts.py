"""Programas que brigam com o Controle LED pelas cores da placa e das memórias.

- LightingService (ASUS Aura/Armoury Crate): reaplica o perfil do Aura nas
  memórias; atualizações do Armoury Crate costumam reativá-lo.
- Uma segunda cópia do OpenRGB (ex.: atalho na pasta Inicializar enquanto o
  OpenRGB já roda como serviço): as duas gravam nos mesmos LEDs.
"""
import csv
import io
import os
import subprocess
import time
from pathlib import Path

ASUS_SERVICE = 'LightingService'
OPENRGB_SERVICE = 'OpenRGB'
SDK_PORT = 6742
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

# start type do Windows: 2 automático, 3 manual, 4 desativado
DISABLED = 4


def service_state(name):
    """(rodando, tipo_de_início) ou None se o serviço não existe."""
    if os.name != 'nt':
        return None
    import win32service
    try:
        scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
    except Exception:
        return None
    try:
        handle = win32service.OpenService(
            scm, name, win32service.SERVICE_QUERY_STATUS | win32service.SERVICE_QUERY_CONFIG)
    except Exception:
        win32service.CloseServiceHandle(scm)
        return None
    try:
        running = win32service.QueryServiceStatus(handle)[1] == win32service.SERVICE_RUNNING
        start = win32service.QueryServiceConfig(handle)[1]
        return running, start
    finally:
        win32service.CloseServiceHandle(handle)
        win32service.CloseServiceHandle(scm)


def process_ids(image='OpenRGB.exe'):
    if os.name != 'nt':
        return []
    try:
        out = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {image}', '/FO', 'CSV', '/NH'],
                             capture_output=True, text=True, timeout=10,
                             creationflags=NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [int(row[1]) for row in csv.reader(io.StringIO(out))
            if len(row) > 1 and row[0].lower() == image.lower()]


def startup_folders():
    folders = [Path(os.environ.get('APPDATA', '')) / r'Microsoft\Windows\Start Menu\Programs\Startup',
               Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) /
               r'Microsoft\Windows\Start Menu\Programs\StartUp']
    return [f for f in folders if f.is_dir()]


def openrgb_shortcuts():
    return [p for folder in startup_folders() for p in folder.glob('*.lnk')
            if 'openrgb' in p.name.lower()]


def analyse(asus, openrgb_service, pids, shortcuts):
    """Decide quais conflitos existem. Separado para poder testar."""
    found = []
    if asus is not None and (asus[0] or asus[1] != DISABLED):
        found.append(('asus', 'O serviço de iluminação da ASUS (Aura) está ativo e '
                              'troca as cores das memórias.'))
    duplicate = len(pids) > 1 or (shortcuts and openrgb_service is not None)
    if duplicate:
        found.append(('openrgb', 'Há uma segunda cópia do OpenRGB abrindo com o Windows '
                                 'e disputando os LEDs.'))
    return found


def find_conflicts():
    return analyse(service_state(ASUS_SERVICE), service_state(OPENRGB_SERVICE),
                   process_ids(), openrgb_shortcuts())


def fix_script(backup_dir, shortcuts):
    lines = ["$ErrorActionPreference = 'SilentlyContinue'",
             f"Stop-Service -Name {ASUS_SERVICE} -Force",
             f"Set-Service -Name {ASUS_SERVICE} -StartupType Disabled"]
    if shortcuts:
        lines.append(f"New-Item -ItemType Directory -Force -Path '{backup_dir}' | Out-Null")
        for path in shortcuts:
            lines.append(f"Move-Item -LiteralPath '{path}' -Destination '{backup_dir}' -Force")
    # Mantém só o OpenRGB que serve a porta do SDK; fecha as cópias extras.
    lines += [f"$server = (Get-NetTCPConnection -LocalPort {SDK_PORT} -State Listen | "
              "Select-Object -First 1).OwningProcess",
              "if ($server) { Get-Process OpenRGB | Where-Object { $_.Id -ne $server } | "
              "Stop-Process -Force }"]
    return '\r\n'.join(lines) + '\r\n'


def run_fix(folder):
    """Roda a correção como administrador (o Windows pede confirmação).
    Devolve False se a pessoa cancelar o pedido de permissão."""
    folder = Path(folder)
    script = folder / 'corrigir-conflitos.ps1'
    script.write_text(fix_script(folder / 'backup-inicializar', openrgb_shortcuts()),
                      encoding='utf-8-sig')
    import pywintypes
    import win32con
    import win32event
    from win32com.shell import shell, shellcon
    try:
        info = shell.ShellExecuteEx(
            fMask=shellcon.SEE_MASK_NOCLOSEPROCESS, lpVerb='runas', lpFile='powershell.exe',
            lpParameters=f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{script}"',
            nShow=win32con.SW_HIDE)
    except pywintypes.error as exc:
        if exc.winerror == 1223:  # pedido cancelado
            return False
        raise RuntimeError(f'Não foi possível executar a correção: {exc.strerror}') from None
    win32event.WaitForSingleObject(info['hProcess'], 60000)
    time.sleep(1)
    return True

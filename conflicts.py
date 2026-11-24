"""Programas que disputam os LEDs da placa e das memórias com o Controle LED.

Só um programa pode controlar os LEDs por vez. Qualquer outro software de RGB
(Armoury Crate/Aura, iCUE, SignalRGB, MSI Center...) regrava as cores por
cima, e o resultado são memórias e placa com cores diferentes das escolhidas.
Aqui ficam o catálogo desses programas, a detecção e as correções.
"""
import fnmatch
import os
import re
import subprocess
import time
from pathlib import Path

OPENRGB_SERVICE = 'OpenRGB'
SDK_PORT = 6742
DISABLED = 4  # tipo de início "desativado" no Windows

GENERIC_STEPS = [
    'Feche o programa (inclusive o ícone perto do relógio).',
    'Desinstale em Configurações → Aplicativos → Aplicativos instalados.',
    'Se precisar dele para mouse, teclado ou fone, desative nele o controle de '
    'placa-mãe e memórias e qualquer "sincronizar tudo".',
    'Reinicie o PC e clique em Verificar de novo.',
]

SOFTWARE = [
    dict(key='asus', name='ASUS Armoury Crate / Aura Sync',
         services=['LightingService', 'ArmouryCrateService', 'ArmouryCrateControlInterface'],
         processes=['aac*hal*.exe', 'lightingservice.exe', 'armourycrate*.exe',
                    'armourysocketserver.exe', 'armouryhtmldebugserver.exe', 'auracreator*.exe'],
         installed=r'\baura\b|armoury crate|aura creator', store=['armourycrate'],
         steps=['Clique em Parar agora: interrompe o Aura na hora (vale até reiniciar).',
                'Desinstale o Armoury Crate e todos os componentes "AURA" listados abaixo.',
                'Para remover os restos, use a ferramenta oficial da ASUS '
                '"Armoury Crate Uninstall Tool" (link abaixo).',
                'Na BIOS, desative a reinstalação automática: Advanced (ou Tool) → '
                'ASUS Armoury Crate → "Download & Install ARMOURY CRATE app" → Disabled. '
                'Sem isso o Windows reinstala o Armoury Crate sozinho.',
                'Reinicie o PC e clique em Verificar de novo.'],
         help_url='https://www.bing.com/search?q=Armoury+Crate+Uninstall+Tool+site%3Aasus.com'),
    dict(key='icue', name='Corsair iCUE', services=['CorsairService', 'iCUEDevicePluginHost'],
         processes=['icue*.exe', 'corsair.service*.exe'], installed=r'\bicue\b'),
    dict(key='signalrgb', name='SignalRGB', processes=['signalrgb*.exe'], installed=r'signalrgb'),
    dict(key='msi', name='MSI Center / Mystic Light',
         processes=['mysticlight*.exe', 'msi.centralserver*.exe', 'msi center*.exe', 'ledkeeper*.exe'],
         installed=r'mystic light|msi center|\bledkeeper', store=['msicenter']),
    dict(key='gigabyte', name='Gigabyte RGB Fusion / Control Center',
         processes=['rgbfusion*.exe', 'gigabytecontrolcenter*.exe'],
         installed=r'rgb fusion|gigabyte control center'),
    dict(key='asrock', name='ASRock Polychrome RGB', processes=['polychrome*.exe'],
         installed=r'polychrome'),
    dict(key='nzxt', name='NZXT CAM', processes=['nzxt cam*.exe'], installed=r'nzxt cam'),
    dict(key='razer', name='Razer Synapse / Chroma',
         processes=['razer synapse*.exe', 'razerappengine*.exe', 'razer chroma*.exe'],
         installed=r'razer synapse|razer chroma'),
    dict(key='xpg', name='XPG Prime / XPG RGB Sync', processes=['xpg*.exe'], installed=r'\bxpg\b'),
    dict(key='kingston', name='Kingston FURY CTRL', processes=['fury*ctrl*.exe'],
         installed=r'fury ctrl'),
    dict(key='tforce', name='T-Force Blitz', processes=['t-force*blitz*.exe', 'tforce*.exe'],
         installed=r't-?force blitz'),
    dict(key='thermaltake', name='Thermaltake TT RGB Plus', processes=['tt rgb plus*.exe'],
         installed=r'tt rgb plus'),
    dict(key='coolermaster', name='Cooler Master MasterPlus', processes=['masterplus*.exe'],
         installed=r'masterplus'),
    dict(key='lianli', name='Lian Li L-Connect', processes=['l-connect*.exe'],
         installed=r'l-connect'),
    dict(key='hyperx', name='HyperX NGENUITY', processes=['ngenuity*.exe'], installed=r'ngenuity'),
    dict(key='gskill', name='G.Skill Trident Z Lighting Control', processes=['trident*.exe'],
         installed=r'trident z lighting'),
    dict(key='crucial', name='Crucial Ballistix M.U.', processes=['ballistix*.exe'],
         installed=r'ballistix'),
    dict(key='patriot', name='Patriot Viper RGB', processes=['viper*rgb*.exe'],
         installed=r'viper rgb'),
]

KNOWN_NAMES = [s['name'] for s in SOFTWARE]


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
        return running, win32service.QueryServiceConfig(handle)[1]
    finally:
        win32service.CloseServiceHandle(handle)
        win32service.CloseServiceHandle(scm)


def startup_folders():
    folders = [Path(os.environ.get('APPDATA', '')) / r'Microsoft\Windows\Start Menu\Programs\Startup',
               Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) /
               r'Microsoft\Windows\Start Menu\Programs\StartUp']
    return [f for f in folders if f.is_dir()]


def openrgb_shortcuts():
    return [p for folder in startup_folders() for p in folder.glob('*.lnk')
            if 'openrgb' in p.name.lower()]


def analyse(procs, service_lookup, installed, store, openrgb_pids, openrgb_service, shortcuts):
    """Monta a lista de achados. Entrada já coletada, para poder testar.

    procs: nomes de processo em minúsculas; service_lookup(nome) → (rodando, início)
    ou None; installed: [(nome, desinstalar)]; store: nomes de pacotes da Store.
    """
    findings = []
    for soft in SOFTWARE:
        running = sorted(p for p in procs
                         if any(fnmatch.fnmatch(p, pat) for pat in soft.get('processes', [])))
        services = []
        for name in soft.get('services', []):
            st = service_lookup(name)
            if st is not None and (st[0] or st[1] != DISABLED):
                services.append((name, st[0]))
        pattern = soft.get('installed')
        programs = [(n, c) for n, c in installed if pattern and re.search(pattern, n, re.I)]
        packages = [p for p in store
                    if any(s in p.lower() for s in soft.get('store', []))]
        if running or services or programs or packages:
            findings.append(dict(
                key=soft['key'], name=soft['name'], running=running, services=services,
                installed=programs, store=packages,
                active=bool(running or any(r for _, r in services)),
                steps=soft.get('steps', GENERIC_STEPS), help_url=soft.get('help_url')))
    if len(openrgb_pids) > 1 or (shortcuts and openrgb_service is not None):
        findings.append(dict(
            key='openrgb', name='Segunda cópia do OpenRGB', running=['openrgb.exe'] * len(openrgb_pids),
            services=[], installed=[], store=[], active=True, shortcuts=list(shortcuts),
            steps=['O OpenRGB já roda como serviço; a cópia extra (atalho na pasta '
                   'Inicializar) disputa os LEDs.', 'Clique em Parar agora: o atalho vai para '
                   'um backup e a cópia extra é fechada.'], help_url=None))
    return findings


def find_conflicts():
    from winproc import processes, installed_programs, store_apps
    procs = processes()
    names = {n.lower() for n in procs.values()}
    openrgb = [pid for pid, n in procs.items() if n.lower() == 'openrgb.exe']
    return analyse(names, service_state, installed_programs(), store_apps(),
                   openrgb, service_state(OPENRGB_SERVICE), openrgb_shortcuts())


def summary(findings):
    """Texto curto para o aviso fixo."""
    if not findings:
        return ''
    names = ', '.join(f['name'] + (' (ativo)' if f['active'] else ' (instalado)') for f in findings)
    return (f'Programas interferindo nos LEDs: {names}. Para funcionar corretamente, '
            'remova todo e qualquer outro programa de RGB.')


def _ps_quote(text):
    return "'" + str(text).replace("'", "''") + "'"


def stop_script(findings, backup_dir):
    """PowerShell que para tudo o que interfere agora (sem desinstalar)."""
    lines = ["$ErrorActionPreference = 'SilentlyContinue'"]
    for f in findings:
        for name, _ in f['services']:
            lines.append(f'Stop-Service -Name {_ps_quote(name)} -Force')
            lines.append(f'Set-Service -Name {_ps_quote(name)} -StartupType Disabled')
        for proc in sorted(set(f['running'])):
            if proc != 'openrgb.exe':
                lines.append(f'Stop-Process -Name {_ps_quote(proc[:-4])} -Force')
        for path in f.get('shortcuts', []):
            lines.append(f'New-Item -ItemType Directory -Force -Path {_ps_quote(backup_dir)} | Out-Null')
            lines.append(f'Move-Item -LiteralPath {_ps_quote(path)} -Destination {_ps_quote(backup_dir)} -Force')
    # Mantém só o OpenRGB que serve a porta do SDK; fecha cópias extras.
    lines += [f'$server = (Get-NetTCPConnection -LocalPort {SDK_PORT} -State Listen | '
              'Select-Object -First 1).OwningProcess',
              'if ($server) { Get-Process OpenRGB | Where-Object { $_.Id -ne $server } | '
              'Stop-Process -Force }']
    return '\r\n'.join(lines) + '\r\n'


def _run_elevated(file, params):
    """Executa como administrador e espera. False se a pessoa cancelar o UAC."""
    import pywintypes
    import win32con
    import win32event
    from win32com.shell import shell, shellcon
    try:
        info = shell.ShellExecuteEx(fMask=shellcon.SEE_MASK_NOCLOSEPROCESS, lpVerb='runas',
                                    lpFile=file, lpParameters=params, nShow=win32con.SW_HIDE)
    except pywintypes.error as exc:
        if exc.winerror == 1223:
            return False
        raise RuntimeError(f'Não foi possível executar: {exc.strerror}') from None
    win32event.WaitForSingleObject(info['hProcess'], 10 * 60 * 1000)
    time.sleep(1)
    return True


def stop_now(findings, folder):
    folder = Path(folder)
    script = folder / 'parar-programas-rgb.ps1'
    script.write_text(stop_script(findings, folder / 'backup-inicializar'), encoding='utf-8-sig')
    return _run_elevated('powershell.exe',
                         f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{script}"')


def uninstall(command):
    """Roda o desinstalador registrado do programa (com permissão de administrador)."""
    if not command:
        raise RuntimeError('Este programa não informa como desinstalar. Use Configurações → Aplicativos.')
    import win32api
    import win32con
    try:
        win32api.ShellExecute(0, 'runas', os.environ.get('COMSPEC', 'cmd.exe'),
                              f'/c "{command}"', None, win32con.SW_HIDE)
    except Exception as exc:
        if getattr(exc, 'winerror', None) == 1223:
            return False
        raise RuntimeError(f'Não foi possível abrir o desinstalador: {exc}') from None
    return True


def open_apps_settings():
    os.startfile('ms-settings:appsfeatures')

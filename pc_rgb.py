"""LEDs do PC (placa-mãe e memórias) via servidor SDK do OpenRGB.

O SDK Aura do Armoury Crate não enumera dispositivos nas versões atuais,
então a integração usa o OpenRGB, que suporta o controlador Aura USB das
placas ASUS B550 e memórias DDR4 RGB (ex.: ADATA XPG Spectrix).
"""
import copy
import os
import subprocess
import threading
import time
from pathlib import Path

from effects import SPEED_FRACTION, openrgb_modes, uses_colour

HOST = '127.0.0.1'
PORT = 6742
# Tipos do OpenRGB: 0 = placa-mãe (inclui headers ARGB), 1 = memória RAM.
TARGET_TYPES = (0, 1)

OPENRGB_DIRS = [r'D:\Program Files\OpenRGB', r'C:\Program Files\OpenRGB',
                os.path.expandvars(r'%LOCALAPPDATA%\Programs\OpenRGB')]

WARM = (255, 186, 107)
COLD = (205, 228, 255)


def hex_to_rgb(hex_colour):
    return tuple(int(hex_colour[i:i+2], 16) for i in (1, 3, 5))


def white_rgb(temperature):
    """Converte temperatura Tuya (0 quente … 1000 frio) em RGB aproximado."""
    t = max(0, min(1000, temperature)) / 1000
    return tuple(round(a + (b - a) * t) for a, b in zip(WARM, COLD))


def white_hex(temperature):
    return '#%02x%02x%02x' % white_rgb(temperature)


def find_openrgb(extra=None):
    for folder in ([extra] if extra else []) + OPENRGB_DIRS:
        exe = Path(folder)
        exe = exe if exe.suffix.lower() == '.exe' else exe / 'OpenRGB.exe'
        if exe.is_file():
            return str(exe)
    return None


def launch_openrgb(exe):
    """Abre o OpenRGB minimizado na bandeja, já com o servidor SDK ligado."""
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0)
    subprocess.Popen([exe, '--server', '--startminimized'], cwd=str(Path(exe).parent),
                     creationflags=flags, close_fds=True)


def scale(rgb, brightness):
    """Aplica brilho de 0–100% à cor; LEDs de PC não têm canal de brilho."""
    factor = max(0, min(100, brightness)) / 100
    return tuple(round(c * factor) for c in rgb)


class PcLighting:
    """Cliente simples e seguro para várias threads; reconecta quando preciso."""

    def __init__(self, host=HOST, port=PORT, types=TARGET_TYPES, client_factory=None,
                 launcher=None, wait=20):
        self.host, self.port, self.types = host, port, tuple(types)
        self._factory = client_factory
        self._launcher = launcher  # função sem argumentos que abre o OpenRGB
        self._wait = wait
        self._launched = 0
        self._client = None
        self._lock = threading.Lock()
        self._modes = {}

    def _connect(self):
        if self._client is None:
            factory = self._factory
            if factory is None:
                try:
                    from openrgb import OpenRGBClient
                except ImportError:
                    raise RuntimeError('Biblioteca openrgb-python não instalada.') from None
                factory = OpenRGBClient
            self._client = self._open(factory)
            self._modes.clear()
        return self._client

    def _open(self, factory):
        try:
            return factory(self.host, self.port, 'Controle LED')
        except (OSError, ConnectionError, TimeoutError):
            pass
        # Servidor fora do ar: abre o OpenRGB (no máximo uma vez por minuto).
        if self._launcher and time.time() - self._launched > 60:
            self._launched = time.time()
            try:
                self._launcher()
            except OSError:
                pass
            else:
                deadline = time.time() + self._wait
                while time.time() < deadline:
                    time.sleep(1)
                    try:
                        client = factory(self.host, self.port, 'Controle LED')
                    except (OSError, ConnectionError, TimeoutError):
                        continue
                    time.sleep(2)  # dá tempo de detectar memórias e placa
                    client.update()
                    return client
        raise RuntimeError('OpenRGB não está aberto. Abra o OpenRGB e ative o servidor '
                           '(aba Servidor SDK → Iniciar servidor).')

    def _disconnect(self):
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
        self._client = None
        self._modes.clear()

    def _targets(self, client, types=None):
        types = self.types if types is None else tuple(types)
        return [d for d in client.devices if int(d.type) in types]

    def _run(self, action):
        with self._lock:
            for attempt in range(2):
                try:
                    return action(self._connect())
                except RuntimeError:
                    raise
                except Exception as exc:
                    # Conexão caiu (OpenRGB reiniciado etc.): tenta mais uma vez.
                    self._disconnect()
                    if attempt:
                        raise RuntimeError(f'Falha no OpenRGB: {exc}') from None

    def devices(self, types=None):
        """Lista os nomes dos dispositivos que serão controlados."""
        return self._run(lambda c: [d.name for d in self._targets(c, types)])

    def _apply_device(self, device, mode_names, colour, speed):
        mode = pick_mode(device, mode_names) or pick_mode(device, ['Direct', 'Static'])
        if mode is None:
            raise RuntimeError(f'{device.name}: nenhum modo compatível.')
        mode = copy.copy(mode)
        if getattr(mode, 'speed', None) is not None and mode.speed_min is not None:
            fraction = SPEED_FRACTION.get(speed, 0.5)
            mode.speed = round(mode.speed_min + (mode.speed_max - mode.speed_min) * fraction)
        colour_mode = getattr(mode.color_mode, 'name', str(mode.color_mode))
        if colour_mode == 'MODE_SPECIFIC' and colour is not None and mode.colors_max:
            mode.colors = [colour] * mode.colors_max
        key = (mode.id, getattr(mode, 'speed', None))
        # Cor por LED no mesmo modo: só troca a cor (rápido, sem gravar na placa).
        if colour_mode != 'PER_LED' or self._modes.get(device.id) != key or device.active_mode != mode.id:
            device.set_mode(mode)
            self._modes[device.id] = key
        if colour_mode == 'PER_LED' and colour is not None:
            device.set_color(colour, fast=True)

    def set_effect(self, effect, rgb=None, speed='medium', types=None):
        mode_names = openrgb_modes(effect)

        def action(client):
            targets = self._targets(client, types)
            if not targets:
                raise RuntimeError('OpenRGB não encontrou o dispositivo. Para as memórias, '
                                   'abra o OpenRGB como administrador.')
            colour = None if rgb is None else self._colour_class()(*rgb)
            for device in targets:
                self._apply_device(device, mode_names, colour, speed)
            return len(targets)
        return self._run(action)

    def set_rgb(self, rgb, types=None):
        return self.set_effect('static', rgb, types=types)

    def apply_selection(self, sel, types=None):
        """Aplica uma seleção da tela (cor, branco ou efeito) aos dispositivos."""
        level = sel.get('brightness', 100)
        if sel.get('mode') == 'white':
            return self.set_rgb(scale(white_rgb(sel.get('temperature', 500)), level), types)
        rgb = scale(hex_to_rgb(sel.get('colour', '#ffffff')), level)
        if sel.get('mode') == 'effect':
            effect = sel.get('effect', 'static')
            return self.set_effect(effect, rgb if uses_colour(effect) else None,
                                   sel.get('speed', 'medium'), types)
        return self.set_rgb(rgb, types)

    def apply(self, hex_colour, brightness, types=None):
        return self.set_rgb(scale(hex_to_rgb(hex_colour), brightness), types)

    def apply_white(self, temperature, brightness, types=None):
        return self.set_rgb(scale(white_rgb(temperature), brightness), types)

    def off(self, types=None):
        return self.set_rgb((0, 0, 0), types)

    def close(self):
        with self._lock:
            self._disconnect()

    def _colour_class(self):
        if self._factory is not None:
            return lambda r, g, b: (r, g, b)
        from openrgb.utils import RGBColor
        return RGBColor


def pick_mode(device, names):
    modes = getattr(device, 'modes', None) or []
    for name in names:
        for mode in modes:
            if mode.name.lower() == name.lower():
                return mode
    return None

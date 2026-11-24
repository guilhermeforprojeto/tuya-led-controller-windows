"""LEDs do PC (placa-mãe e memórias) via servidor SDK do OpenRGB.

O SDK Aura do Armoury Crate não enumera dispositivos nas versões atuais,
então a integração usa o OpenRGB, que suporta o controlador Aura USB das
placas ASUS B550 e memórias DDR4 RGB (ex.: ADATA XPG Spectrix).
"""
import copy
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from effects import SPEED_FRACTION, openrgb_modes, uses_colour
from fx import LEDS_PER_STICK, frame, is_animated, led_hex, led_rgb

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
        self._lock = threading.RLock()  # o animador consulta dispositivos dentro de _run
        self._modes = {}
        self.ram = RamAnimator(self)

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

    def apply_selection(self, sel, types=None, sticks=None):
        """Aplica uma seleção da tela (cor, branco ou efeito) aos dispositivos.
        Memórias (tipo 1) vão para o animador; sticks = posições 1–4 (None = todos)."""
        types = self.types if types is None else tuple(types)
        result = 0
        if 1 in types:
            addresses = self.ram.resolve(sticks)
            if not addresses:
                raise RuntimeError('OpenRGB não encontrou as memórias. Abra o OpenRGB como administrador.')
            self.ram.set(sel, addresses)
            result += len(addresses)
        rest = tuple(t for t in types if t != 1)
        if rest:
            result += self._apply_hardware(sel, rest)
        return result

    def ram_power(self, on, sticks=None, fallback=None):
        addresses = self.ram.resolve(sticks)
        if not addresses:
            raise RuntimeError('OpenRGB não encontrou as memórias. Abra o OpenRGB como administrador.')
        self.ram.power(on, addresses, fallback)
        return len(addresses)

    def _apply_hardware(self, sel, types):
        level = sel.get('brightness', 100)
        if sel.get('mode') == 'white':
            return self.set_rgb(scale(white_rgb(sel.get('temperature', 500)), level), types)
        rgb = scale(hex_to_rgb(led_hex(sel)), level)
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
        types = self.types if types is None else tuple(types)
        result = 0
        if 1 in types:
            addresses = self.ram.resolve(None)
            self.ram.power(False, addresses)
            # Desligamento do PC: grava já, sem esperar o próximo quadro.
            self.ram._send(time.time())
            result += len(addresses)
        rest = tuple(t for t in types if t != 1)
        if rest:
            result += self.set_rgb((0, 0, 0), rest)
        return result

    def close(self):
        self.ram.stop()
        with self._lock:
            self._disconnect()

    def _colour_class(self):
        if self._factory is not None:
            return lambda r, g, b: (r, g, b)
        from openrgb.utils import RGBColor
        return RGBColor


def stick_address(device):
    """Endereço do pente no barramento (ex.: '0x70'), estável entre reinícios."""
    location = getattr(getattr(device, 'metadata', None), 'location', '') or ''
    match = re.search(r'0x[0-9a-fA-F]+', location)
    return match.group(0).lower() if match else location or str(getattr(device, 'id', ''))


def stick_colours(sticks, ordered, t, led=False):
    """{endereço: [rgb × 5]}: pentes com a mesma seleção (grupo) animam juntos,
    na ordem de `ordered`. sticks: endereço → {'sel', 'on', 'group'}.
    led=True: cores ajustadas para o LED (a prévia usa as da tela)."""
    out, groups = {}, {}
    for a in ordered:
        st = sticks.get(a)
        if st is None:
            continue
        if not st['on']:
            out[a] = [(0, 0, 0)] * LEDS_PER_STICK
        else:
            groups.setdefault(st['group'], []).append(a)
    for members in groups.values():
        sel = sticks[members[0]]['sel']
        rows = frame(sel, t, sticks=len(members))
        for a, row in zip(members, rows):
            out[a] = [led_rgb(sel, rgb) for rgb in row] if led else row
    return out


class RamAnimator:
    """Controla cada pente de memória separadamente, em modo Direct.

    Cada pente recebe uma seleção (cor, branco ou efeito) ou fica desligado.
    Pentes com a mesma seleção formam um grupo, e o efeito do grupo percorre
    os pentes na ordem escolhida (1 → 4), num relógio único: fica sincronizado.
    """
    FPS = 30

    def __init__(self, pc):
        self.pc = pc
        self.order = []          # endereços na ordem da pessoa (posição 1, 2, 3, 4)
        self.sticks = {}         # endereço → {'sel': {...}, 'on': bool, 'group': int}
        self._group = 0
        self._flash = {}         # endereço → instante em que termina o "piscar"
        self._dirty = True
        self._cond = threading.Condition()
        self._stop = False
        self._error_until = 0
        self._thread = None

    # ---- estado
    def addresses(self):
        """Endereços detectados, na ordem escolhida (os novos vão para o fim)."""
        found = self.pc._run(lambda c: [stick_address(d) for d in self.pc._targets(c, (1,))])
        return self.order_known(found)

    def resolve(self, positions):
        """Posições 1–4 → endereços; None = todos."""
        ordered = self.addresses()
        if positions is None:
            return ordered
        return [ordered[p - 1] for p in sorted(set(positions)) if 0 < p <= len(ordered)]

    def set(self, sel, addresses):
        with self._cond:
            self._group += 1
            for a in addresses:
                self.sticks[a] = {'sel': dict(sel), 'on': True, 'group': self._group}
            self._touch()

    def power(self, on, addresses, fallback=None):
        with self._cond:
            for a in addresses:
                st = self.sticks.get(a)
                if st is None:
                    if not on or fallback is None:
                        self.sticks[a] = {'sel': dict(fallback or {}), 'on': on, 'group': 0}
                        continue
                    self._group += 1
                    st = self.sticks[a] = {'sel': dict(fallback), 'on': True, 'group': self._group}
                st['on'] = on
            self._touch()

    solo = None  # calibração: só este pente aceso (branco), os outros apagados

    def set_solo(self, address, fallback=None):
        """Acende só um pente. Ao terminar (None), pentes que o app ainda não
        controlava recebem a seleção `fallback` em vez de ficarem apagados."""
        with self._cond:
            if address is None and fallback is not None:
                missing = [a for a in self.known if a not in self.sticks]
                if missing:
                    self._group += 1
                    for a in missing:
                        self.sticks[a] = {'sel': dict(fallback), 'on': True, 'group': self._group}
            self.solo = address
            self._touch()

    def position_states(self):
        """[ligado?] por posição 1–N, na ordem escolhida."""
        with self._cond:
            return [self.sticks.get(a, {'on': True})['on'] for a in self.known]

    def identify(self, address, seconds=2.0):
        with self._cond:
            self._flash[address] = time.time() + seconds
            self._touch()

    def snapshot(self):
        with self._cond:
            return {a: {'sel': dict(s['sel']), 'on': s['on'], 'group': s['group']}
                    for a, s in self.sticks.items()}

    def restore(self, data):
        with self._cond:
            self.sticks = {a: {'sel': dict(s.get('sel') or {}), 'on': bool(s.get('on', True)),
                               'group': int(s.get('group', 0))} for a, s in (data or {}).items()}
            self._group = max([s['group'] for s in self.sticks.values()] + [0])
            self._touch()

    autostart = True  # testes desligam o laço e chamam _send direto

    def _touch(self):
        self._dirty = True
        self._cond.notify_all()
        if self.autostart and (self._thread is None or not self._thread.is_alive()):
            self._stop = False
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self):
        with self._cond:
            self._stop = True
            self._cond.notify_all()

    # ---- cálculo (puro, testável)
    def colours(self, t, ordered):
        """{endereço: [rgb × 5]} para o instante t."""
        if self.solo is not None:
            return {a: [(255, 255, 255) if a == self.solo else (0, 0, 0)] * LEDS_PER_STICK
                    for a in ordered}
        out = stick_colours(self.sticks, ordered, t, led=True)
        for a, until in list(self._flash.items()):
            if until > t:
                on = int((until - t) * 6) % 2 == 0
                out[a] = [(255, 255, 255) if on else (0, 0, 0)] * LEDS_PER_STICK
            else:
                del self._flash[a]
                self._dirty = True  # volta ao estado normal do pente
        return out

    def _animated(self, now):
        if self.solo is not None:
            return False
        if any(until > now for until in self._flash.values()):
            return True
        return any(s['on'] and is_animated(s['sel']) for s in self.sticks.values())

    # ---- laço
    def _loop(self):
        while True:
            with self._cond:
                if self._stop:
                    return
                now = time.time()
                if not self._dirty and not self._animated(now):
                    self._cond.wait(1.0)
                    continue
                self._dirty = False
            if time.time() < self._error_until:
                time.sleep(0.5)
                continue
            try:
                self._send(time.time())
            except Exception:
                self._error_until = time.time() + 3  # OpenRGB fora: tenta de novo depois
                self._dirty = True
            time.sleep(1 / self.FPS)

    def _send(self, t):
        colour_cls = self.pc._colour_class()

        def action(client):
            devices = {stick_address(d): d for d in self.pc._targets(client, (1,))}
            ordered = self.order_known(list(devices))
            with self._cond:
                frame_colours = self.colours(t, ordered)
            for a, rgbs in frame_colours.items():
                d = devices.get(a)
                if d is None:
                    continue
                if self.pc._modes.get(d.id) != 'direct-sw':
                    direct = pick_mode(d, ['Direct'])
                    if direct is None:
                        continue
                    d.set_mode(direct)
                    self.pc._modes[d.id] = 'direct-sw'
                d.set_colors([colour_cls(*(round(c) for c in rgb)) for rgb in rgbs], fast=True)
        self.pc._run(action)

    def order_known(self, found):
        known = [a for a in self.order if a in found]
        self.known = known + sorted(a for a in found if a not in known)
        return list(self.known)

    known = []  # últimos endereços vistos, na ordem escolhida


def pick_mode(device, names):
    modes = getattr(device, 'modes', None) or []
    for name in names:
        for mode in modes:
            if mode.name.lower() == name.lower():
                return mode
    return None

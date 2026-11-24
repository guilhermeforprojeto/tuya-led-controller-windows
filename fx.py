"""Motor de efeitos por software: a cor de cada LED num instante t.

Um único relógio para tudo: as memórias (vários pentes em ordem), a prévia da
janela e o ícone da bandeja usam a mesma função, então mostram o mesmo efeito
no mesmo ritmo. Os efeitos andam na ordem dos pentes (1 → 2 → 3 → 4).
"""
import colorsys
import math

LEDS_PER_STICK = 5
WARM = (255, 186, 107)
COLD = (205, 228, 255)

# Duração de um ciclo, em segundos, por velocidade.
PERIOD = {'slow': 4.0, 'medium': 2.4, 'fast': 1.2}
ANIMATED = {'breathing', 'flashing', 'rainbow', 'cycle', 'chase', 'flicker'}


def hex_to_rgb(hex_colour):
    return tuple(int(hex_colour[i:i+2], 16) for i in (1, 3, 5))


def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % tuple(max(0, min(255, round(c))) for c in rgb)


def _scale(rgb, k):
    return tuple(c * k for c in rgb)


def _hue(h):
    return tuple(c * 255 for c in colorsys.hsv_to_rgb(h % 1, 1, 1))


def _noise(i, step):
    """Pseudoaleatório estável (mesmo valor para o mesmo LED e passo)."""
    x = math.sin(i * 12.9898 + step * 78.233) * 43758.5453
    return x - math.floor(x)


def base_colour(sel):
    if sel.get('mode') == 'white':
        t = max(0, min(1000, sel.get('temperature', 500))) / 1000
        return tuple(a + (b - a) * t for a, b in zip(WARM, COLD))
    return hex_to_rgb(sel.get('colour', '#ffffff'))


def effect_of(sel):
    return sel.get('effect', 'static') if sel.get('mode') == 'effect' else 'static'


def is_animated(sel):
    return effect_of(sel) in ANIMATED


def frame(sel, t, sticks=1, leds=LEDS_PER_STICK):
    """Cores RGB (0–255) de cada LED: lista [pente][led], pentes na ordem."""
    level = max(0, min(100, sel.get('brightness', 100))) / 100
    colour = base_colour(sel)
    effect = effect_of(sel)
    period = PERIOD.get(sel.get('speed', 'medium'), 2.4)
    phase = (t / period) % 1
    out = []
    for s in range(sticks):
        row = []
        for led in range(leds):
            # Posição ao longo do conjunto: pente inteiro + um pouco pelo LED.
            x = (s + led / max(1, leds) * 0.6) / max(1, sticks)
            if effect == 'breathing':
                k = 0.08 + 0.92 * (0.5 - 0.5 * math.cos(2 * math.pi * phase))
                rgb = _scale(colour, k)
            elif effect == 'flashing':
                rgb = colour if phase < 0.5 else (0, 0, 0)
            elif effect == 'rainbow':
                rgb = _hue(x - phase)
            elif effect == 'cycle':
                rgb = _hue(phase)
            elif effect == 'chase':
                # Um cometa que percorre os pentes em ordem, com rastro.
                head = phase * (sticks + 1) - 0.5
                d = head - s
                k = 1.0 if -0.5 <= d <= 0.5 else max(0.0, 1 - (d - 0.5) / 1.2) if d > 0.5 else 0.0
                rgb = _scale(colour, 0.06 + 0.94 * k)
            elif effect == 'flicker':
                step = math.floor(t / period * 6)
                rgb = _hue(_noise(s * leds + led, step)) if _noise(s * leds + led, step + 0.5) > 0.35 \
                    else (0, 0, 0)
            else:
                rgb = colour
            row.append(_scale(rgb, level))
        out.append(row)
    return out


def single(sel, t):
    """Cor de um LED só (prévia e ícone), no mesmo relógio dos pentes."""
    return frame(sel, t, 1, 1)[0][0]

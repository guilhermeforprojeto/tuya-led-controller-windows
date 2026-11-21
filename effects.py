"""Efeitos predefinidos: cenas Tuya (scene_data_v2) e modos de hardware do OpenRGB."""
import colorsys

# chave, nome na tela, usa a cor escolhida, modos OpenRGB em ordem de preferência
EFFECTS = [
    ('static', 'Estático', True, ['Direct', 'Static']),
    ('breathing', 'Respirar', True, ['Breathing']),
    ('flashing', 'Piscar', True, ['Flashing']),
    ('rainbow', 'Arco-íris', False, ['Rainbow', 'Spectrum Cycle']),
    ('cycle', 'Ciclo de cores', False, ['Spectrum Cycle', 'Rainbow']),
    ('chase', 'Perseguição', True, ['Chase Fade', 'Chase']),
    ('flicker', 'Cintilar', False, ['Random Flicker', 'Flashing']),
]
BY_KEY = {e[0]: e for e in EFFECTS}

SPEEDS = [('slow', 'Lenta'), ('medium', 'Média'), ('fast', 'Rápida')]
# Fração de 0 (lento) a 1 (rápido), usada nos dois sistemas.
SPEED_FRACTION = {'slow': 0.0, 'medium': 0.5, 'fast': 1.0}

RAINBOW_HUES = [0, 30, 60, 120, 180, 240, 280, 320]
FLICKER_HUES = [200, 20, 300, 90, 0, 260, 160, 45]


def uses_colour(effect):
    return BY_KEY.get(effect, BY_KEY['static'])[2]


def openrgb_modes(effect):
    return BY_KEY.get(effect, BY_KEY['static'])[3]


def hex_to_hs(hex_colour):
    rgb = tuple(int(hex_colour[i:i+2], 16) / 255 for i in (1, 3, 5))
    h, s, _ = colorsys.rgb_to_hsv(*rgb)
    return round(h * 360), round(s * 1000)


def _durations(speed, factor=1.0):
    """Tuya: 0–100, menor = mais rápido."""
    fraction = SPEED_FRACTION.get(speed, 0.5)
    value = round((85 - 70 * fraction) * factor)
    return max(1, min(100, value))


def _unit(mode, duration, h, s, v):
    return {'unit_change_mode': mode, 'unit_switch_duration': duration,
            'unit_gradient_duration': duration, 'h': h, 's': s, 'v': v,
            'bright': 0, 'temperature': 0}


def tuya_scene(effect, hex_colour, brightness, speed):
    """Monta o valor de scene_data_v2 para a fita (efeitos não estáticos)."""
    v = max(10, min(1000, round(brightness * 10)))
    h, s = hex_to_hs(hex_colour)
    d = _durations(speed)
    if effect == 'breathing':
        units = [_unit('gradient', d, h, s, v), _unit('gradient', d, h, s, 10)]
    elif effect == 'flashing':
        fast = max(1, d // 3)
        units = [_unit('jump', fast, h, s, v), _unit('jump', fast, h, s, 0)]
    elif effect == 'rainbow':
        units = [_unit('jump', d, hue, 1000, v) for hue in RAINBOW_HUES]
    elif effect == 'cycle':
        slow = _durations(speed, 1.15)
        units = [_unit('gradient', slow, hue, 1000, v) for hue in RAINBOW_HUES]
    elif effect == 'chase':
        other = (h + 180) % 360
        units = [_unit('gradient', d, h, s, v), _unit('gradient', d, other, s, v)]
    elif effect == 'flicker':
        fast = max(1, d // 4)
        units = [_unit('jump', fast, hue, 1000, v) for hue in FLICKER_HUES]
    else:
        raise ValueError(f'Efeito desconhecido: {effect}')
    number = [e[0] for e in EFFECTS].index(effect) + 1  # 1–8
    # A Tuya exige objeto JSON aqui (texto dá "1104: type is incorrect").
    return {'scene_num': number, 'scene_units': units}

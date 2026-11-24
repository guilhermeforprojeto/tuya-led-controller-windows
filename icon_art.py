"""Ícone do Controle LED: azulejo escuro com um LED brilhando na cor atual."""
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from shapes import squircle_points

TILE = '#151a26'
TILE_EDGE = '#2a3346'
RAINBOW = ['#ff3b3b', '#ff9a2e', '#ffe14a', '#3fe07a', '#36b4ff', '#8a5cff', '#ff4fc3']
SUPER = 4  # desenha maior e reduz, para bordas suaves


def _rgb(hex_colour):
    return tuple(int(hex_colour[i:i+2], 16) for i in (1, 3, 5))


def draw_icon(colour='#a020f0', size=64, rainbow=False, on=True):
    s = size * SUPER
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    m = s * 0.04
    tile = squircle_points(m, m, s - m, s - m, s * 0.22, steps=16)
    ImageDraw.Draw(img).polygon(tile, fill=TILE, outline=TILE_EDGE, width=max(1, s // 64))

    c = s / 2
    r = s * 0.24
    glow = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    if not on:
        core = (88, 96, 112)
        gd.ellipse((c - r, c - r, c + r, c + r), fill=core + (255,))
    elif rainbow:
        ring = r * 1.55
        step = 360 / len(RAINBOW)
        for i, hue in enumerate(RAINBOW):
            gd.pieslice((c - ring, c - ring, c + ring, c + ring), i * step - 90,
                        (i + 1) * step - 90, fill=_rgb(hue) + (255,))
        glow = glow.filter(ImageFilter.GaussianBlur(s * 0.06))
        gd = ImageDraw.Draw(glow)
        gd.ellipse((c - r, c - r, c + r, c + r), fill=(255, 255, 255, 255))
    else:
        core = _rgb(colour)
        halo = r * 1.9
        gd.ellipse((c - halo, c - halo, c + halo, c + halo), fill=core + (150,))
        glow = glow.filter(ImageFilter.GaussianBlur(s * 0.07))
        gd = ImageDraw.Draw(glow)
        gd.ellipse((c - r, c - r, c + r, c + r), fill=core + (255,))

    # O brilho fica só dentro do azulejo.
    mask = Image.new('L', (s, s), 0)
    ImageDraw.Draw(mask).polygon(tile, fill=255)
    glow.putalpha(ImageChops.multiply(glow.getchannel('A'), mask))
    img = Image.alpha_composite(img, glow)

    if on:  # reflexo de luz no LED
        shine = Image.new('RGBA', (s, s), (0, 0, 0, 0))
        hr = r * 0.42
        hx, hy = c - r * 0.32, c - r * 0.36
        ImageDraw.Draw(shine).ellipse((hx - hr, hy - hr * 0.7, hx + hr, hy + hr * 0.7),
                                      fill=(255, 255, 255, 120))
        img = Image.alpha_composite(img, shine.filter(ImageFilter.GaussianBlur(s * 0.012)))
    return img.resize((size, size), Image.LANCZOS)


def icon_for(sel, on=True):
    """Escolhe o desenho conforme a seleção (cor, branco ou efeito)."""
    from effects import uses_colour
    from pc_rgb import white_hex
    if sel.get('mode') == 'white':
        return dict(colour=white_hex(sel.get('temperature', 500)), on=on)
    if sel.get('mode') == 'effect' and not uses_colour(sel.get('effect', 'static')):
        return dict(rainbow=True, on=on)
    return dict(colour=sel.get('colour', '#a020f0'), on=on)


def save_ico(path, colour='#a020f0'):
    sizes = [16, 24, 32, 48, 64, 128, 256]
    draw_icon(colour, 256).save(path, sizes=[(n, n) for n in sizes])

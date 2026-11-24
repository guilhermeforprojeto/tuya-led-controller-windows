"""Interface Tkinter do Controle LED.

Cantos contínuos (squircle) desenhados no Canvas e raios concêntricos:
o raio de um elemento interno é o raio do externo menos o espaço entre eles.
"""
import tkinter as tk
import webbrowser
from tkinter import ttk

from shapes import concentric, squircle_points

# Cores
BG = '#0d111a'
SURFACE = '#161c29'
SURFACE_2 = '#202839'
SURFACE_3 = '#2c3549'
LINE = '#2a3346'
TEXT = '#f2f4fa'
MUTED = '#9aa4ba'
ACCENT = '#c6a0ff'
ACCENT_HOVER = '#d6bbff'
ACCENT_TEXT = '#1a1030'
WARN = '#ffbf5e'
WARN_BG = '#2a2115'

# Raios: padroniza os de fora e calcula os de dentro.
CARD_R, CARD_PAD = 20, 14
CHIP_R = concentric(CARD_R, CARD_PAD)          # 6
SEG_R, SEG_PAD = 14, 4
SEG_ITEM_R = concentric(SEG_R, SEG_PAD)        # 10
BTN_R = 12
BANNER_R, BANNER_PAD = 18, 10
BANNER_BTN_R = concentric(BANNER_R, BANNER_PAD)  # 8

FONT = 'Segoe UI'


def mix(a, b, t):
    """Mistura duas cores #rrggbb (t=0 → a, t=1 → b)."""
    ca = [int(a[i:i+2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i+2], 16) for i in (1, 3, 5)]
    return '#%02x%02x%02x' % tuple(round(x + (y - x) * t) for x, y in zip(ca, cb))


def white_preview(temperature):
    t = temperature / 1000
    return '#%02x%02x%02x' % tuple(round(a+(b-a)*t) for a, b in zip((255, 186, 107), (205, 228, 255)))


class _Canvas(tk.Canvas):
    def __init__(self, parent, **kwargs):
        kwargs.setdefault('bg', parent.cget('bg'))
        super().__init__(parent, highlightthickness=0, bd=0, **kwargs)

    def has_focus(self):
        try:
            return self.focus_get() is self
        except (KeyError, tk.TclError):  # foco num menu suspenso
            return False

    def shape(self, x0, y0, x1, y1, radius, **kwargs):
        kwargs.setdefault('outline', '')
        return self.create_polygon(squircle_points(x0, y0, x1, y1, radius), **kwargs)


class RoundBox(_Canvas):
    """Card com canto contínuo; o conteúdo vai em .body."""
    def __init__(self, parent, radius=CARD_R, pad=CARD_PAD, fill=SURFACE, outline=''):
        super().__init__(parent, height=2 * pad)
        self.radius, self.pad, self.fill, self.outline = radius, pad, fill, outline
        self.body = tk.Frame(self, bg=fill)
        self._win = self.create_window(pad, pad, window=self.body, anchor='nw')
        self.body.bind('<Configure>', self._fit, add='+')
        self.bind('<Configure>', self._fit, add='+')

    def _fit(self, _=None):
        w = max(2 * self.pad + 2, self.winfo_width())
        self.itemconfigure(self._win, width=w - 2 * self.pad)
        h = self.body.winfo_reqheight() + 2 * self.pad
        if int(float(self.cget('height'))) != h:
            self.configure(height=h)
        self.delete('shape')
        self.shape(0, 0, w - 1, h - 1, self.radius, fill=self.fill,
                   outline=self.outline, tags='shape')
        self.tag_lower('shape')


class PillButton(_Canvas):
    def __init__(self, parent, text, command, radius=BTN_R, height=40, fill=SURFACE_2,
                 hover=SURFACE_3, fg=TEXT, font=(FONT, 10, 'bold')):
        # largura mínima: quem define o tamanho é o pack/grid (botões lado a lado iguais)
        super().__init__(parent, height=height, width=10, cursor='hand2', takefocus=True)
        self.text, self.command, self.radius = text, command, radius
        self.colours = {'fill': fill, 'hover': hover, 'fg': fg}
        self.font, self._hover, self._focus = font, False, False
        for seq, fn in [('<Configure>', lambda _: self.redraw()),
                        ('<Enter>', lambda _: self._set('_hover', True)),
                        ('<Leave>', lambda _: self._set('_hover', False)),
                        ('<FocusIn>', lambda _: self._set('_focus', True)),
                        ('<FocusOut>', lambda _: self._set('_focus', False)),
                        ('<ButtonRelease-1>', self._click),
                        ('<Return>', lambda _: self.command()),
                        ('<space>', lambda _: self.command())]:
            self.bind(seq, fn)

    def _set(self, name, value):
        setattr(self, name, value)
        self.redraw()

    def _click(self, event):
        if 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            self.command()

    def set_text(self, text):
        self.text = text
        self.redraw()

    def redraw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        fill = self.colours['hover' if self._hover else 'fill']
        self.shape(0, 0, w - 1, h - 1, self.radius, fill=fill,
                   outline=ACCENT if self._focus else '', width=2)
        self.create_text(w / 2, h / 2, text=self.text, fill=self.colours['fg'], font=self.font)


class Segmented(_Canvas):
    """Abas em pílula: o item escolhido fica concêntrico ao contêiner."""
    def __init__(self, parent, variable, options, height=42, font_size=10):
        super().__init__(parent, height=height, cursor='hand2', takefocus=True)
        self.variable, self.options = variable, list(options)
        self.visible = [k for k, _ in self.options]
        self.font_size, self._hover = font_size, None
        self.bind('<Configure>', lambda _: self.redraw())
        self.bind('<Button-1>', self._click)
        self.bind('<Motion>', self._motion)
        self.bind('<Leave>', lambda _: self._motion(None))
        self.bind('<Left>', lambda _: self._step(-1))
        self.bind('<Right>', lambda _: self._step(1))
        self.bind('<FocusIn>', lambda _: self.redraw())
        self.bind('<FocusOut>', lambda _: self.redraw())
        self._trace = variable.trace_add('write', lambda *_: self.redraw())
        self.bind('<Destroy>', lambda e: e.widget is self and variable.trace_remove('write', self._trace))

    def set_visible(self, keys):
        self.visible = [k for k, _ in self.options if k in keys]
        self.redraw()

    def _index_at(self, x):
        n = len(self.visible)
        span = (self.winfo_width() - 2 * SEG_PAD) / max(1, n)
        return max(0, min(n - 1, int((x - SEG_PAD) // span)))

    def _click(self, event):
        self.focus_set()
        self.variable.set(self.visible[self._index_at(event.x)])

    def _motion(self, event):
        hover = None if event is None else self._index_at(event.x)
        if hover != self._hover:
            self._hover = hover
            self.redraw()

    def _step(self, amount):
        if self.variable.get() in self.visible:
            i = self.visible.index(self.variable.get())
            self.variable.set(self.visible[max(0, min(len(self.visible) - 1, i + amount))])

    def redraw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        focused = self.has_focus()
        self.shape(0, 0, w - 1, h - 1, SEG_R, fill=SURFACE_2,
                   outline=ACCENT if focused else '', width=2)
        labels = dict(self.options)
        n = len(self.visible)
        span = (w - 2 * SEG_PAD) / max(1, n)
        for i, key in enumerate(self.visible):
            x0 = SEG_PAD + i * span
            selected = key == self.variable.get()
            if selected or i == self._hover:
                self.shape(x0, SEG_PAD, x0 + span, h - SEG_PAD, SEG_ITEM_R,
                           fill=SURFACE_3 if selected else mix(SURFACE_2, SURFACE_3, 0.45))
            self.create_text(x0 + span / 2, h / 2, text=labels[key],
                             fill=TEXT if selected else MUTED,
                             font=(FONT, self.font_size, 'bold' if selected else 'normal'))


class ChipGrid(_Canvas):
    """Grade de opções (efeitos) dentro de um card: raio concêntrico ao card."""
    def __init__(self, parent, variable, options, columns=4, chip_h=34, gap=6):
        self.rows = -(-len(options) // columns)
        super().__init__(parent, height=self.rows * chip_h + (self.rows - 1) * gap, cursor='hand2')
        self.variable, self.options = variable, list(options)
        self.columns, self.chip_h, self.gap = columns, chip_h, gap
        self.bind('<Configure>', lambda _: self.redraw())
        self.bind('<Button-1>', self._click)
        self._trace = variable.trace_add('write', lambda *_: self.redraw())
        self.bind('<Destroy>', lambda e: e.widget is self and variable.trace_remove('write', self._trace))

    def _cell(self, index):
        w = (self.winfo_width() - (self.columns - 1) * self.gap) / self.columns
        r, c = divmod(index, self.columns)
        x0, y0 = c * (w + self.gap), r * (self.chip_h + self.gap)
        return x0, y0, x0 + w, y0 + self.chip_h

    def _click(self, event):
        for i, (key, _) in enumerate(self.options):
            x0, y0, x1, y1 = self._cell(i)
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                self.variable.set(key)

    def redraw(self):
        self.delete('all')
        for i, (key, text) in enumerate(self.options):
            x0, y0, x1, y1 = self._cell(i)
            selected = key == self.variable.get()
            self.shape(x0, y0, x1, y1, CHIP_R,
                       fill=mix(SURFACE, ACCENT, 0.22) if selected else SURFACE_2,
                       outline=ACCENT if selected else '', width=1)
            self.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=text,
                             fill=TEXT if selected else MUTED, font=(FONT, 9))


class Swatches(_Canvas):
    """Paleta em círculos; o anel marca a cor atual. O último abre o seletor."""
    SIZE, GAP = 28, 10

    def __init__(self, parent, variable, colours, pick):
        super().__init__(parent, height=self.SIZE + 8, cursor='hand2')
        self.variable, self.colours, self.pick = variable, colours, pick
        self.bind('<Configure>', lambda _: self.redraw())
        self.bind('<Button-1>', self._click)
        self._trace = variable.trace_add('write', lambda *_: self.redraw())
        self.bind('<Destroy>', lambda e: e.widget is self and variable.trace_remove('write', self._trace))

    def _centre(self, i):
        return 4 + self.SIZE / 2 + i * (self.SIZE + self.GAP), 4 + self.SIZE / 2

    def _click(self, event):
        for i in range(len(self.colours) + 1):
            x, y = self._centre(i)
            if abs(event.x - x) <= self.SIZE / 2 + 3 and abs(event.y - y) <= self.SIZE / 2 + 3:
                if i == len(self.colours):
                    self.pick()
                else:
                    self.variable.set(self.colours[i])

    def redraw(self):
        self.delete('all')
        r = self.SIZE / 2
        current = self.variable.get().lower()
        for i, colour in enumerate(self.colours):
            x, y = self._centre(i)
            if colour.lower() == current:
                self.create_oval(x - r - 3, y - r - 3, x + r + 3, y + r + 3, outline=TEXT, width=2)
            self.create_oval(x - r + 1, y - r + 1, x + r - 1, y + r - 1, fill=colour, outline='')
        x, y = self._centre(len(self.colours))
        custom = current not in [c.lower() for c in self.colours]
        self.create_oval(x - r + 1, y - r + 1, x + r - 1, y + r - 1,
                         fill=self.variable.get() if custom else SURFACE_2,
                         outline=TEXT if custom else MUTED, width=2 if custom else 1,
                         dash=() if custom else (3, 3))
        self.create_text(x, y - 1, text='+', fill=TEXT, font=(FONT, 13, 'bold'))


class Slider(_Canvas):
    """Barra com puxador, clique, arraste, roda do mouse e setas."""
    def __init__(self, parent, variable, lo, hi, gradient=None, step=1):
        super().__init__(parent, height=30, cursor='hand2', takefocus=True)
        self.variable, self.lo, self.hi, self.gradient, self.unit = variable, lo, hi, gradient, step
        self.bind('<Configure>', lambda _: self.redraw())
        self.bind('<Button-1>', self.select)
        self.bind('<B1-Motion>', self.select)
        self.bind('<MouseWheel>', lambda e: self.step(1 if e.delta > 0 else -1))
        for key, amount in [('Left', -1), ('Right', 1), ('Down', -1), ('Up', 1)]:
            self.bind('<' + key + '>', lambda _e, n=amount: self.step(n))
        self.bind('<FocusIn>', lambda _: self.redraw())
        self.bind('<FocusOut>', lambda _: self.redraw())
        self._trace = variable.trace_add('write', lambda *_: self.redraw())
        self.bind('<Destroy>', lambda e: e.widget is self and variable.trace_remove('write', self._trace))

    def set_value(self, value):
        self.variable.set(max(self.lo, min(self.hi, round(value))))
        return 'break'

    def step(self, amount):
        return self.set_value(self.variable.get() + amount * self.unit)

    def select(self, event):
        self.focus_set()
        span = max(1, self.winfo_width() - 28)
        self.set_value(self.lo + (self.hi - self.lo) * (event.x - 14) / span)

    def redraw(self):
        self.delete('all')
        w = max(30, self.winfo_width())
        y = 15
        frac = (max(self.lo, min(self.hi, self.variable.get())) - self.lo) / (self.hi - self.lo)
        x = 14 + (w - 28) * frac
        if self.gradient:
            a, b = self.gradient
            pieces = 40
            for i in range(pieces):
                xa = 14 + (w - 28) * i / pieces
                xb = 14 + (w - 28) * (i + 1) / pieces
                self.create_line(xa, y, xb, y, width=8, fill=mix(a, b, i / (pieces - 1)),
                                 capstyle='round' if i in (0, pieces - 1) else 'butt')
        else:
            self.create_line(14, y, w - 14, y, fill=SURFACE_3, width=8, capstyle='round')
            self.create_line(14, y, x, y, fill=ACCENT, width=8, capstyle='round')
        ring = ACCENT if self.has_focus() else SURFACE
        self.create_oval(x - 12, y - 12, x + 12, y + 12, fill=ring, outline='')
        self.create_oval(x - 9, y - 9, x + 9, y + 9, fill='#ffffff', outline='')


class Switch(_Canvas):
    """Interruptor ligado/desligado com rótulo clicável."""
    def __init__(self, parent, variable, text):
        super().__init__(parent, height=26, cursor='hand2', takefocus=True)
        self.variable, self.text = variable, text
        self.bind('<Configure>', lambda _: self.redraw())
        for seq in ('<Button-1>', '<space>', '<Return>'):
            self.bind(seq, lambda _: self.variable.set(not self.variable.get()))
        self._trace = variable.trace_add('write', lambda *_: self.redraw())
        self.bind('<Destroy>', lambda e: e.widget is self and variable.trace_remove('write', self._trace))

    def redraw(self):
        self.delete('all')
        on = bool(self.variable.get())
        # Trilho em pílula; puxador concêntrico (pílula dentro de pílula).
        self.create_line(13, 13, 31, 13, width=22, capstyle='round',
                         fill=ACCENT if on else SURFACE_3)
        x = 31 if on else 13
        self.create_oval(x - 8, 5, x + 8, 21, fill='#ffffff' if on else MUTED, outline='')
        self.create_text(54, 13, anchor='w', text=self.text, fill=TEXT if on else MUTED,
                         font=(FONT, 9))


def setup_theme(root):
    root.configure(bg=BG)
    root.minsize(480, 0)  # a altura acompanha o conteúdo de cada modo
    root.resizable(True, True)
    root.option_add('*Font', (FONT, 10))
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', background=BG, foreground=TEXT)
    style.configure('TFrame', background=BG)
    style.configure('TLabel', background=BG, foreground=TEXT)
    style.configure('TButton', background=SURFACE_2, foreground=TEXT, padding=9, borderwidth=0)
    style.map('TButton', background=[('active', SURFACE_3)])
    style.configure('TCheckbutton', background=BG, foreground=TEXT)
    style.map('TCheckbutton', background=[('active', BG)])
    style.configure('TEntry', fieldbackground=SURFACE_2, foreground=TEXT, insertcolor=TEXT)
    style.configure('TSeparator', background=LINE)


TARGETS = [('all', 'Geral'), ('strip', 'Fita'), ('board', 'Placa-mãe'), ('ram', 'Memórias')]
PC_TARGETS = ('board', 'ram')
PALETTE = ['#a020f0', '#ff4569', '#ff943b', '#ffdc60', '#40d9a0', '#3d9dff', '#ffffff']
RAINBOW = ['#ff4040', '#ffb040', '#f0f040', '#40e080', '#40a0ff', '#b060ff']


def build_panel(frame, v, pick, apply_selection, set_power, effects, speeds, fix_conflicts):
    """v: namespace com as variáveis Tk (target, mode, colour, brightness,
    temperature, effect, speed, pc_sync, power, status, warning)."""
    labels = dict(TARGETS)
    effect_info = {key: (name, colour) for key, name, colour, _ in effects}
    frame.configure(style='TFrame')

    def label(parent, text=None, fg=TEXT, **kwargs):
        return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=fg, **kwargs)

    shell = tk.Frame(frame, bg=BG)
    shell.pack(fill='both', expand=True)

    # Cabeçalho
    top = tk.Frame(shell, bg=BG)
    top.pack(fill='x')
    icon_label = tk.Label(top, bg=BG)
    icon_label.pack(side='left', padx=(0, 10))
    titles = tk.Frame(top, bg=BG)
    titles.pack(side='left')
    label(titles, 'Controle LED', font=(FONT, 18, 'bold')).pack(anchor='w')
    label(titles, textvariable=v.power, fg=MUTED, font=(FONT, 9)).pack(anchor='w')

    # Aviso de conflito (aparece só quando há)
    banner = RoundBox(shell, radius=BANNER_R, pad=BANNER_PAD, fill=WARN_BG, outline='#5a4320')
    label(banner.body, '⚠', fg=WARN, font=(FONT, 13)).pack(side='left', padx=(2, 8))
    label(banner.body, textvariable=v.warning, fg=WARN, wraplength=290, justify='left',
          font=(FONT, 9)).pack(side='left', fill='x', expand=True)
    fix_button = PillButton(banner.body, 'Corrigir', fix_conflicts, radius=BANNER_BTN_R,
                            height=32, fill=WARN, hover='#ffd28c', fg='#2a1c05',
                            font=(FONT, 9, 'bold'))
    fix_button.configure(width=86)
    fix_button.pack(side='right', padx=(8, 0))

    targets = Segmented(shell, v.target, TARGETS)
    targets.pack(fill='x', pady=(16, 10))

    power_row = tk.Frame(shell, bg=BG)
    power_row.pack(fill='x')
    on_button = PillButton(power_row, 'Ligar', lambda: set_power(True))
    on_button.pack(side='left', expand=True, fill='x', padx=(0, 5))
    off_button = PillButton(power_row, 'Desligar', lambda: set_power(False))
    off_button.pack(side='left', expand=True, fill='x', padx=(5, 0))
    Switch(shell, v.pc_sync, 'Controlar placa-mãe e memórias (OpenRGB)').pack(fill='x', pady=(10, 12))

    Segmented(shell, v.mode, [('colour', 'Cor'), ('white', 'Branco'), ('effect', 'Efeitos')],
              height=38, font_size=10).pack(fill='x', pady=(0, 10))

    preview = _Canvas(shell, height=96, cursor='hand2')
    preview.pack(fill='x')
    preview.bind('<Button-1>', lambda _: pick())
    preview.bind('<Configure>', lambda _: update())

    tools = RoundBox(shell)
    tools.pack(fill='x', pady=(10, 0))
    effect_tools = tk.Frame(tools.body, bg=SURFACE)
    label(effect_tools, 'Efeito', fg=MUTED, font=(FONT, 9)).pack(anchor='w', pady=(0, 6))
    ChipGrid(effect_tools, v.effect, [(key, name) for key, name, *_ in effects]).pack(fill='x')
    speed_row = tk.Frame(effect_tools, bg=SURFACE)
    speed_row.pack(fill='x', pady=(10, 0))
    label(speed_row, 'Velocidade', fg=MUTED, font=(FONT, 9)).pack(side='left', padx=(0, 10))
    ChipGrid(speed_row, v.speed, speeds, columns=3, chip_h=30).pack(side='left', expand=True, fill='x')

    colour_tools = tk.Frame(tools.body, bg=SURFACE)
    label(colour_tools, 'Cor', fg=MUTED, font=(FONT, 9)).pack(anchor='w', pady=(0, 4))
    Swatches(colour_tools, v.colour, PALETTE, pick).pack(fill='x')

    white_tools = tk.Frame(tools.body, bg=SURFACE)
    white_title = tk.Frame(white_tools, bg=SURFACE)
    white_title.pack(fill='x')
    label(white_title, 'Temperatura do branco', fg=MUTED, font=(FONT, 9)).pack(side='left')
    temperature_label = label(white_title, '', font=(FONT, 9, 'bold'))
    temperature_label.pack(side='right')
    Slider(white_tools, v.temperature, 0, 1000, gradient=('#ffba6b', '#cde4ff'), step=25).pack(fill='x', pady=(4, 0))
    ends = tk.Frame(white_tools, bg=SURFACE)
    ends.pack(fill='x')
    label(ends, 'Quente', fg=MUTED, font=(FONT, 8)).pack(side='left')
    label(ends, 'Frio', fg=MUTED, font=(FONT, 8)).pack(side='right')

    bright = RoundBox(shell)
    bright.pack(fill='x', pady=(10, 0))
    line = tk.Frame(bright.body, bg=SURFACE)
    line.pack(fill='x')
    label(line, 'Brilho', fg=MUTED, font=(FONT, 9)).pack(side='left')
    percent = label(line, '', font=(FONT, 9, 'bold'))
    percent.pack(side='right')
    Slider(bright.body, v.brightness, 1, 100, step=5).pack(fill='x', pady=(4, 0))

    action = PillButton(shell, '', apply_selection, radius=14, height=50, fill=ACCENT,
                        hover=ACCENT_HOVER, fg=ACCENT_TEXT, font=(FONT, 12, 'bold'))
    action.pack(fill='x', pady=(14, 4))

    footer = tk.Frame(shell, bg=BG)
    footer.pack(side='bottom', fill='x', pady=(8, 0))
    tk.Label(footer, textvariable=v.status, bg=BG, fg=MUTED, wraplength=440,
             justify='left', anchor='w', font=(FONT, 9)).pack(fill='x')
    brand = tk.Label(footer, text='Feito por System Bee Solutions ↗', bg=BG,
                     fg=ACCENT, cursor='hand2', takefocus=True, font=(FONT, 9), pady=6)
    brand.pack(anchor='w', pady=(2, 0))
    for sequence in ('<Button-1>', '<Return>', '<space>'):
        brand.bind(sequence, lambda _: webbrowser.open('https://systembee.com.br/'))

    def draw_preview(where, mode, colour, effect_name, effect_colour):
        preview.delete('all')
        w, h = preview.winfo_width(), preview.winfo_height()
        preview.shape(0, 0, w - 1, h - 1, CARD_R, fill=SURFACE)
        cx, cy, r = 62, h / 2, 26
        rainbow = mode == 'effect' and not effect_colour
        glow = mix(RAINBOW[0], RAINBOW[4], 0.5) if rainbow else colour
        for i in range(7, 0, -1):  # halo
            rr = r + i * 3
            preview.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline='',
                                fill=mix(SURFACE, glow, 0.04 + (7 - i) * 0.045))
        if rainbow:
            step = 360 / len(RAINBOW)
            for i, c in enumerate(RAINBOW):
                preview.create_arc(cx - r, cy - r, cx + r, cy + r, start=90 - (i + 1) * step,
                                   extent=step, fill=c, outline=c, style='pieslice')
        else:
            preview.create_oval(cx - r, cy - r, cx + r, cy + r, fill=colour, outline='')
        preview.create_oval(cx - 14, cy - 17, cx - 2, cy - 9, fill=mix(glow, '#ffffff', 0.6), outline='')
        title = ('Branco' if mode == 'white' else effect_name if mode == 'effect' else colour.upper())
        detail = (f'{colour.upper()} · ' if mode == 'effect' and effect_colour else '')
        hint = ('Ajuste a temperatura abaixo' if mode == 'white' else
                'Efeito com cores próprias' if rainbow else 'Clique para escolher outra cor')
        x = cx + r + 34
        preview.create_text(x, cy - 24, anchor='w', text=f'PRÉVIA · {where.upper()}', fill=MUTED, font=(FONT, 8))
        preview.create_text(x, cy, anchor='w', text=title, fill=TEXT, font=(FONT, 16, 'bold'))
        preview.create_text(x, cy + 24, anchor='w', fill=MUTED, font=(FONT, 9), text=detail + hint)

    def update(*_):
        if not v.pc_sync.get() and v.target.get() in PC_TARGETS:
            v.target.set('all')
            return
        targets.set_visible([k for k, _ in TARGETS if v.pc_sync.get() or k not in PC_TARGETS])
        mode = v.mode.get()
        where = labels.get(v.target.get(), 'Geral')
        percent.configure(text=f'{v.brightness.get()}%')
        temperature_label.configure(text=f'{round(v.temperature.get()/10)}% frio')
        effect_name, effect_colour = effect_info.get(v.effect.get(), ('Estático', True))
        for part in (effect_tools, colour_tools, white_tools):
            part.pack_forget()
        if mode == 'effect':
            effect_tools.pack(fill='x')
        if mode == 'white':
            white_tools.pack(fill='x')
        elif mode == 'colour' or effect_colour:
            colour_tools.pack(fill='x', pady=(12, 0) if mode == 'effect' else 0)
        on_button.set_text(f'Ligar · {where}')
        off_button.set_text(f'Desligar · {where}')
        action.set_text(f'Aplicar em {where}')
        colour = white_preview(v.temperature.get()) if mode == 'white' else v.colour.get()
        draw_preview(where, mode, colour, effect_name, effect_colour)

    def update_warning(*_):
        if v.warning.get():
            banner.pack(fill='x', pady=(14, 0), after=top)
        else:
            banner.pack_forget()

    for variable in (v.target, v.mode, v.colour, v.brightness, v.temperature, v.effect, v.pc_sync):
        variable.trace_add('write', update)
    v.warning.trace_add('write', update_warning)
    update()
    update_warning()

    def set_icon(photo):
        icon_label.configure(image=photo)
        icon_label.image = photo
    return set_icon


def build_menu(root, settings, refresh, minimize, quit_app):
    menu = tk.Menu(root)
    file_menu = tk.Menu(menu, tearoff=False)
    file_menu.add_command(label='Minimizar para a bandeja', command=minimize)
    file_menu.add_separator()
    file_menu.add_command(label='Sair', command=quit_app)
    menu.add_cascade(label='Arquivo', menu=file_menu)
    options = tk.Menu(menu, tearoff=False)
    options.add_command(label='Configurações…', command=settings)
    options.add_separator()
    options.add_command(label='Atualizar estado da fita', command=refresh)
    menu.add_cascade(label='Opções', menu=options)
    root.configure(menu=menu)

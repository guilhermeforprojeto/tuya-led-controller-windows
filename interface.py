"""Interface Tkinter do Controle LED.

Cantos contínuos (squircle) desenhados no Canvas e raios concêntricos:
o raio de um elemento interno é o raio do externo menos o espaço entre eles.
Poucas superfícies: seções separadas por espaço e título, só a prévia é card.
"""
import sys
import time
import tkinter as tk
import webbrowser
from tkinter import ttk
from types import SimpleNamespace

from fx import is_animated as fx_animated, rgb_to_hex, single as fx_single
from palettes import FAVOURITES, name_for
from shapes import concentric, squircle_points

# Cores
BG = '#0d111a'
SURFACE = '#161c29'
SURFACE_2 = '#202839'
SURFACE_3 = '#2c3549'
LINE = '#2a3346'
TEXT = '#f2f4fa'
TEXT_2 = '#c9d0de'
MUTED = '#8f9ab0'
ACCENT = '#c6a0ff'
ACCENT_HOVER = '#d6bbff'
ACCENT_SOFT = '#e4d4ff'
ACCENT_TEXT = '#1a1030'
WARN = '#ffbf5e'
WARN_BG = '#251d12'
OK = '#5fd39a'

# Raios: padroniza os de fora e calcula os de dentro.
CARD_R, CARD_PAD = 16, 12
CHIP_R = concentric(CARD_R, CARD_PAD)          # 4: chip dentro de card
FREE_R = 9                                      # chip/botão solto na tela
SEG_R, SEG_PAD = 12, 3
SEG_ITEM_R = concentric(SEG_R, SEG_PAD)        # 9
BTN_R = 10
BANNER_R, BANNER_PAD = 14, 8
BANNER_BTN_R = concentric(BANNER_R, BANNER_PAD)  # 6

# Windows 11 tem a Segoe UI Variable (melhor leitura em tamanhos pequenos).
_W11 = sys.platform == 'win32' and sys.getwindowsversion().build >= 22000
FONT = 'Segoe UI Variable Text' if _W11 else 'Segoe UI'
DISPLAY = 'Segoe UI Variable Display' if _W11 else 'Segoe UI'


def mix(a, b, t):
    """Mistura duas cores #rrggbb (t=0 → a, t=1 → b)."""
    ca = [int(a[i:i+2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i+2], 16) for i in (1, 3, 5)]
    return '#%02x%02x%02x' % tuple(round(x + (y - x) * t) for x, y in zip(ca, cb))


def white_preview(temperature):
    t = temperature / 1000
    return '#%02x%02x%02x' % tuple(round(a+(b-a)*t) for a, b in zip((255, 186, 107), (205, 228, 255)))


def draw_warning(canvas, x, y, size, colour):
    """Ícone de alerta desenhado (triângulo com exclamação)."""
    s = size
    canvas.create_polygon(x + s / 2, y + 1, x + s - 1, y + s - 2, x + 1, y + s - 2,
                          fill='', outline=colour, width=1.6, joinstyle='round')
    canvas.create_line(x + s / 2, y + s * 0.38, x + s / 2, y + s * 0.62, fill=colour,
                       width=1.8, capstyle='round')
    canvas.create_oval(x + s / 2 - 1.1, y + s * 0.74, x + s / 2 + 1.1, y + s * 0.74 + 2.2,
                       fill=colour, outline='')


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

    def watch(self, variable):
        """Redesenha quando a variável muda (e solta o vínculo ao destruir)."""
        trace = variable.trace_add('write', lambda *_: self.redraw())
        self.bind('<Destroy>', lambda e: e.widget is self and variable.trace_remove('write', trace),
                  add='+')


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
                 hover=SURFACE_3, fg=TEXT, font=None):
        # largura mínima: quem define o tamanho é o pack/grid (botões lado a lado iguais)
        super().__init__(parent, height=height, width=10, cursor='hand2', takefocus=True)
        self.text, self.command, self.radius = text, command, radius
        self.colours = {'fill': fill, 'hover': hover, 'fg': fg}
        self.font = font or (FONT, 10, 'bold')
        self._hover = self._focus = self._down = False
        for seq, fn in [('<Configure>', lambda _: self.redraw()),
                        ('<Enter>', lambda _: self._set('_hover', True)),
                        ('<Leave>', lambda _: self._set('_hover', False) or self._set('_down', False)),
                        ('<FocusIn>', lambda _: self._set('_focus', True)),
                        ('<FocusOut>', lambda _: self._set('_focus', False)),
                        ('<ButtonPress-1>', lambda _: self._set('_down', True)),
                        ('<ButtonRelease-1>', self._click),
                        ('<Return>', lambda _: self.command()),
                        ('<space>', lambda _: self.command())]:
            self.bind(seq, fn)

    def _set(self, name, value):
        setattr(self, name, value)
        self.redraw()

    def _click(self, event):
        self._set('_down', False)
        if 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            self.command()

    def set_text(self, text):
        self.text = text
        self.redraw()

    def redraw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        fill = self.colours['hover' if self._hover else 'fill']
        if self._down:  # resposta imediata ao clique
            fill = mix(fill, BG, 0.18)
        self.shape(0, 0, w - 1, h - 1, self.radius, fill=fill,
                   outline=ACCENT if self._focus else '', width=2)
        self.create_text(w / 2, h / 2, text=self.text, fill=self.colours['fg'], font=self.font)


class Segmented(_Canvas):
    """Abas em pílula: o item escolhido fica concêntrico ao contêiner."""
    def __init__(self, parent, variable, options, height=40, font_size=10):
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
        self.watch(variable)

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
        self.shape(0, 0, w - 1, h - 1, SEG_R, fill=SURFACE,
                   outline=ACCENT if self.has_focus() else '', width=2)
        labels = dict(self.options)
        n = len(self.visible)
        span = (w - 2 * SEG_PAD) / max(1, n)
        for i, key in enumerate(self.visible):
            x0 = SEG_PAD + i * span
            selected = key == self.variable.get()
            if selected or i == self._hover:
                self.shape(x0, SEG_PAD, x0 + span, h - SEG_PAD, SEG_ITEM_R,
                           fill=SURFACE_3 if selected else SURFACE_2)
            self.create_text(x0 + span / 2, h / 2, text=labels[key],
                             fill=TEXT if selected else MUTED,
                             font=(FONT, self.font_size, 'bold' if selected else 'normal'))


class ChipGrid(_Canvas):
    """Grade de opções. Discreta: só o item escolhido ganha cor."""
    def __init__(self, parent, variable, options, columns=4, chip_h=32, gap=6,
                 chip_fill=None, radius=FREE_R, font_size=9):
        self.rows = -(-len(options) // columns)
        super().__init__(parent, height=self.rows * chip_h + (self.rows - 1) * gap, cursor='hand2')
        self.variable, self.options = variable, list(options)
        self.columns, self.chip_h, self.gap, self.radius = columns, chip_h, gap, radius
        self.chip_fill = chip_fill or mix(self.cget('bg'), SURFACE_2, 0.75)
        self.font_size, self._hover = font_size, None
        self.bind('<Configure>', lambda _: self.redraw())
        self.bind('<Button-1>', self._click)
        self.bind('<Motion>', lambda e: self._set_hover(self._index_at(e.x, e.y)))
        self.bind('<Leave>', lambda _: self._set_hover(None))
        self.watch(variable)

    def _cell(self, index):
        w = (self.winfo_width() - (self.columns - 1) * self.gap) / self.columns
        r, c = divmod(index, self.columns)
        x0, y0 = c * (w + self.gap), r * (self.chip_h + self.gap)
        return x0, y0, x0 + w, y0 + self.chip_h

    def _index_at(self, x, y):
        for i in range(len(self.options)):
            x0, y0, x1, y1 = self._cell(i)
            if x0 <= x <= x1 and y0 <= y <= y1:
                return i
        return None

    def _set_hover(self, index):
        if index != self._hover:
            self._hover = index
            self.redraw()

    def _click(self, event):
        i = self._index_at(event.x, event.y)
        if i is not None:
            self.variable.set(self.options[i][0])

    def redraw(self):
        self.delete('all')
        for i, (key, text) in enumerate(self.options):
            x0, y0, x1, y1 = self._cell(i)
            selected = str(key) == str(self.variable.get())
            fill = (mix(self.cget('bg'), ACCENT, 0.24) if selected else
                    mix(self.chip_fill, '#ffffff', 0.06) if i == self._hover else self.chip_fill)
            self.shape(x0, y0, x1, y1, self.radius, fill=fill)
            self.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=text,
                             fill=ACCENT_SOFT if selected else TEXT_2,
                             font=(FONT, self.font_size, 'bold' if selected else 'normal'))


class StickChips(_Canvas):
    """Escolha de pentes (vários ao mesmo tempo). variable guarda as posições,
    ex.: '134'. Nunca fica vazio: o último escolhido não desmarca."""
    def __init__(self, parent, variable, count, height=32, gap=6):
        super().__init__(parent, height=height, cursor='hand2', takefocus=True)
        self.variable, self.count, self.gap = variable, count, gap
        self._hover = None
        self.bind('<Configure>', lambda _: self.redraw())
        self.bind('<Button-1>', self._click)
        self.bind('<Motion>', lambda e: self._set_hover(self._index_at(e.x)))
        self.bind('<Leave>', lambda _: self._set_hover(None))
        for n in range(1, 10):
            self.bind(str(n), lambda _e, n=n: self.toggle(n))
        self.watch(variable)
        self.watch(count)

    def _n(self):
        return max(1, self.count.get())

    def _cell(self, i):
        n = self._n() + 1  # +1: "Todos"
        w = (self.winfo_width() - (n - 1) * self.gap) / n
        return i * (w + self.gap), i * (w + self.gap) + w

    def _index_at(self, x):
        for i in range(self._n() + 1):
            x0, x1 = self._cell(i)
            if x0 <= x <= x1:
                return i
        return None

    def _set_hover(self, i):
        if i != self._hover:
            self._hover = i
            self.redraw()

    def chosen(self):
        return [int(c) for c in self.variable.get() if c.isdigit() and 0 < int(c) <= self._n()]

    def toggle(self, n):
        now = set(self.chosen())
        now ^= {n}
        if now:
            self.variable.set(''.join(str(i) for i in sorted(now)))

    def _click(self, event):
        self.focus_set()
        i = self._index_at(event.x)
        if i is None:
            return
        if i == self._n():
            self.variable.set(''.join(str(k) for k in range(1, self._n() + 1)))
        else:
            self.toggle(i + 1)

    def redraw(self):
        self.delete('all')
        h = self.winfo_height()
        chosen = set(self.chosen())
        every = len(chosen) == self._n()
        for i in range(self._n() + 1):
            x0, x1 = self._cell(i)
            on = every if i == self._n() else (i + 1) in chosen
            base = mix(self.cget('bg'), SURFACE_2, 0.75)
            fill = (mix(self.cget('bg'), ACCENT, 0.24) if on else
                    mix(base, '#ffffff', 0.06) if i == self._hover else base)
            self.shape(x0, 0, x1, h - 1, FREE_R, fill=fill)
            self.create_text((x0 + x1) / 2, h / 2, text='Todos' if i == self._n() else str(i + 1),
                             fill=ACCENT_SOFT if on else TEXT_2,
                             font=(FONT, 10, 'bold' if on else 'normal'))


class Swatches(_Canvas):
    """Paleta em círculos; o anel marca a cor atual. O último abre o seletor."""
    SIZE, GAP = 28, 10

    def __init__(self, parent, variable, colours, pick):
        super().__init__(parent, height=self.SIZE + 8, cursor='hand2')
        self.variable, self.colours, self.pick = variable, colours, pick
        self._hover = None
        self.bind('<Configure>', lambda _: self.redraw())
        self.bind('<Button-1>', self._click)
        self.bind('<Motion>', lambda e: self._set_hover(self._index_at(e.x, e.y)))
        self.bind('<Leave>', lambda _: self._set_hover(None))
        self.watch(variable)

    def _centre(self, i):
        return 4 + self.SIZE / 2 + i * (self.SIZE + self.GAP), 4 + self.SIZE / 2

    def _index_at(self, x, y):
        for i in range(len(self.colours) + 1):
            cx, cy = self._centre(i)
            if abs(x - cx) <= self.SIZE / 2 + 3 and abs(y - cy) <= self.SIZE / 2 + 3:
                return i
        return None

    def _set_hover(self, index):
        if index != self._hover:
            self._hover = index
            self.redraw()

    def _click(self, event):
        i = self._index_at(event.x, event.y)
        if i == len(self.colours):
            self.pick()
        elif i is not None:
            self.variable.set(self.colours[i])

    def redraw(self):
        self.delete('all')
        r = self.SIZE / 2
        current = self.variable.get().lower()
        for i, colour in enumerate(self.colours):
            x, y = self._centre(i)
            grow = 1.5 if i == self._hover else 0
            if colour.lower() == current:
                self.create_oval(x - r - 3, y - r - 3, x + r + 3, y + r + 3, outline=TEXT, width=2)
            self.create_oval(x - r + 1 - grow, y - r + 1 - grow, x + r - 1 + grow, y + r - 1 + grow,
                             fill=colour, outline='')
        x, y = self._centre(len(self.colours))
        custom = bool(current) and current not in [c.lower() for c in self.colours]
        hover = self._hover == len(self.colours)
        if custom:
            self.create_oval(x - r - 3, y - r - 3, x + r + 3, y + r + 3, outline=TEXT, width=2)
        self.create_oval(x - r + 1, y - r + 1, x + r - 1, y + r - 1,
                         fill=self.variable.get() if custom else (SURFACE_3 if hover else SURFACE_2),
                         outline='')
        # "+" desenhado
        mark = '#000000' if custom and _luma(self.variable.get()) > 0.6 else TEXT
        self.create_line(x - 5, y, x + 5, y, fill=mark, width=2, capstyle='round')
        self.create_line(x, y - 5, x, y + 5, fill=mark, width=2, capstyle='round')


def _luma(hex_colour):
    r, g, b = (int(hex_colour[i:i+2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


class Slider(_Canvas):
    """Barra com puxador, clique, arraste, roda do mouse e setas."""
    def __init__(self, parent, variable, lo, hi, gradient=None, step=1):
        super().__init__(parent, height=28, cursor='hand2', takefocus=True)
        self.variable, self.lo, self.hi, self.gradient, self.unit = variable, lo, hi, gradient, step
        self.bind('<Configure>', lambda _: self.redraw())
        self.bind('<Button-1>', self.select)
        self.bind('<B1-Motion>', self.select)
        self.bind('<MouseWheel>', lambda e: self.step(1 if e.delta > 0 else -1))
        for key, amount in [('Left', -1), ('Right', 1), ('Down', -1), ('Up', 1)]:
            self.bind('<' + key + '>', lambda _e, n=amount: self.step(n))
        self.bind('<FocusIn>', lambda _: self.redraw())
        self.bind('<FocusOut>', lambda _: self.redraw())
        self.watch(variable)

    def set_value(self, value):
        self.variable.set(max(self.lo, min(self.hi, round(value))))
        return 'break'

    def step(self, amount):
        return self.set_value(self.variable.get() + amount * self.unit)

    def select(self, event):
        self.focus_set()
        span = max(1, self.winfo_width() - 24)
        self.set_value(self.lo + (self.hi - self.lo) * (event.x - 12) / span)

    def redraw(self):
        self.delete('all')
        w = max(30, self.winfo_width())
        y = 14
        frac = (max(self.lo, min(self.hi, self.variable.get())) - self.lo) / (self.hi - self.lo)
        x = 12 + (w - 24) * frac
        if self.gradient:
            a, b = self.gradient
            pieces = 40
            for i in range(pieces):
                xa = 12 + (w - 24) * i / pieces
                xb = 12 + (w - 24) * (i + 1) / pieces
                self.create_line(xa, y, xb, y, width=6, fill=mix(a, b, i / (pieces - 1)),
                                 capstyle='round' if i in (0, pieces - 1) else 'butt')
        else:
            self.create_line(12, y, w - 12, y, fill=SURFACE_3, width=6, capstyle='round')
            self.create_line(12, y, x, y, fill=ACCENT, width=6, capstyle='round')
        if self.has_focus():
            self.create_oval(x - 12, y - 12, x + 12, y + 12, fill=mix(BG, ACCENT, 0.35), outline='')
        self.create_oval(x - 8, y - 8, x + 8, y + 8, fill='#ffffff', outline='')


class Switch(_Canvas):
    """Interruptor ligado/desligado com rótulo clicável."""
    def __init__(self, parent, variable, text):
        super().__init__(parent, height=24, cursor='hand2', takefocus=True)
        self.variable, self.text = variable, text
        self.bind('<Configure>', lambda _: self.redraw())
        for seq in ('<Button-1>', '<space>', '<Return>'):
            self.bind(seq, lambda _: self.variable.set(not self.variable.get()))
        self.watch(variable)

    def redraw(self):
        self.delete('all')
        on = bool(self.variable.get())
        # Trilho em pílula; puxador concêntrico (pílula dentro de pílula).
        self.create_line(12, 12, 28, 12, width=20, capstyle='round',
                         fill=ACCENT if on else SURFACE_3)
        x = 28 if on else 12
        self.create_oval(x - 7, 5, x + 7, 19, fill='#ffffff' if on else MUTED, outline='')
        self.create_text(50, 12, anchor='w', text=self.text, fill=TEXT_2 if on else MUTED,
                         font=(FONT, 9))


def setup_theme(root):
    root.configure(bg=BG)
    root.minsize(460, 0)  # a altura acompanha o conteúdo de cada modo
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
    style.configure('Vertical.TScrollbar', background=SURFACE_3, troughcolor=BG, bordercolor=BG,
                    arrowcolor=MUTED, lightcolor=SURFACE_3, darkcolor=SURFACE_3)
    style.map('Vertical.TScrollbar', background=[('active', MUTED)])


TARGETS = [('all', 'Geral'), ('strip', 'Fita'), ('board', 'Placa-mãe'), ('ram', 'Memórias')]
PC_TARGETS = ('board', 'ram')
PALETTE = FAVOURITES[:7]
RAINBOW = ['#ff4040', '#ffb040', '#f0f040', '#40e080', '#40a0ff', '#b060ff']


def section(parent, title, value=None):
    """Título de seção (e um valor à direita, se houver)."""
    row = tk.Frame(parent, bg=parent.cget('bg'))
    row.pack(fill='x', pady=(18, 6))
    tk.Label(row, text=title, bg=row.cget('bg'), fg=TEXT_2, font=(FONT, 10, 'bold')).pack(side='left')
    right = None
    if value is not None:
        right = tk.Label(row, text=value, bg=row.cget('bg'), fg=TEXT_2, font=(FONT, 10))
        right.pack(side='right')
    return right


def warning_banner(parent, variable, on_click, wraplength=300):
    """Aviso curto com ícone desenhado e botão Resolver."""
    banner = RoundBox(parent, radius=BANNER_R, pad=BANNER_PAD, fill=WARN_BG, outline='#4a3818')
    mark = _Canvas(banner.body, width=20, height=20)
    mark.pack(side='left', padx=(4, 8))
    draw_warning(mark, 1, 1, 18, WARN)
    tk.Label(banner.body, textvariable=variable, bg=WARN_BG, fg=WARN, wraplength=wraplength,
             justify='left', font=(FONT, 9)).pack(side='left', fill='x', expand=True)
    button = PillButton(banner.body, 'Resolver', on_click, radius=BANNER_BTN_R, height=30,
                        fill=WARN, hover='#ffd28c', fg='#2a1c05', font=(FONT, 9, 'bold'))
    button.configure(width=84)
    button.pack(side='right', padx=(8, 0))
    return banner


def build_panel(frame, v, pick, apply_selection, set_power, effects, speeds, fix_conflicts,
                ram=None):
    """v: namespace com as variáveis Tk (target, mode, colour, brightness,
    temperature, effect, speed, pc_sync, power, status, warning_short, sticks,
    stick_count). ram: preview(t, sel, posições) → [[rgb×5] por pente] e
    open_order() para escolher a ordem dos pentes."""
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
    icon_label.pack(side='left', padx=(0, 12))
    titles = tk.Frame(top, bg=BG)
    titles.pack(side='left')
    label(titles, 'Controle LED', font=(DISPLAY, 17, 'bold')).pack(anchor='w')
    label(titles, textvariable=v.power, fg=MUTED, font=(FONT, 9)).pack(anchor='w')

    banner = warning_banner(shell, v.warning_short, fix_conflicts)

    targets = Segmented(shell, v.target, TARGETS)
    targets.pack(fill='x', pady=(18, 10))

    # Aba Memórias: quais pentes (1–4) recebem o comando.
    stick_box = tk.Frame(shell, bg=BG)
    stick_head = tk.Frame(stick_box, bg=BG)
    stick_head.pack(fill='x', pady=(0, 6))
    tk.Label(stick_head, text='Pentes', bg=BG, fg=TEXT_2, font=(FONT, 10, 'bold')).pack(side='left')
    order_link = tk.Label(stick_head, text='Ordem e identificação', bg=BG, fg=ACCENT,
                          cursor='hand2', font=(FONT, 9))
    order_link.pack(side='right')
    order_link.bind('<Button-1>', lambda _: ram and ram.open_order())
    order_link.bind('<Enter>', lambda _: order_link.configure(fg=ACCENT_SOFT))
    order_link.bind('<Leave>', lambda _: order_link.configure(fg=ACCENT))
    StickChips(stick_box, v.sticks, v.stick_count).pack(fill='x')
    stick_hint = tk.Label(stick_box, bg=BG, fg=MUTED, font=(FONT, 8), anchor='w')
    stick_hint.pack(fill='x', pady=(4, 10))

    power_row = tk.Frame(shell, bg=BG)
    power_row.pack(fill='x')
    PillButton(power_row, 'Ligar', lambda: set_power(True), height=38).pack(
        side='left', expand=True, fill='x', padx=(0, 4))
    PillButton(power_row, 'Desligar', lambda: set_power(False), height=38).pack(
        side='left', expand=True, fill='x', padx=(4, 0))
    Switch(shell, v.pc_sync, 'Controlar placa-mãe e memórias (OpenRGB)').pack(fill='x', pady=(12, 0))

    Segmented(shell, v.mode, [('colour', 'Cor'), ('white', 'Branco'), ('effect', 'Efeitos')],
              height=36).pack(fill='x', pady=(18, 10))

    preview = _Canvas(shell, height=92, cursor='hand2')
    preview.pack(fill='x')
    preview.bind('<Button-1>', lambda _: pick())
    preview.bind('<Configure>', lambda _: update())

    tools = tk.Frame(shell, bg=BG)
    tools.pack(fill='x')
    effect_tools = tk.Frame(tools, bg=BG)
    section(effect_tools, 'Efeito')
    ChipGrid(effect_tools, v.effect, [(key, name) for key, name, *_ in effects]).pack(fill='x')
    section(effect_tools, 'Velocidade')
    ChipGrid(effect_tools, v.speed, speeds, columns=3, chip_h=30).pack(fill='x')

    colour_tools = tk.Frame(tools, bg=BG)
    section(colour_tools, 'Cor')
    Swatches(colour_tools, v.colour, PALETTE, pick).pack(fill='x')

    white_tools = tk.Frame(tools, bg=BG)
    temperature_label = section(white_tools, 'Temperatura', '')
    Slider(white_tools, v.temperature, 0, 1000, gradient=('#ffba6b', '#cde4ff'), step=25).pack(fill='x')
    ends = tk.Frame(white_tools, bg=BG)
    ends.pack(fill='x')
    label(ends, 'Quente', fg=MUTED, font=(FONT, 8)).pack(side='left')
    label(ends, 'Frio', fg=MUTED, font=(FONT, 8)).pack(side='right')

    percent = section(shell, 'Brilho', '')
    Slider(shell, v.brightness, 1, 100, step=5).pack(fill='x')

    action = PillButton(shell, '', apply_selection, radius=12, height=48, fill=ACCENT,
                        hover=ACCENT_HOVER, fg=ACCENT_TEXT, font=(FONT, 11, 'bold'))
    action.pack(fill='x', pady=(22, 0))

    footer = tk.Frame(shell, bg=BG)
    footer.pack(side='bottom', fill='x', pady=(14, 0))
    tk.Label(footer, textvariable=v.status, bg=BG, fg=MUTED, wraplength=420,
             justify='left', anchor='w', font=(FONT, 9)).pack(fill='x')
    brand = tk.Label(footer, text='System Bee Solutions ↗', bg=BG, fg=MUTED,
                     cursor='hand2', takefocus=True, font=(FONT, 8), pady=4)
    brand.pack(anchor='w', pady=(4, 0))
    brand.bind('<Enter>', lambda _: brand.configure(fg=ACCENT))
    brand.bind('<Leave>', lambda _: brand.configure(fg=MUTED))
    for sequence in ('<Button-1>', '<Return>', '<space>'):
        brand.bind(sequence, lambda _: webbrowser.open('https://systembee.com.br/'))

    def current_sel():
        return {k: getattr(v, k).get() for k in
                ('mode', 'colour', 'brightness', 'temperature', 'effect', 'speed')}

    def sticks_mode():
        return v.target.get() == 'ram' and ram is not None

    def led_area():
        return 52 + 22 + 30 if not sticks_mode() else 20 + v.stick_count.get() * 20 + 24

    def draw_led(t=None):
        """Parte animada da prévia: o LED (ou os pentes), no relógio do efeito."""
        t = time.time() if t is None else t
        preview.delete('led')
        h = preview.winfo_height()
        sel = current_sel()
        if sticks_mode():
            positions = [int(c) for c in v.sticks.get() if c.isdigit()]
            rows = ram.preview(t, sel, positions) or []
            x = 20
            for i, row in enumerate(rows):
                chosen = (i + 1) in positions
                top, bottom = 14, h - 24
                preview.shape(x, top, x + 14, bottom, 4, fill=SURFACE_3 if chosen else SURFACE_2,
                              outline=ACCENT if chosen else '', width=1, tags='led')
                step = (bottom - top - 8) / max(1, len(row))
                for k, rgb in enumerate(reversed(row)):  # LED 1 embaixo, como no pente
                    y = top + 4 + k * step + step / 2
                    c = rgb_to_hex(rgb)
                    preview.create_oval(x + 3, y - 4, x + 11, y + 4, fill=c, outline='', tags='led')
                preview.create_text(x + 7, h - 12, text=str(i + 1), tags='led',
                                    fill=ACCENT_SOFT if chosen else MUTED,
                                    font=(FONT, 8, 'bold' if chosen else 'normal'))
                x += 20
            return
        colour = rgb_to_hex(fx_single(sel, t))
        glow = mix(SURFACE, colour, 1.0)
        cx, cy, r = 52, h / 2, 22
        for i in range(6, 0, -1):  # halo
            rr = r + i * 3
            preview.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline='', tags='led',
                                fill=mix(SURFACE, glow, 0.03 + (6 - i) * 0.05))
        preview.create_oval(cx - r, cy - r, cx + r, cy + r, fill=colour, outline='', tags='led')

    def draw_preview(where, mode, colour, effect_name, effect_colour):
        preview.delete('all')
        w, h = preview.winfo_width(), preview.winfo_height()
        preview.shape(0, 0, w - 1, h - 1, CARD_R, fill=SURFACE)
        cy = h / 2
        rainbow = mode == 'effect' and not effect_colour
        draw_led()
        name = name_for(colour)
        if mode == 'white':
            title, detail = 'Branco', 'Ajuste a temperatura abaixo'
        elif mode == 'effect':
            title = effect_name
            detail = 'Cores próprias do efeito' if rainbow else (name or colour.upper())
        else:
            title = name or colour.upper()
            detail = colour.upper() + ' · clique para mais cores' if name else 'Clique para mais cores'
        if sticks_mode():
            n = len([c for c in v.sticks.get() if c.isdigit()])
            detail = ('Todos os pentes' if n == v.stick_count.get() else
                      f"Pente{'s' if n > 1 else ''} {', '.join(c for c in v.sticks.get())}") + ' · ' + detail
        x = led_area()
        preview.create_text(x, cy - 10, anchor='w', text=title, fill=TEXT, font=(DISPLAY, 15, 'bold'))
        preview.create_text(x, cy + 14, anchor='w', fill=MUTED, font=(FONT, 9), text=detail)

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
            colour_tools.pack(fill='x')
        if sticks_mode():
            stick_box.pack(fill='x', after=targets)
            stick_hint.configure(text='Escolha um ou mais pentes; os outros ficam como estão.')
        else:
            stick_box.pack_forget()
        action.set_text(f'Aplicar em {where}')
        colour = white_preview(v.temperature.get()) if mode == 'white' else v.colour.get()
        draw_preview(where, mode, colour, effect_name, effect_colour)

    def update_warning(*_):
        if v.warning_short.get():
            banner.pack(fill='x', pady=(16, 0), after=top)
        else:
            banner.pack_forget()

    for variable in (v.target, v.mode, v.colour, v.brightness, v.temperature, v.effect, v.pc_sync,
                     v.speed, v.sticks, v.stick_count):
        variable.trace_add('write', update)
    v.warning_short.trace_add('write', update_warning)
    update()
    update_warning()

    def set_icon(photo):
        icon_label.configure(image=photo)
        icon_label.image = photo

    def tick(t):
        """Chamado pelo relógio de animação; só redesenha o que se move."""
        if sticks_mode() or fx_animated(current_sel()):
            draw_led(t)

    return SimpleNamespace(set_icon=set_icon, tick=tick, redraw=update)


def build_menu(root, settings, refresh, minimize, quit_app, extras=()):
    menu = tk.Menu(root)
    file_menu = tk.Menu(menu, tearoff=False)
    file_menu.add_command(label='Minimizar para a bandeja', command=minimize)
    file_menu.add_separator()
    file_menu.add_command(label='Sair', command=quit_app)
    menu.add_cascade(label='Arquivo', menu=file_menu)
    options = tk.Menu(menu, tearoff=False)
    options.add_command(label='Configurações…', command=settings)
    for text, command in extras:
        options.add_command(label=text, command=command)
    options.add_separator()
    options.add_command(label='Atualizar estado da fita', command=refresh)
    menu.add_cascade(label='Opções', menu=options)
    root.configure(menu=menu)

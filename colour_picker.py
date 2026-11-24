"""Seletor de cores do Controle LED (substitui o seletor antigo do Windows).

Abas com sugestões nomeadas (Vivas, Aconchego, Foco, Pantone) e uma aba
Livre com campo de matiz × saturação. Não há controle de "escuro": no LED o
brilho é ajustado à parte, então o campo só oferece o que a fita mostra.
"""
import colorsys
import re
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from shapes import squircle_points

from interface import (BG, SURFACE, SURFACE_2, SURFACE_3, TEXT, TEXT_2, MUTED, ACCENT,
                       ACCENT_HOVER, ACCENT_TEXT, FONT, DISPLAY, CARD_R, _Canvas, PillButton,
                       Segmented, mix)
from palettes import GROUPS, name_for

FIELD_H = 150
MIN_SAT = 0.12  # a base do campo é quase branca, nunca cinza


def hex_from_hs(h, s):
    r, g, b = colorsys.hsv_to_rgb(h, s, 1)
    return '#%02x%02x%02x' % (round(r * 255), round(g * 255), round(b * 255))


def hs_from_hex(hex_colour):
    rgb = [int(hex_colour[i:i+2], 16) / 255 for i in (1, 3, 5)]
    h, s, _ = colorsys.rgb_to_hsv(*rgb)
    return h, s


def parse_hex(text):
    text = (text or '').strip().lstrip('#')
    if re.fullmatch(r'[0-9a-fA-F]{3}', text):
        text = ''.join(c * 2 for c in text)
    return '#' + text.lower() if re.fullmatch(r'[0-9a-fA-F]{6}', text) else None


class NamedSwatches(_Canvas):
    """Grade de cores com o nome embaixo de cada uma."""
    COLS, CELL_H, R = 5, 70, 17

    def __init__(self, parent, colours, current, choose, confirm):
        rows = -(-len(colours) // self.COLS)
        super().__init__(parent, height=rows * self.CELL_H, cursor='hand2')
        self.colours, self.current, self.choose, self.confirm = colours, current, choose, confirm
        self._hover = None
        self.bind('<Configure>', lambda _: self.redraw())
        self.bind('<Button-1>', lambda e: self._pick(e, self.choose))
        self.bind('<Double-Button-1>', lambda e: self._pick(e, self.confirm))
        self.bind('<Motion>', self._motion)
        self.bind('<Leave>', lambda _: self._set_hover(None))
        self.watch(current)

    def _cell(self, i):
        w = self.winfo_width() / self.COLS
        r, c = divmod(i, self.COLS)
        return c * w, r * self.CELL_H, w

    def _index(self, x, y):
        w = max(1, self.winfo_width() / self.COLS)
        i = int(y // self.CELL_H) * self.COLS + int(x // w)
        return i if 0 <= i < len(self.colours) else None

    def _motion(self, event):
        self._set_hover(self._index(event.x, event.y))

    def _set_hover(self, i):
        if i != self._hover:
            self._hover = i
            self.redraw()

    def _pick(self, event, action):
        i = self._index(event.x, event.y)
        if i is not None:
            action(self.colours[i][1])

    def redraw(self):
        self.delete('all')
        current = self.current.get().lower()
        for i, (name, colour) in enumerate(self.colours):
            x0, y0, w = self._cell(i)
            cx, cy, r = x0 + w / 2, y0 + self.R + 4, self.R
            if colour.lower() == current:
                self.create_oval(cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4, outline=TEXT, width=2)
            grow = 1.5 if i == self._hover else 0
            self.create_oval(cx - r - grow, cy - r - grow, cx + r + grow, cy + r + grow,
                             fill=colour, outline='')
            title, _, year = name.partition(' · ')
            selected = colour.lower() == current
            self.create_text(cx, cy + r + 12, text=title, fill=TEXT if selected else TEXT_2,
                             font=(FONT, 8, 'bold' if selected else 'normal'), width=w - 4)
            if year:
                self.create_text(cx, cy + r + 25, text=year, fill=MUTED, font=(FONT, 8))


class HueSatField(_Canvas):
    """Campo livre: matiz na horizontal, saturação na vertical."""
    def __init__(self, parent, current, choose):
        super().__init__(parent, height=FIELD_H, cursor='crosshair')
        self.current, self.choose = current, choose
        self._image = None
        self._size = None
        self.bind('<Configure>', lambda _: self.redraw())
        self.bind('<Button-1>', self._pick)
        self.bind('<B1-Motion>', self._pick)
        self.watch(current)

    def _render(self, w, h):
        hues = Image.new('RGB', (w, 1))
        hues.putdata([tuple(round(c * 255) for c in colorsys.hsv_to_rgb(x / max(1, w - 1), 1, 1))
                      for x in range(w)])
        hues = hues.resize((w, h))
        mask = Image.linear_gradient('L').resize((w, h))  # 0 em cima → 255 embaixo
        mask = mask.point(lambda v: round(v * (1 - MIN_SAT)))
        field = Image.composite(Image.new('RGB', (w, h), 'white'), hues, mask)
        # Cantos contínuos: recorta o campo sobre o fundo da janela.
        shape = Image.new('L', (w, h), 0)
        ImageDraw.Draw(shape).polygon(squircle_points(0, 0, w - 1, h - 1, CARD_R), fill=255)
        return ImageTk.PhotoImage(Image.composite(field, Image.new('RGB', (w, h), BG), shape))

    def _pick(self, event):
        w, h = max(1, self.winfo_width() - 1), max(1, self.winfo_height() - 1)
        hue = max(0, min(1, event.x / w))
        sat = 1 - max(0, min(1, event.y / h)) * (1 - MIN_SAT)
        self.choose(hex_from_hs(hue, sat))

    def redraw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2:
            return
        if self._size != (w, h):
            self._size = (w, h)
            self._image = self._render(w, h)
        self.delete('all')
        self.create_image(0, 0, anchor='nw', image=self._image)
        try:
            hue, sat = hs_from_hex(self.current.get())
        except (ValueError, IndexError):
            return
        x = hue * (w - 1)
        y = (1 - sat) / (1 - MIN_SAT) * (h - 1)
        y = max(0, min(h - 1, y))
        self.create_oval(x - 9, y - 9, x + 9, y + 9, outline='#ffffff', width=3)
        self.create_oval(x - 10, y - 10, x + 10, y + 10, outline='#000000', width=1)


class ColourPicker:
    def __init__(self, root, initial, on_pick, recent=()):
        self.on_pick = on_pick
        self.colour = tk.StringVar(value=(initial or '#8a2bff').lower())
        win = self.win = tk.Toplevel(root, bg=BG)
        win.title('Escolher cor')
        win.resizable(False, False)
        win.transient(root)
        box = tk.Frame(win, bg=BG, padx=20, pady=18)
        box.pack(fill='both', expand=True)

        # Prévia
        head = tk.Frame(box, bg=BG)
        head.pack(fill='x')
        self.dot = _Canvas(head, width=48, height=48)
        self.dot.pack(side='left', padx=(0, 14))
        names = tk.Frame(head, bg=BG)
        names.pack(side='left', fill='x', expand=True)
        self.title = tk.Label(names, bg=BG, fg=TEXT, font=(DISPLAY, 15, 'bold'), anchor='w')
        self.title.pack(anchor='w')
        hex_row = tk.Frame(names, bg=BG)
        hex_row.pack(anchor='w', pady=(2, 0))
        tk.Label(hex_row, text='HEX', bg=BG, fg=MUTED, font=(FONT, 8)).pack(side='left', padx=(0, 6))
        self.hex_text = tk.StringVar()
        entry = tk.Entry(hex_row, textvariable=self.hex_text, width=9, bg=SURFACE_2, fg=TEXT,
                         insertbackground=TEXT, relief='flat', font=(FONT, 10),
                         highlightthickness=1, highlightbackground=SURFACE_2, highlightcolor=ACCENT)
        entry.pack(side='left', ipady=3, ipadx=4)
        entry.bind('<Return>', lambda _: self._typed())
        entry.bind('<FocusOut>', lambda _: self._typed())

        # Abas
        tabs = [(key, title) for key, title, _ in GROUPS] + [('livre', 'Livre')]
        self.tab = tk.StringVar(value=self._initial_tab())
        Segmented(box, self.tab, tabs, height=36, font_size=9).pack(fill='x', pady=(18, 4))
        self.hint = tk.Label(box, bg=BG, fg=MUTED, font=(FONT, 8), anchor='w', justify='left',
                             wraplength=400)
        self.hint.pack(fill='x', pady=(4, 10))
        self.pages = {}
        holder = tk.Frame(box, bg=BG, height=FIELD_H)
        holder.pack(fill='x')
        holder.pack_propagate(False)  # mesma altura em todas as abas
        for key, _, colours in GROUPS:
            self.pages[key] = NamedSwatches(holder, colours, self.colour, self.set, self.confirm)
        self.pages['livre'] = HueSatField(holder, self.colour, self.set)
        self.tab.trace_add('write', lambda *_: self._show_tab())

        # Recentes
        self.recent = [c for c in recent if parse_hex(c)][:8]
        if self.recent:
            tk.Label(box, text='Recentes', bg=BG, fg=TEXT_2, font=(FONT, 9, 'bold')).pack(
                anchor='w', pady=(16, 6))
            row = _Canvas(box, height=26, cursor='hand2')
            row.pack(fill='x')
            for i, c in enumerate(self.recent):
                row.create_oval(i * 32 + 2, 2, i * 32 + 24, 24, fill=c, outline='', tags=('c', c))
            row.tag_bind('c', '<Button-1>', lambda e: self.set(row.gettags('current')[1]))

        buttons = tk.Frame(box, bg=BG)
        buttons.pack(fill='x', pady=(20, 0))
        PillButton(buttons, 'Cancelar', win.destroy, height=40).pack(
            side='left', expand=True, fill='x', padx=(0, 4))
        PillButton(buttons, 'Usar esta cor', self.confirm, height=40, fill=ACCENT,
                   hover=ACCENT_HOVER, fg=ACCENT_TEXT).pack(side='left', expand=True, fill='x', padx=(4, 0))

        self.colour.trace_add('write', lambda *_: self._refresh())
        win.bind('<Escape>', lambda _: win.destroy())
        self._show_tab()
        self._refresh()
        win.geometry('460x0')
        win.update_idletasks()
        win.geometry(f'460x{win.winfo_reqheight()}+{root.winfo_rootx() + 20}+{root.winfo_rooty() + 40}')
        win.grab_set()
        win.focus_force()

    def _initial_tab(self):
        current = self.colour.get()
        for key, _, colours in GROUPS:
            if current in [c.lower() for _, c in colours]:
                return key
        return 'vivas' if not name_for(current) else 'livre'

    def _show_tab(self):
        for page in self.pages.values():
            page.pack_forget()
        key = self.tab.get()
        self.pages[key].pack(fill='x')
        self.hint.configure(text={
            'vivas': 'Cores puras: as mais fortes e fiéis no LED.',
            'aconchego': 'Tons quentes e suaves para a noite.',
            'foco': 'Tons frios e claros para trabalhar ou estudar.',
            'pantone': 'Cores do ano da Pantone (aproximações). No LED os tons escuros '
                       'aparecem mais vivos, porque o brilho é ajustado à parte.',
            'livre': 'Arraste para escolher: matiz na horizontal, intensidade da cor na vertical.',
        }[key])

    def _refresh(self):
        c = self.colour.get()
        self.dot.delete('all')
        for i in range(4, 0, -1):
            rr = 18 + i * 1.5
            self.dot.create_oval(24 - rr, 24 - rr, 24 + rr, 24 + rr, outline='',
                                 fill=mix(BG, c, 0.08 * (5 - i)))
        self.dot.create_oval(6, 6, 42, 42, fill=c, outline='')
        self.title.configure(text=name_for(c) or 'Cor personalizada')
        self.hex_text.set(c.upper())

    def _typed(self):
        value = parse_hex(self.hex_text.get())
        if value:
            self.set(value)
        else:
            self.hex_text.set(self.colour.get().upper())

    def set(self, hex_colour):
        self.colour.set(hex_colour.lower())

    def confirm(self, hex_colour=None):
        if hex_colour:
            self.set(hex_colour)
        value = self.colour.get()
        self.win.destroy()
        self.on_pick(value)

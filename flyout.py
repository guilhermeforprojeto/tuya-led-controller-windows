"""Painel rápido da bandeja (botão direito no ícone), no visual do app.

Substitui o menu nativo do Windows. É montado uma vez e só mostrado/escondido,
então abre na hora; mostra "Enviando…/Aplicado" para cada toque.
"""
import ctypes
import time
import tkinter as tk

from effects import EFFECTS
from interface import (BG, TEXT, MUTED, ACCENT, FONT, DISPLAY, PillButton,
                       ChipGrid, Slider, Swatches, section, warning_banner)
from palettes import FAVOURITES

WIDTH = 340
WHITES = [('0', 'Quente'), ('500', 'Neutro'), ('1000', 'Frio')]


class SmallSwatches(Swatches):
    SIZE, GAP = 24, 8


def tray_icon_class(on_right_click):
    """Ícone da bandeja em que o botão direito chama on_right_click
    em vez de abrir o menu nativo."""
    from pystray import _win32
    rbutton_up = getattr(_win32.win32, 'WM_RBUTTONUP', 0x0205)

    class TrayIcon(_win32.Icon):
        def _on_notify(self, wparam, lparam):
            if lparam == rbutton_up:
                on_right_click()
                return
            return super()._on_notify(wparam, lparam)
    return TrayIcon


def _round_corners(win):
    """Cantos arredondados nativos do Windows 11 (ignorado em versões antigas)."""
    try:
        hwnd = int(win.wm_frame(), 16)
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), 4)
    except Exception:
        pass


def _place(win, width, height):
    """Abre perto do cursor, dentro da área útil (sem cobrir a barra de tarefas)."""
    try:
        import win32api
        cx, cy = win32api.GetCursorPos()
        left, top, right, bottom = win32api.GetMonitorInfo(
            win32api.MonitorFromPoint((cx, cy), 2))['Work']
    except Exception:
        cx, cy = win.winfo_pointerxy()
        left, top, right, bottom = 0, 0, win.winfo_screenwidth(), win.winfo_screenheight()
    x = max(left + 8, min(cx - width // 2, right - width - 8))
    y = bottom - height - 8 if cy > (top + bottom) / 2 else top + 8
    win.geometry(f'{width}x{height}+{x}+{y}')


class TrayFlyout:
    def __init__(self, root, ctx):
        """ctx: selection(), quick(changes), power(on), pick_colour(), open_main(),
        open_auto(), open_conflicts(), quit(), warning (StringVar curta), status
        (StringVar), subtitle(), icon_image(size)."""
        self.root, self.ctx = root, ctx
        self.win = None
        self.visible = False
        self.closed_at = 0
        self._syncing = False
        self._debounce = None

    # ---- abrir/fechar
    def toggle(self):
        if self.visible:
            self.hide()
        elif time.time() - self.closed_at > 0.3:  # o clique que fechou não reabre
            self.show()

    def show(self):
        if self.win is None:
            self._build()
        self._sync()
        win = self.win
        # Os cards (ex.: aviso) ajustam a altura num evento próprio: mede até estabilizar.
        height = 0
        for _ in range(4):
            win.update()
            self.banner._fit()  # oculto, o card não recebe <Configure>
            if win.winfo_reqheight() == height:
                break
            height = win.winfo_reqheight()
            _place(win, WIDTH, height)
        win.deiconify()
        win.lift()
        win.focus_force()
        self.visible = True

    def prepare(self):
        """Monta o painel com antecedência (a primeira abertura também fica instantânea)."""
        if self.win is None:
            self._build()

    def hide(self):
        if self.win is not None and self.visible:
            self.win.withdraw()
            self.visible = False
            self.closed_at = time.time()

    close = hide

    def _maybe_hide(self):
        if not self.visible:
            return
        try:
            focused = self.win.focus_get()
        except (KeyError, tk.TclError):
            focused = None
        if focused is None or not str(focused).startswith(str(self.win)):
            self.hide()

    # ---- montagem (uma vez)
    def _send(self, changes):
        if not self._syncing:
            self.ctx.quick(changes)

    def _build(self):
        ctx = self.ctx
        win = self.win = tk.Toplevel(self.root, bg=BG)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes('-topmost', True)
        box = tk.Frame(win, bg=BG, padx=18, pady=16)
        box.pack(fill='both', expand=True)

        def label(parent, text='', fg=MUTED, font=None, **kw):
            return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=fg,
                            font=font or (FONT, 9), **kw)

        head = tk.Frame(box, bg=BG)
        head.pack(fill='x')
        self.icon_label = tk.Label(head, bg=BG)
        self.icon_label.pack(side='left', padx=(0, 12))
        titles = tk.Frame(head, bg=BG)
        titles.pack(side='left', fill='x', expand=True)
        label(titles, 'Controle LED', fg=TEXT, font=(DISPLAY, 13, 'bold')).pack(anchor='w')
        self.subtitle = label(titles, wraplength=230, justify='left')
        self.subtitle.pack(anchor='w')
        self.anchor = head
        self.banner = warning_banner(box, ctx.warning, self._then(ctx.open_conflicts), wraplength=170)

        power = tk.Frame(box, bg=BG)
        power.pack(fill='x', pady=(16, 0))
        PillButton(power, 'Ligar', lambda: ctx.power(True), height=36).pack(
            side='left', expand=True, fill='x', padx=(0, 4))
        PillButton(power, 'Desligar', lambda: ctx.power(False), height=36).pack(
            side='left', expand=True, fill='x', padx=(4, 0))

        section(box, 'Cor')
        self.colour = tk.StringVar()
        SmallSwatches(box, self.colour, FAVOURITES, self._then(ctx.pick_colour)).pack(fill='x')
        self.colour.trace_add('write', lambda *_: self.colour.get() and
                              self._send({'mode': 'colour', 'colour': self.colour.get()}))
        self.white = tk.StringVar()
        ChipGrid(box, self.white, WHITES, columns=3, chip_h=30).pack(fill='x', pady=(10, 0))
        self.white.trace_add('write', lambda *_: self.white.get() and
                             self._send({'mode': 'white', 'temperature': int(self.white.get())}))

        section(box, 'Efeito')
        self.effect = tk.StringVar()
        ChipGrid(box, self.effect, [(k, n) for k, n, *_ in EFFECTS if k != 'static'],
                 columns=3, chip_h=30).pack(fill='x')
        self.effect.trace_add('write', lambda *_: self.effect.get() and
                              self._send({'mode': 'effect', 'effect': self.effect.get()}))

        self.percent = section(box, 'Brilho', '')
        self.bright = tk.IntVar(value=100)
        Slider(box, self.bright, 1, 100, step=5).pack(fill='x')
        self.bright.trace_add('write', self._brightness_changed)

        label(box, textvariable=ctx.status, wraplength=300, justify='left',
              anchor='w').pack(fill='x', pady=(14, 0))

        foot = tk.Frame(box, bg=BG)
        foot.pack(fill='x', pady=(12, 0))
        for text, fn, side in [('Abrir controles', ctx.open_main, 'left'),
                               ('Rotinas e perfis', ctx.open_auto, 'left'),
                               ('Sair', ctx.quit, 'right')]:
            base = ACCENT if side == 'left' else MUTED
            link = label(foot, text, fg=base, cursor='hand2')
            link.pack(side=side, padx=(0, 14) if side == 'left' else 0)
            link.bind('<Button-1>', lambda _e, f=fn: self._then(f)())
            link.bind('<Enter>', lambda _e, w=link: w.configure(fg=TEXT))
            link.bind('<Leave>', lambda _e, w=link, c=base: w.configure(fg=c))

        win.bind('<Escape>', lambda _: self.hide())
        win.bind('<FocusOut>', lambda _: win.after(150, self._maybe_hide))
        # Primeira exibição fora da tela para os cantos e medidas ficarem prontos.
        win.geometry(f'{WIDTH}x600+-4000+-4000')
        win.deiconify()
        win.update()
        _round_corners(win)
        win.withdraw()

    def _then(self, fn):
        def run(*_):
            self.hide()
            fn()
        return run

    def _brightness_changed(self, *_):
        self.percent.configure(text=f'{self.bright.get()}%')
        if self._syncing:
            return
        if self._debounce:
            self.win.after_cancel(self._debounce)
        # Espera parar de arrastar para não enfileirar vários envios.
        self._debounce = self.win.after(350, lambda: self.ctx.quick({'brightness': self.bright.get()}))

    def _sync(self):
        """Traz o painel para o estado atual sem disparar envios."""
        sel = self.ctx.selection()
        self._syncing = True
        try:
            mode = sel.get('mode')
            self.colour.set(sel.get('colour', '') if mode == 'colour' else '')
            self.white.set(str(sel.get('temperature')) if mode == 'white' else '')
            self.effect.set(sel.get('effect', '') if mode == 'effect' else '')
            self.bright.set(sel.get('brightness', 100))
        finally:
            self._syncing = False
        photo = self.ctx.icon_image(36)
        self.icon_label.configure(image=photo)
        self.icon_label.image = photo
        self.subtitle.configure(text=self.ctx.subtitle())
        if self.ctx.warning.get():
            self.banner.pack(fill='x', pady=(14, 0), after=self.anchor)
        else:
            self.banner.pack_forget()

    def refresh_icon(self):
        """Só o ícone do cabeçalho (acompanha o efeito animado)."""
        if self.win is not None:
            photo = self.ctx.icon_image(36)
            self.icon_label.configure(image=photo)
            self.icon_label.image = photo

    def refresh(self):
        """Atualiza o painel aberto (ex.: depois de aplicar)."""
        if self.visible:
            self._sync()

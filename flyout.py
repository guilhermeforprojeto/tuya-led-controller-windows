"""Painel rápido da bandeja (botão direito no ícone), no visual do app.

Substitui o menu nativo do Windows: cores, brancos, efeitos, brilho,
ligar/desligar e o aviso de programas que interferem, num painel que abre
acima do relógio e fecha ao clicar fora.
"""
import ctypes
import time
import tkinter as tk

from effects import EFFECTS, QUICK_COLOURS
from interface import (BG, SURFACE, SURFACE_2, SURFACE_3, TEXT, MUTED, ACCENT, ACCENT_HOVER,
                       ACCENT_TEXT, WARN, WARN_BG, FONT, CHIP_R, RoundBox, PillButton,
                       ChipGrid, Slider, Swatches, mix)

WIDTH = 340
WHITES = [('0', 'Quente'), ('500', 'Neutro'), ('1000', 'Frio')]


class SmallSwatches(Swatches):
    SIZE, GAP = 22, 7


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


def _place(win, width):
    """Abre perto do cursor, dentro da área útil (sem cobrir a barra de tarefas)."""
    win.update_idletasks()
    w, h = width, win.winfo_reqheight()
    try:
        import win32api
        cx, cy = win32api.GetCursorPos()
        left, top, right, bottom = win32api.GetMonitorInfo(
            win32api.MonitorFromPoint((cx, cy), 2))['Work']
    except Exception:
        cx, cy = win.winfo_pointerxy()
        left, top, right, bottom = 0, 0, win.winfo_screenwidth(), win.winfo_screenheight()
    x = max(left + 8, min(cx - w // 2, right - w - 8))
    y = bottom - h - 8 if cy > (top + bottom) / 2 else top + 8
    win.geometry(f'{w}x{h}+{x}+{y}')


class TrayFlyout:
    def __init__(self, root, ctx):
        """ctx: selection(), quick(changes), power(on), open_main(), open_auto(),
        open_conflicts(), quit(), conflicts(), subtitle(), icon_image(size)."""
        self.root, self.ctx = root, ctx
        self.win = None
        self.closed_at = 0
        self._debounce = None

    def toggle(self):
        if self.win is not None:
            self.close()
        elif time.time() - self.closed_at > 0.35:  # o clique que fechou não reabre
            self.open()

    def close(self):
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None
            self.closed_at = time.time()

    def _act(self, fn, close=False):
        def run(*_):
            fn()
            if close:
                self.close()
        return run

    def open(self):
        ctx = self.ctx
        sel = ctx.selection()
        win = self.win = tk.Toplevel(self.root, bg=BG)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes('-topmost', True)
        box = tk.Frame(win, bg=BG, padx=16, pady=14, highlightthickness=1,
                       highlightbackground=SURFACE_3)
        box.pack(fill='both', expand=True)

        def label(parent, text, fg=MUTED, size=9, bold=False, **kw):
            return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=fg,
                            font=(FONT, size, 'bold' if bold else 'normal'), **kw)

        # Cabeçalho
        head = tk.Frame(box, bg=BG)
        head.pack(fill='x')
        photo = ctx.icon_image(36)
        tk.Label(head, image=photo, bg=BG).pack(side='left', padx=(0, 10))
        head.image = photo
        titles = tk.Frame(head, bg=BG)
        titles.pack(side='left', fill='x', expand=True)
        label(titles, 'Controle LED', fg=TEXT, size=12, bold=True).pack(anchor='w')
        label(titles, ctx.subtitle(), wraplength=180, justify='left').pack(anchor='w')
        opener = PillButton(head, 'Abrir', self._act(ctx.open_main, True), radius=CHIP_R,
                            height=30, font=(FONT, 9, 'bold'))
        opener.configure(width=64)
        opener.pack(side='right')

        found = ctx.conflicts()
        if found:
            warn = RoundBox(box, radius=14, pad=10, fill=WARN_BG, outline='#5a4320')
            warn.pack(fill='x', pady=(12, 0))
            text = (f'⚠  {len(found)} programa(s) interferindo nos LEDs. '
                    'Clique para resolver.')
            w = label(warn.body, text, fg=WARN, wraplength=270, justify='left', cursor='hand2')
            w.pack(anchor='w')
            for widget in (w, warn, warn.body):
                widget.bind('<Button-1>', self._act(ctx.open_conflicts, True))

        power = tk.Frame(box, bg=BG)
        power.pack(fill='x', pady=(12, 0))
        PillButton(power, 'Ligar', self._act(lambda: ctx.power(True)), height=36).pack(
            side='left', expand=True, fill='x', padx=(0, 4))
        PillButton(power, 'Desligar', self._act(lambda: ctx.power(False)), height=36).pack(
            side='left', expand=True, fill='x', padx=(4, 0))

        card = RoundBox(box)
        card.pack(fill='x', pady=(12, 0))
        body = card.body
        label(body, 'Cores').pack(anchor='w')
        colour = tk.StringVar(value=sel.get('colour', '') if sel.get('mode') == 'colour' else '')
        SmallSwatches(body, colour, [c for _, c in QUICK_COLOURS],
                      self._act(ctx.open_main, True)).pack(fill='x', pady=(4, 0))
        colour.trace_add('write', lambda *_: ctx.quick({'mode': 'colour', 'colour': colour.get()}))

        white = tk.StringVar(value=str(sel.get('temperature')) if sel.get('mode') == 'white' else '')
        ChipGrid(body, white, WHITES, columns=3, chip_h=28).pack(fill='x', pady=(8, 0))
        white.trace_add('write', lambda *_: ctx.quick({'mode': 'white', 'temperature': int(white.get())}))

        label(body, 'Efeitos').pack(anchor='w', pady=(12, 4))
        effect = tk.StringVar(value=sel.get('effect', '') if sel.get('mode') == 'effect' else '')
        ChipGrid(body, effect, [(k, n) for k, n, *_ in EFFECTS if k != 'static'],
                 columns=3, chip_h=30).pack(fill='x')
        effect.trace_add('write', lambda *_: ctx.quick({'mode': 'effect', 'effect': effect.get()}))

        line = tk.Frame(body, bg=SURFACE)
        line.pack(fill='x', pady=(12, 0))
        label(line, 'Brilho').pack(side='left')
        bright = tk.IntVar(value=sel.get('brightness', 100))
        percent = label(line, f'{bright.get()}%', fg=TEXT, bold=True)
        percent.pack(side='right')
        Slider(body, bright, 1, 100, step=5).pack(fill='x')

        def brightness_changed(*_):
            percent.configure(text=f'{bright.get()}%')
            if self._debounce:
                win.after_cancel(self._debounce)
            # Espera parar de arrastar para não enfileirar vários envios.
            self._debounce = win.after(450, lambda: ctx.quick({'brightness': bright.get()}))
        bright.trace_add('write', brightness_changed)

        foot = tk.Frame(box, bg=BG)
        foot.pack(fill='x', pady=(12, 0))
        for text, fn in [('Rotinas e perfis', ctx.open_auto), ('Sair', ctx.quit)]:
            link = label(foot, text, fg=ACCENT if text != 'Sair' else MUTED, cursor='hand2')
            link.pack(side='left' if text != 'Sair' else 'right')
            link.bind('<Button-1>', self._act(fn, True))

        # Desenha fora da tela para os cards calcularem a altura, depois posiciona.
        win.geometry(f'{WIDTH}x600+-4000+-4000')
        win.deiconify()
        for _ in range(3):
            win.update()
        _place(win, WIDTH)
        _round_corners(win)
        win.lift()
        win.focus_force()
        win.bind('<Escape>', lambda _: self.close())
        win.bind('<FocusOut>', lambda _: win.after(150, self._maybe_close))

    def _maybe_close(self):
        if self.win is None:
            return
        try:
            focused = self.win.focus_get()
        except (KeyError, tk.TclError):
            focused = None
        if focused is None or not str(focused).startswith(str(self.win)):
            self.close()

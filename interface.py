"""Interface Tkinter do Controle LED: foco nos ajustes de iluminação."""
import tkinter as tk
import webbrowser
from tkinter import ttk

BG = '#10141e'
CARD = '#1b2231'
TEXT = '#f2f4fa'
MUTED = '#a8b2c7'
ACCENT = '#c6a0ff'


class BrightnessSlider(tk.Canvas):
    """Barra contínua com preenchimento, puxador visível e acesso por teclado."""
    def __init__(self, parent, variable):
        super().__init__(parent, height=38, bg=BG, highlightthickness=1,
                         highlightbackground=BG, highlightcolor=ACCENT,
                         bd=0, takefocus=True, cursor='hand2')
        self.variable = variable
        self.bind('<Configure>', lambda _: self.redraw())
        self.bind('<Button-1>', self.select)
        self.bind('<B1-Motion>', self.select)
        for key, amount in [('Left', -1), ('Right', 1), ('Down', -1), ('Up', 1)]:
            self.bind('<'+key+'>', lambda event, n=amount: self.step(n))
        self.bind('<Home>', lambda _: self.set_value(1))
        self.bind('<End>', lambda _: self.set_value(100))
        self._trace = variable.trace_add('write', lambda *_: self.redraw())
        self.bind('<Destroy>', self.cleanup)

    def cleanup(self, event):
        if event.widget is self:
            self.variable.trace_remove('write', self._trace)

    def set_value(self, value):
        self.variable.set(max(1, min(100, round(value))))
        return 'break'

    def step(self, amount):
        return self.set_value(self.variable.get()+amount)

    def select(self, event):
        self.focus_set()
        span = max(1, self.winfo_width()-32)
        self.set_value(1+99*(event.x-16)/span)

    def redraw(self):
        self.delete('all')
        width = max(34, self.winfo_width())
        x = 16+(width-32)*(max(1, min(100, self.variable.get()))-1)/99
        y = 19
        self.create_line(16, y, width-16, y, fill='#303b50', width=10, capstyle='round')
        self.create_line(16, y, x, y, fill=ACCENT, width=10, capstyle='round')
        self.create_oval(x-13, y-13, x+13, y+13, fill='#3d3458', outline='')
        self.create_oval(x-9, y-9, x+9, y+9, fill='#f5efff', outline=ACCENT, width=2)


def setup_theme(root):
    root.configure(bg=BG)
    root.geometry('480x760')
    root.minsize(480, 740)
    root.resizable(True, True)
    root.option_add('*Font', ('Segoe UI', 10))
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', background=BG, foreground=TEXT)
    style.configure('TFrame', background=BG)
    style.configure('TLabel', background=BG, foreground=TEXT)
    style.configure('TButton', background=CARD, foreground=TEXT, padding=9, borderwidth=0)
    style.map('TButton', background=[('active', '#303b50')])
    style.configure('TCheckbutton', background=BG, foreground=TEXT)
    style.map('TCheckbutton', background=[('active', BG)])
    style.configure('TEntry', fieldbackground=CARD, foreground=TEXT, insertcolor=TEXT)
    style.configure('TSeparator', background='#303b50')


TARGETS = [('all', 'Geral'), ('strip', 'Fita'), ('board', 'Placa-mãe'), ('ram', 'Memórias')]
PC_TARGETS = ('board', 'ram')
PALETTE = ['#a020f0', '#ff4569', '#ff943b', '#ffdc60', '#40d9a0', '#3d9dff', '#ffffff']


def white_preview(temperature):
    t = temperature / 1000
    return '#%02x%02x%02x' % tuple(round(a+(b-a)*t) for a, b in zip((255, 186, 107), (205, 228, 255)))


def build_panel(frame, v, pick, apply_selection, set_power, effects, speeds):
    """v: namespace com as variáveis Tk (target, mode, colour, brightness,
    temperature, effect, speed, pc_sync, power, status)."""
    labels = dict(TARGETS)
    effect_info = {key: (name, colour) for key, name, colour, _ in effects}

    def label(parent, text=None, **kwargs):
        kwargs.setdefault('fg', TEXT)
        return tk.Label(parent, text=text, bg=parent.cget('bg'), **kwargs)

    def button(parent, text, callback, bg=CARD, fg=TEXT, **kwargs):
        return tk.Button(parent, text=text, command=callback, bg=bg, fg=fg,
                         activebackground='#3a4660', activeforeground=TEXT,
                         relief='flat', bd=0, cursor='hand2', padx=14, pady=8,
                         highlightthickness=0, **kwargs)

    def segmented(parent, variable, options, pady=8, font=None):
        bar = tk.Frame(parent, bg=CARD, padx=4, pady=4)
        items = {}
        for value, text in options:
            items[value] = tk.Radiobutton(bar, text=text, variable=variable, value=value,
                indicatoron=False, bg=CARD, fg=MUTED, selectcolor='#414269',
                activebackground='#303b50', activeforeground=TEXT, relief='flat',
                bd=0, pady=pady, cursor='hand2', font=font)
            items[value].pack(side='left', expand=True, fill='x')
        return bar, items

    shell = tk.Frame(frame, bg=BG)
    shell.pack(fill='both', expand=True)
    top = tk.Frame(shell, bg=BG)
    top.pack(fill='x')
    label(top, 'Controle LED', font=('Segoe UI', 20, 'bold')).pack(side='left')
    label(top, textvariable=v.power, fg=MUTED, font=('Segoe UI', 9)).pack(side='right', pady=(10, 0))

    target_bar, target_items = segmented(shell, v.target, TARGETS, font=('Segoe UI', 10, 'bold'))
    target_bar.pack(fill='x', pady=(10, 8))
    power_row = tk.Frame(shell, bg=BG)
    power_row.pack(fill='x', pady=(0, 6))
    on_button = button(power_row, 'Ligar', lambda: set_power(True))
    on_button.pack(side='left', expand=True, fill='x', padx=(0, 5))
    off_button = button(power_row, 'Desligar', lambda: set_power(False))
    off_button.pack(side='left', expand=True, fill='x', padx=(5, 0))
    tk.Checkbutton(shell, text='  Usar placa-mãe e memórias (OpenRGB)', variable=v.pc_sync,
                   bg=BG, fg=MUTED, selectcolor=CARD, activebackground=BG,
                   activeforeground=TEXT, highlightthickness=0, bd=0,
                   cursor='hand2', anchor='w', font=('Segoe UI', 9)).pack(fill='x', pady=(0, 8))

    mode_bar, _ = segmented(shell, v.mode, [('colour', 'Cor'), ('white', 'Branco'), ('effect', 'Efeitos')])
    mode_bar.pack(fill='x', pady=(0, 10))

    preview = tk.Canvas(shell, height=84, bg=CARD, highlightthickness=0, cursor='hand2')
    preview.pack(fill='x')
    preview.bind('<Button-1>', lambda _: pick())

    body = tk.Frame(shell, bg=BG)
    body.pack(fill='x')
    effect_tools = tk.Frame(body, bg=BG)
    grid = tk.Frame(effect_tools, bg=BG)
    grid.pack(fill='x', pady=(10, 0))
    for index, (key, name, _, _) in enumerate(effects):
        tk.Radiobutton(grid, text=name, variable=v.effect, value=key, indicatoron=False,
                       bg=CARD, fg=MUTED, selectcolor='#414269', activebackground='#303b50',
                       activeforeground=TEXT, relief='flat', bd=0, pady=7, cursor='hand2',
                       font=('Segoe UI', 9)).grid(row=index // 4, column=index % 4,
                                                  sticky='ew', padx=2, pady=2)
    for column in range(4):
        grid.columnconfigure(column, weight=1, uniform='fx')
    speed_row = tk.Frame(effect_tools, bg=BG)
    speed_row.pack(fill='x', pady=(6, 0))
    label(speed_row, 'Velocidade', font=('Segoe UI', 9)).pack(side='left', padx=(0, 10))
    speed_bar, _ = segmented(speed_row, v.speed, speeds, pady=4, font=('Segoe UI', 9))
    speed_bar.pack(side='left', expand=True, fill='x')

    colour_tools = tk.Frame(body, bg=BG)
    palette = tk.Frame(colour_tools, bg=BG)
    palette.pack(side='left', pady=10)
    for colour in PALETTE:
        tk.Button(palette, bg=colour, activebackground=colour, relief='flat', bd=0,
                  width=3, height=1, cursor='hand2',
                  command=lambda c=colour: v.colour.set(c)).pack(side='left', padx=(0, 5))
    button(colour_tools, 'Outra cor…', pick).pack(side='right', pady=8)

    white_tools = tk.Frame(body, bg=BG)
    white_title = tk.Frame(white_tools, bg=BG)
    white_title.pack(fill='x', pady=(10, 0))
    label(white_title, 'Temperatura do branco').pack(side='left')
    temperature_label = label(white_title, '')
    temperature_label.pack(side='right')
    tk.Scale(white_tools, from_=0, to=1000, variable=v.temperature, orient='horizontal',
             showvalue=False, bg=BG, fg=TEXT, troughcolor=CARD, activebackground=ACCENT,
             highlightthickness=0, bd=0, sliderrelief='flat', length=360).pack(fill='x')
    ends_white = tk.Frame(white_tools, bg=BG)
    ends_white.pack(fill='x')
    tk.Label(ends_white, text='Quente', bg=BG, fg=MUTED, font=('Segoe UI', 8)).pack(side='left')
    tk.Label(ends_white, text='Frio', bg=BG, fg=MUTED, font=('Segoe UI', 8)).pack(side='right')

    brightness_box = tk.Frame(shell, bg=BG)
    brightness_box.pack(fill='x', pady=(6, 0))
    line = tk.Frame(brightness_box, bg=BG)
    line.pack(fill='x')
    label(line, 'Brilho', font=('Segoe UI', 11, 'bold')).pack(side='left')
    percent = label(line, '', font=('Segoe UI', 11, 'bold'))
    percent.pack(side='right')
    BrightnessSlider(brightness_box, v.brightness).pack(fill='x', pady=(2, 0))
    action = tk.Button(shell, text='', command=apply_selection,
                       bg=ACCENT, fg='#171124', activebackground='#d9bfff',
                       activeforeground='#171124', relief='flat', bd=0,
                       cursor='hand2', pady=12, font=('Segoe UI', 12, 'bold'))
    action.pack(fill='x', pady=(10, 4))
    footer = tk.Frame(shell, bg=BG)
    footer.pack(side='bottom', fill='x', pady=(8, 0))
    tk.Label(footer, textvariable=v.status, bg=BG, fg=MUTED, wraplength=400,
             justify='left', anchor='w', font=('Segoe UI', 9)).pack(fill='x')
    brand = tk.Label(footer, text='Feito por System Bee Solutions ↗', bg=BG,
                     fg=ACCENT, cursor='hand2', takefocus=True,
                     font=('Segoe UI', 9, 'underline'), pady=6)
    brand.pack(anchor='w', pady=(2, 0))
    for sequence in ('<Button-1>', '<Return>', '<space>'):
        brand.bind(sequence, lambda _: webbrowser.open('https://systembee.com.br/'))

    def update(*_):
        if not v.pc_sync.get() and v.target.get() in PC_TARGETS:
            v.target.set('all')
            return
        for key in PC_TARGETS:
            target_items[key].pack_forget()
            if v.pc_sync.get():
                target_items[key].pack(side='left', expand=True, fill='x')
        mode = v.mode.get()
        where = labels.get(v.target.get(), 'Geral')
        percent.configure(text=f'{v.brightness.get()}%')
        temperature_label.configure(text=f'{round(v.temperature.get()/10)}% frio')
        effect_name, effect_colour = effect_info.get(v.effect.get(), ('Estático', True))
        for tools in (effect_tools, colour_tools, white_tools):
            tools.pack_forget()
        if mode == 'effect':
            effect_tools.pack(fill='x')
        if mode == 'white':
            white_tools.pack(fill='x')
        elif mode == 'colour' or effect_colour:
            colour_tools.pack(fill='x')
        on_button.configure(text=f'Ligar · {where}')
        off_button.configure(text=f'Desligar · {where}')
        action.configure(text=f'Aplicar em {where}')

        preview.delete('all')
        colour = white_preview(v.temperature.get()) if mode == 'white' else v.colour.get()
        if mode == 'effect' and not effect_colour:
            width = 68 / 6
            for i, c in enumerate(['#ff4040', '#ffb040', '#f0f040', '#40e080', '#40a0ff', '#b060ff']):
                preview.create_rectangle(16 + i*width, 8, 16 + (i+1)*width, 76, fill=c, outline='')
        else:
            preview.create_oval(16, 8, 84, 76, fill=colour, outline='')
        if mode == 'white':
            title = 'Branco'
        elif mode == 'effect':
            title = effect_name
        else:
            title = colour.upper()
        detail = (f'{colour.upper()} · ' if mode == 'effect' and effect_colour else '')
        preview.create_text(100, 24, anchor='w', text=f'PRÉVIA · {where.upper()}', fill=MUTED, font=('Segoe UI', 9))
        preview.create_text(100, 48, anchor='w', text=title, fill=TEXT, font=('Segoe UI', 17, 'bold'))
        preview.create_text(100, 70, anchor='w', fill=MUTED, font=('Segoe UI', 9),
                            text=detail + ('Ajuste a temperatura abaixo' if mode == 'white' else
                                         'Efeito com cores próprias' if mode == 'effect' and not effect_colour
                                         else 'Clique para escolher outra cor'))

    for variable in (v.target, v.mode, v.colour, v.brightness, v.temperature, v.effect, v.pc_sync):
        variable.trace_add('write', update)
    update()
    return update


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

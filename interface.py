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
    root.geometry('460x700')
    root.minsize(460, 700)
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


def build_panel(frame, state, brightness, temperature, mode, power, status,
                pick, apply_colour, set_power):
    def label(parent, text=None, **kwargs):
        return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=TEXT, **kwargs)

    def button(parent, text, callback, bg=CARD, fg=TEXT, **kwargs):
        return tk.Button(parent, text=text, command=callback, bg=bg, fg=fg,
                         activebackground='#3a4660', activeforeground=TEXT,
                         relief='flat', bd=0, cursor='hand2', padx=14, pady=9,
                         highlightthickness=0, **kwargs)

    shell = tk.Frame(frame, bg=BG)
    shell.pack(fill='both', expand=True)
    top = tk.Frame(shell, bg=BG)
    top.pack(fill='x')
    label(top, 'Controle LED', font=('Segoe UI', 22, 'bold')).pack(side='left')
    label(shell, textvariable=power).pack(anchor='w', pady=(2, 12))
    power_row = tk.Frame(shell, bg=BG)
    power_row.pack(fill='x', pady=(0, 16))
    button(power_row, 'Ligar', lambda: set_power(True)).pack(side='left', expand=True, fill='x', padx=(0, 5))
    button(power_row, 'Desligar', lambda: set_power(False)).pack(side='left', expand=True, fill='x', padx=(5, 0))

    tabs = tk.Frame(shell, bg=CARD, padx=4, pady=4)
    tabs.pack(fill='x', pady=(0, 14))
    for text, value in [('Cor RGB', 'colour'), ('Branco', 'white')]:
        tk.Radiobutton(tabs, text=text, variable=mode, value=value,
            indicatoron=False, bg=CARD, fg=MUTED, selectcolor='#414269',
            activebackground='#303b50', activeforeground=TEXT, relief='flat',
            bd=0, pady=9, cursor='hand2').pack(side='left', expand=True, fill='x')

    preview = tk.Canvas(shell, height=112, bg=CARD, highlightthickness=0, cursor='hand2')
    preview.pack(fill='x')
    preview.bind('<Button-1>', lambda _: pick())
    colour_tools = tk.Frame(shell, bg=BG)
    palette = tk.Frame(colour_tools, bg=BG)
    palette.pack(side='left', pady=12)
    for colour in ['#a020f0', '#ff4569', '#ff943b', '#ffdc60', '#40d9a0', '#3d9dff']:
        def choose(c=colour):
            state['colour'] = c
            mode.set('colour')
            update()
        tk.Button(palette, bg=colour, activebackground=colour, relief='flat', bd=0,
                  width=3, height=1, cursor='hand2', command=choose).pack(side='left', padx=(0, 5))
    button(colour_tools, 'Outra cor…', pick).pack(side='right', pady=8)
    white_tools = tk.Frame(shell, bg=BG)
    white_title = tk.Frame(white_tools, bg=BG)
    white_title.pack(fill='x', pady=(12, 0))
    label(white_title, 'Temperatura do branco').pack(side='left')
    temperature_label = label(white_title, '')
    temperature_label.pack(side='right')
    tk.Scale(white_tools, from_=0, to=1000, variable=temperature, orient='horizontal',
             showvalue=False, bg=BG, fg=TEXT, troughcolor=CARD, activebackground=ACCENT,
             highlightthickness=0, bd=0, sliderrelief='flat', length=360).pack(fill='x')
    label(white_tools, 'Quente                                               Frio', font=('Segoe UI', 9)).pack(fill='x')

    brightness_box = tk.Frame(shell, bg=BG)
    brightness_box.pack(fill='x', pady=(4, 0))
    line = tk.Frame(brightness_box, bg=BG)
    line.pack(fill='x')
    label(line, 'Brilho', font=('Segoe UI', 11, 'bold')).pack(side='left')
    percent = label(line, '', font=('Segoe UI', 11, 'bold'))
    percent.pack(side='right')
    BrightnessSlider(brightness_box, brightness).pack(fill='x', pady=(4, 0))
    ends = tk.Frame(brightness_box, bg=BG)
    ends.pack(fill='x')
    tk.Label(ends, text='1%', bg=BG, fg=MUTED, font=('Segoe UI', 8)).pack(side='left')
    tk.Label(ends, text='100%', bg=BG, fg=MUTED, font=('Segoe UI', 8)).pack(side='right')
    action = tk.Button(shell, text='Aplicar cor', command=apply_colour,
                       bg=ACCENT, fg='#171124', activebackground='#d9bfff',
                       activeforeground='#171124', relief='flat', bd=0,
                       cursor='hand2', pady=14, font=('Segoe UI', 13, 'bold'))
    action.pack(fill='x', pady=(12, 6))
    label(shell, 'Escolha os ajustes e clique em Aplicar.', font=('Segoe UI', 9)).pack(anchor='w')
    footer = tk.Frame(shell, bg=BG)
    footer.pack(side='bottom', fill='x', pady=(12, 0))
    tk.Label(footer, textvariable=status, bg=BG, fg=MUTED, wraplength=400,
             justify='left', anchor='w', font=('Segoe UI', 9)).pack(fill='x')
    brand = tk.Label(footer, text='Feito por System Bee Solutions ↗', bg=BG,
                     fg=ACCENT, cursor='hand2', takefocus=True,
                     font=('Segoe UI', 9, 'underline'), pady=8)
    brand.pack(anchor='w', pady=(4, 0))
    brand.bind('<Button-1>', lambda _: webbrowser.open('https://systembee.com.br/'))
    brand.bind('<Return>', lambda _: webbrowser.open('https://systembee.com.br/'))
    brand.bind('<space>', lambda _: webbrowser.open('https://systembee.com.br/'))

    def update(*_):
        percent.configure(text=f'{brightness.get()}%')
        temperature_label.configure(text=f'{round(temperature.get()/10)}% frio')
        white = mode.get() == 'white'
        action.configure(text='Aplicar branco e brilho' if white else 'Aplicar cor e brilho')
        colour_tools.pack_forget()
        white_tools.pack_forget()
        (white_tools if white else colour_tools).pack(fill='x', before=brightness_box)
        colour = state['colour']
        if white:
            t = temperature.get()/1000
            colour = '#%02x%02x%02x' % tuple(round(a+(b-a)*t) for a,b in zip((255,186,107),(205,228,255)))
        preview.delete('all')
        preview.create_oval(20, 20, 88, 88, fill=colour, outline='')
        preview.create_text(108, 36, anchor='w', text='PRÉVIA DA SELEÇÃO', fill=MUTED, font=('Segoe UI', 9))
        preview.create_text(108, 62, anchor='w', text='Branco' if white else state['colour'].upper(),
                            fill=TEXT, font=('Segoe UI', 18, 'bold'))
        preview.create_text(108, 88, anchor='w', text='Clique para escolher outra cor' if not white else 'Ajuste a temperatura abaixo',
                            fill=MUTED, font=('Segoe UI', 9))
    for variable in (brightness, temperature, mode):
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

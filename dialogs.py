"""Janelas secundárias: programas que interferem e rotinas/perfis."""
import tkinter as tk
import webbrowser
from tkinter import ttk

from automation import (ACTIONS, WHEN, DAY_NAMES, describe_days, describe_selection,
                        new_id, valid_time)
from conflicts import KNOWN_NAMES
from interface import (BG, SURFACE, SURFACE_2, SURFACE_3, TEXT, MUTED, ACCENT, ACCENT_HOVER,
                       ACCENT_TEXT, WARN, WARN_BG, FONT, CHIP_R, RoundBox, PillButton,
                       Switch, ChipGrid, _Canvas, mix)

OK = '#5fd39a'
DANGER = '#ff7a7a'


def _label(parent, text=None, fg=TEXT, size=9, bold=False, **kw):
    return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=fg, justify='left',
                    font=(FONT, size, 'bold' if bold else 'normal'), **kw)


def _small(parent, text, command, fill=SURFACE_3, fg=TEXT, width=96):
    b = PillButton(parent, text, command, radius=CHIP_R, height=28, fill=fill,
                   hover=mix(fill, '#ffffff', 0.12), fg=fg, font=(FONT, 9, 'bold'))
    b.configure(width=width)
    return b


class ScrollArea(tk.Frame):
    """Área com rolagem vertical (roda do mouse) para conteúdo longo."""
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        bar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.body = tk.Frame(self.canvas, bg=BG)
        win = self.canvas.create_window(0, 0, window=self.body, anchor='nw')
        self.body.bind('<Configure>', lambda _: self.canvas.configure(
            scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(win, width=e.width))
        self.bind_all_wheel()

    def bind_all_wheel(self):
        def wheel(event):
            if self.winfo_exists() and str(event.widget).startswith(str(self.winfo_toplevel())):
                self.canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        self.winfo_toplevel().bind('<MouseWheel>', wheel, add='+')

    def clear(self):
        for child in self.body.winfo_children():
            child.destroy()


def _window(root, title, size):
    win = tk.Toplevel(root)
    win.title(title)
    win.configure(bg=BG)
    win.geometry(size)
    win.minsize(520, 420)
    win.transient(root)
    return win


class ConflictsWindow:
    """Lista o que interfere nos LEDs, com instruções e ações."""

    def __init__(self, root, actions):
        self.actions = actions  # stop, uninstall(cmd), settings, recheck
        self.win = _window(root, 'Programas que interferem nos LEDs', '600x680')
        top = tk.Frame(self.win, bg=BG, padx=18, pady=14)
        top.pack(fill='x')
        _label(top, 'Programas que interferem nos LEDs', size=15, bold=True).pack(anchor='w')
        intro = RoundBox(top, radius=16, pad=12, fill=WARN_BG, outline='#5a4320')
        intro.pack(fill='x', pady=(10, 0))
        _label(intro.body, 'Só um programa pode controlar os LEDs de cada vez. Para o Controle LED '
               'funcionar corretamente, remova todo e qualquer outro programa que controle o RGB '
               'da placa-mãe e das memórias. Fechar não basta: eles voltam ao reiniciar.',
               fg=WARN, wraplength=520).pack(anchor='w')
        buttons = tk.Frame(top, bg=BG)
        buttons.pack(fill='x', pady=(10, 0))
        for text, key, fill, fg in [('Parar agora', 'stop', WARN, '#2a1c05'),
                                    ('Aplicativos instalados', 'settings', SURFACE_2, TEXT),
                                    ('Verificar de novo', 'recheck', SURFACE_2, TEXT)]:
            b = PillButton(buttons, text, actions[key], height=36, fill=fill,
                           hover=mix(fill, '#ffffff', 0.15), fg=fg, font=(FONT, 9, 'bold'))
            b.pack(side='left', expand=True, fill='x', padx=3)
        self.state = tk.StringVar()
        _label(top, textvariable=self.state, fg=MUTED).pack(anchor='w', pady=(8, 0))
        self.area = ScrollArea(self.win)
        self.area.pack(fill='both', expand=True, padx=(18, 4), pady=(0, 12))

    def set_status(self, text):
        if self.win.winfo_exists():
            self.state.set(text)

    def refresh(self, findings):
        if not self.win.winfo_exists():
            return
        self.area.clear()
        body = self.area.body
        if not findings:
            ok = RoundBox(body, fill=mix(SURFACE, OK, 0.12))
            ok.pack(fill='x', pady=(0, 10))
            _label(ok.body, '✓ Nenhum programa interferindo foi encontrado.', fg=OK, size=10,
                   bold=True).pack(anchor='w')
        for f in findings:
            card = RoundBox(body)
            card.pack(fill='x', pady=(0, 10))
            head = tk.Frame(card.body, bg=SURFACE)
            head.pack(fill='x')
            _label(head, f['name'], size=11, bold=True).pack(side='left')
            _label(head, 'ATIVO AGORA' if f['active'] else 'INSTALADO',
                   fg=DANGER if f['active'] else WARN, bold=True).pack(side='right')
            if f['running']:
                _label(card.body, 'Rodando: ' + ', '.join(sorted(set(f['running']))), fg=MUTED,
                       wraplength=500).pack(anchor='w', pady=(6, 0))
            if f['services']:
                _label(card.body, 'Serviços: ' + ', '.join(
                    n + (' (rodando)' if r else ' (ligado)') for n, r in f['services']),
                    fg=MUTED, wraplength=500).pack(anchor='w', pady=(4, 0))
            for name, cmd in f['installed']:
                row = tk.Frame(card.body, bg=SURFACE)
                row.pack(fill='x', pady=(6, 0))
                _label(row, '• ' + name).pack(side='left')
                _small(row, 'Desinstalar', lambda c=cmd: self.actions['uninstall'](c)).pack(side='right')
            for pkg in f['store']:
                row = tk.Frame(card.body, bg=SURFACE)
                row.pack(fill='x', pady=(6, 0))
                _label(row, '• ' + pkg.split('_')[0] + ' (Microsoft Store)').pack(side='left')
                _small(row, 'Abrir', self.actions['settings']).pack(side='right')
            _label(card.body, 'Como remover', fg=ACCENT, bold=True).pack(anchor='w', pady=(10, 2))
            for i, step in enumerate(f['steps'], 1):
                _label(card.body, f'{i}. {step}', wraplength=500).pack(anchor='w', pady=1)
            if f.get('help_url'):
                link = _label(card.body, 'Baixar a ferramenta oficial de remoção ↗', fg=ACCENT)
                link.configure(cursor='hand2')
                link.pack(anchor='w', pady=(6, 0))
                link.bind('<Button-1>', lambda _e, u=f['help_url']: webbrowser.open(u))
        known = RoundBox(body, fill=SURFACE)
        known.pack(fill='x', pady=(0, 10))
        _label(known.body, 'Também interferem (se instalar, remova):', fg=MUTED, bold=True).pack(anchor='w')
        _label(known.body, ', '.join(KNOWN_NAMES) + ' e qualquer outro programa de RGB.',
               fg=MUTED, wraplength=500).pack(anchor='w', pady=(4, 0))


class AutomationWindow:
    """Rotinas por horário e perfis por jogo/app."""

    def __init__(self, root, data, effects, current, list_apps, on_change):
        self.data, self.effects, self.current = data, effects, current
        self.list_apps, self.on_change = list_apps, on_change
        self.win = _window(root, 'Rotinas e perfis', '600x720')
        style = ttk.Style(self.win)
        style.configure('Dark.TCombobox', fieldbackground=SURFACE_2, background=SURFACE_3,
                        foreground=TEXT, arrowcolor=TEXT, bordercolor=SURFACE_3)
        style.map('Dark.TCombobox', fieldbackground=[('readonly', SURFACE_2)])
        self.win.option_add('*TCombobox*Listbox.background', SURFACE_2)
        self.win.option_add('*TCombobox*Listbox.foreground', TEXT)
        self.win.option_add('*TCombobox*Listbox.selectBackground', SURFACE_3)
        self.area = ScrollArea(self.win)
        self.area.pack(fill='both', expand=True, padx=(18, 4), pady=12)
        self.render()

    def changed(self):
        self.on_change()
        self.render()

    # ---- montagem
    def render(self):
        self.area.clear()
        body = self.area.body
        _label(body, 'Rotinas e perfis', size=15, bold=True).pack(anchor='w')
        _label(body, 'Cor/efeito usado nos itens novos: a seleção atual da aba Geral — '
               + describe_selection(self.current(), self.effects), fg=MUTED,
               wraplength=520).pack(anchor='w', pady=(2, 12))

        _label(body, 'Rotinas por horário', size=11, bold=True).pack(anchor='w', pady=(0, 6))
        if not self.data['routines']:
            _label(body, 'Nenhuma rotina. Ex.: 07:00 branco frio, 22:00 roxo fraco, 01:00 desligar.',
                   fg=MUTED).pack(anchor='w', pady=(0, 8))
        for r in self.data['routines']:
            action = dict(ACTIONS)[r['action']]
            extra = (' · ' + describe_selection(r['selection'], self.effects)
                     if r['action'] == 'apply' else '')
            self._item(body, r, f"{r['time']} · {describe_days(r['days'])}", action + extra,
                       self.data['routines'], can_update=r['action'] == 'apply')
        self._routine_form(body)

        _label(body, 'Perfis por jogo ou app', size=11, bold=True).pack(anchor='w', pady=(18, 6))
        _label(body, 'Quando o programa abre, os LEDs mudam; quando fecha, voltam às cores de antes. '
               'O primeiro da lista tem prioridade.', fg=MUTED, wraplength=520).pack(anchor='w', pady=(0, 8))
        for p in self.data['profiles']:
            self._item(body, p, p.get('label') or p['process'],
                       f"{dict(WHEN)[p['when']]} · {describe_selection(p['selection'], self.effects)}",
                       self.data['profiles'], can_update=True)
        self._profile_form(body)

    def _item(self, body, item, title, detail, collection, can_update):
        card = RoundBox(body, pad=12, radius=18)
        card.pack(fill='x', pady=(0, 8))
        row = tk.Frame(card.body, bg=SURFACE)
        row.pack(fill='x')
        enabled = tk.BooleanVar(value=item.get('enabled', True))

        def toggle(*_):
            item['enabled'] = enabled.get()
            self.on_change()
        enabled.trace_add('write', toggle)
        sw = Switch(row, enabled, '')
        sw.configure(width=46)
        sw.pack(side='left')
        texts = tk.Frame(row, bg=SURFACE)
        texts.pack(side='left', fill='x', expand=True)
        _label(texts, title, bold=True, size=10).pack(anchor='w')
        _label(texts, detail, fg=MUTED, wraplength=300).pack(anchor='w')

        def remove():
            collection.remove(item)
            self.changed()

        def update():
            item['selection'] = dict(self.current())
            self.changed()
        _small(row, 'Excluir', remove, fill=mix(SURFACE, DANGER, 0.25), width=72).pack(side='right')
        if can_update:
            _small(row, 'Usar cor atual', update, width=110).pack(side='right', padx=(0, 6))

    def _routine_form(self, body):
        card = RoundBox(body, fill=SURFACE_2)
        card.pack(fill='x', pady=(4, 0))
        f = card.body
        _label(f, 'Nova rotina', bold=True).pack(anchor='w')
        row = tk.Frame(f, bg=SURFACE_2)
        row.pack(fill='x', pady=(8, 0))
        _label(row, 'Horário', fg=MUTED).pack(side='left')
        time_var = tk.StringVar(value='22:00')
        tk.Entry(row, textvariable=time_var, width=7, bg=SURFACE_3, fg=TEXT, insertbackground=TEXT,
                 relief='flat', font=(FONT, 11), justify='center').pack(side='left', padx=8, ipady=4)
        _label(row, '(HH:MM)', fg=MUTED).pack(side='left')
        days = [tk.BooleanVar(value=True) for _ in DAY_NAMES]
        drow = tk.Frame(f, bg=SURFACE_2)
        drow.pack(fill='x', pady=(10, 0))
        for name, var in zip(DAY_NAMES, days):
            tk.Checkbutton(drow, text=name, variable=var, indicatoron=False, bg=SURFACE_3, fg=MUTED,
                           selectcolor=mix(SURFACE, ACCENT, 0.5), activebackground=SURFACE_3,
                           activeforeground=TEXT, relief='flat', bd=0, padx=8, pady=5,
                           cursor='hand2', font=(FONT, 9)).pack(side='left', expand=True, fill='x', padx=1)
        action = tk.StringVar(value='apply')
        ChipGrid(f, action, ACTIONS, columns=3, chip_h=30, chip_fill=SURFACE_3).pack(fill='x', pady=(10, 0))
        msg = tk.StringVar()

        def add():
            t = valid_time(time_var.get())
            chosen = [i for i, d in enumerate(days) if d.get()]
            if not t:
                return msg.set('Horário inválido. Use HH:MM, ex.: 07:30.')
            if not chosen:
                return msg.set('Escolha pelo menos um dia.')
            self.data['routines'].append({'id': new_id(), 'enabled': True, 'time': t,
                                          'days': chosen, 'action': action.get(),
                                          'selection': dict(self.current())})
            self.data['routines'].sort(key=lambda r: r['time'])
            self.changed()
        bottom = tk.Frame(f, bg=SURFACE_2)
        bottom.pack(fill='x', pady=(10, 0))
        _label(bottom, textvariable=msg, fg=DANGER).pack(side='left')
        PillButton(bottom, 'Adicionar rotina', add, radius=CHIP_R, height=34, fill=ACCENT,
                   hover=ACCENT_HOVER, fg=ACCENT_TEXT).pack(side='right', ipadx=60)

    def _profile_form(self, body):
        card = RoundBox(body, fill=SURFACE_2)
        card.pack(fill='x', pady=(4, 12))
        f = card.body
        _label(f, 'Novo perfil', bold=True).pack(anchor='w')
        _label(f, 'Abra o jogo/app, clique em Atualizar e escolha na lista (ou digite o .exe).',
               fg=MUTED, wraplength=500).pack(anchor='w', pady=(2, 0))
        row = tk.Frame(f, bg=SURFACE_2)
        row.pack(fill='x', pady=(8, 0))
        app = tk.StringVar()
        combo = ttk.Combobox(row, textvariable=app, style='Dark.TCombobox', font=(FONT, 10))
        combo.pack(side='left', fill='x', expand=True, ipady=3)
        apps = {}

        def reload():
            apps.clear()
            for exe, title in self.list_apps():
                apps[f'{exe} — {title[:50]}'] = (exe, title)
            combo.configure(values=list(apps))
        reload()
        _small(row, 'Atualizar', reload, width=90).pack(side='left', padx=(6, 0))
        when = tk.StringVar(value='open')
        ChipGrid(f, when, WHEN, columns=2, chip_h=30, chip_fill=SURFACE_3).pack(fill='x', pady=(10, 0))
        msg = tk.StringVar()

        def add():
            text = app.get().strip()
            exe, title = apps.get(text, (text.split(' — ')[0].strip(), ''))
            if not exe.lower().endswith('.exe'):
                return msg.set('Escolha um programa da lista ou digite o nome com .exe.')
            label = title.split(' - ')[0][:40] if title else exe
            self.data['profiles'].append({'id': new_id(), 'enabled': True, 'process': exe.lower(),
                                          'label': f'{label} ({exe})' if title else exe,
                                          'when': when.get(), 'selection': dict(self.current())})
            self.changed()
        bottom = tk.Frame(f, bg=SURFACE_2)
        bottom.pack(fill='x', pady=(10, 0))
        _label(bottom, textvariable=msg, fg=DANGER).pack(side='left')
        PillButton(bottom, 'Adicionar perfil', add, radius=CHIP_R, height=34, fill=ACCENT,
                   hover=ACCENT_HOVER, fg=ACCENT_TEXT).pack(side='right', ipadx=60)

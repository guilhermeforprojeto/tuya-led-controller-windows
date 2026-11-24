"""Janelas secundárias: programas que interferem e rotinas/perfis."""
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import ttk

from automation import (ACTIONS, WHEN, DAY_NAMES, describe_days, describe_selection,
                        new_id, valid_time)
from conflicts import KNOWN_NAMES
from interface import (BG, SURFACE, SURFACE_2, SURFACE_3, TEXT, TEXT_2, MUTED, ACCENT, ACCENT_HOVER, ACCENT_SOFT,
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


class DayChips(_Canvas):
    """Dias da semana (vários ao mesmo tempo); escolhido = destaque com texto claro."""
    def __init__(self, parent, variables, height=30, gap=4):
        super().__init__(parent, height=height, cursor='hand2')
        self.variables, self.gap = variables, gap
        self.bind('<Configure>', lambda _: self.redraw())
        self.bind('<Button-1>', self._click)
        for var in variables:
            self.watch(var)

    def _cell(self, i):
        n = len(self.variables)
        w = (self.winfo_width() - (n - 1) * self.gap) / n
        return i * (w + self.gap), i * (w + self.gap) + w

    def _click(self, event):
        for i, var in enumerate(self.variables):
            x0, x1 = self._cell(i)
            if x0 <= event.x <= x1:
                var.set(not var.get())

    def redraw(self):
        self.delete('all')
        h = self.winfo_height()
        for i, (name, var) in enumerate(zip(DAY_NAMES, self.variables)):
            x0, x1 = self._cell(i)
            on = var.get()
            self.shape(x0, 0, x1, h - 1, CHIP_R,
                       fill=mix(self.cget('bg'), ACCENT, 0.3) if on else SURFACE_3)
            self.create_text((x0 + x1) / 2, h / 2, text=name, fill=ACCENT_SOFT if on else MUTED,
                             font=(FONT, 9, 'bold' if on else 'normal'))


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


class StickOrderWindow:
    """Calibração dos pentes: acende um por vez (branco, os outros apagados) e
    pergunta em qual encaixe da placa ele está. No fim mostra a ordem para
    conferir (Piscar) e salvar. A ordem define o sentido dos efeitos (1 → 4)."""

    def __init__(self, root, pc, on_save, fallback=None):
        self.pc, self.on_save, self.fallback = pc, on_save, fallback
        self.win = _window(root, 'Calibrar pentes', '480x600')
        self.win.minsize(440, 420)
        self.win.protocol('WM_DELETE_WINDOW', self.close)
        box = tk.Frame(self.win, bg=BG, padx=20, pady=18)
        box.pack(fill='both', expand=True)
        _label(box, 'Calibrar pentes', size=15, bold=True).pack(anchor='w')
        _label(box, 'Conte os encaixes da placa-mãe a partir do processador: o mais perto '
               'dele é o 1. Vamos acender um pente por vez para você dizer onde ele está.',
               fg=MUTED, wraplength=430).pack(anchor='w', pady=(4, 12))
        # Rodapé reservado primeiro: o conteúdo nunca empurra os botões para fora.
        self.buttons = tk.Frame(box, bg=BG)
        self.buttons.pack(fill='x', side='bottom', pady=(14, 0))
        self.msg = tk.StringVar(value='Procurando os pentes…')
        _label(box, textvariable=self.msg, fg=MUTED, wraplength=430).pack(
            side='bottom', anchor='w', pady=(10, 0))
        self.body = tk.Frame(box, bg=BG)
        self.body.pack(fill='both', expand=True)
        self.found, self.order, self.answers, self.step = [], [], {}, 0
        self.win.after(50, self._load)

    # ---- utilidades
    def _clear(self):
        for frame in (self.body, self.buttons):
            for child in frame.winfo_children():
                child.destroy()

    def _footer(self, primary_text=None, primary=None):
        PillButton(self.buttons, 'Cancelar', self.close, height=40).pack(
            side='left', expand=True, fill='x', padx=(0, 4 if primary else 0))
        if primary:
            PillButton(self.buttons, primary_text, primary, height=40, fill=ACCENT,
                       hover=ACCENT_HOVER, fg=ACCENT_TEXT).pack(side='left', expand=True,
                                                                fill='x', padx=(4, 0))

    def close(self):
        self.pc.ram.set_solo(None, self.fallback)
        if self.win.winfo_exists():
            self.win.destroy()

    def _load(self):
        result = {}

        def run():
            try:
                result['order'] = self.pc.ram.addresses()
            except Exception as exc:
                result['error'] = str(exc)
        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        def wait():
            if thread.is_alive():
                self.win.after(100, wait)
            elif 'error' in result:
                self.msg.set(result['error'])
                self._footer()
            elif not result['order']:
                self.msg.set('Nenhum pente encontrado. Abra o OpenRGB como administrador.')
                self._footer()
            else:
                self.found = result['order']
                self.order = list(self.found)
                self.msg.set(f'{len(self.found)} pentes encontrados.')
                self.intro()
        wait()

    # ---- telas
    def intro(self):
        self._clear()
        card = RoundBox(self.body, pad=14, radius=16)
        card.pack(fill='x')
        _label(card.body, 'Ordem atual', bold=True, size=10).pack(anchor='w')
        _label(card.body, 'Se algum pente estiver no lugar errado (ex.: o 2 acende no encaixe 3), '
               'calibre. Leva menos de um minuto.', fg=MUTED, wraplength=390).pack(anchor='w', pady=(4, 0))
        self._footer('Começar calibração', self.ask_next)
        self.render_list(show_arrows=False)

    def ask_next(self):
        if self.step >= len(self.found):
            return self.finish()
        address = self.found[self.step]
        free = [p for p in range(1, len(self.found) + 1) if p not in self.answers.values()]
        if len(free) == 1:  # o último só pode ir para o encaixe que sobrou
            self.answers[address] = free[0]
            self.step += 1
            return self.ask_next()
        self.pc.ram.set_solo(address)
        self._clear()
        _label(self.body, f'Pente {self.step + 1} de {len(self.found)}', fg=ACCENT_SOFT,
               bold=True).pack(anchor='w')
        _label(self.body, 'Um pente acendeu em branco e os outros apagaram.\n'
               'Em qual encaixe da placa ele está?', size=12, bold=True,
               wraplength=430).pack(anchor='w', pady=(6, 14))
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill='x')
        for p in range(1, len(self.found) + 1):
            used = p not in free
            btn = PillButton(row, str(p), (lambda p=p: self.answer(address, p)) if not used else (lambda: None),
                             height=56, font=(FONT, 16, 'bold'),
                             fill=BG if used else SURFACE_2, hover=BG if used else SURFACE_3,
                             fg=SURFACE_3 if used else TEXT)
            btn.pack(side='left', expand=True, fill='x', padx=3)
        _label(self.body, 'Nenhum acendeu? Confira se o OpenRGB está aberto e clique em Cancelar.',
               fg=MUTED, wraplength=430).pack(anchor='w', pady=(14, 0))
        self.msg.set('Encaixes já usados ficam apagados.')
        self._footer()
        if self.step:
            back = _small(self.buttons, 'Voltar', self.back, width=80)
            back.pack(side='left', padx=(8, 0))

    def answer(self, address, position):
        self.answers[address] = position
        self.step += 1
        self.ask_next()

    def back(self):
        self.step = max(0, self.step - 1)
        self.answers.pop(self.found[self.step], None)
        self.ask_next()

    def finish(self):
        self.pc.ram.set_solo(None)
        self.order = sorted(self.found, key=lambda a: self.answers[a])
        self._clear()
        _label(self.body, 'Pronto. Confira:', size=12, bold=True).pack(anchor='w', pady=(0, 4))
        _label(self.body, 'Piscar acende o pente de branco por 2 segundos. Se algo ainda estiver '
               'errado, ajuste com as setas ou calibre de novo.', fg=MUTED,
               wraplength=430).pack(anchor='w', pady=(0, 10))
        self.render_list(show_arrows=True)
        self.msg.set('')
        self._footer('Salvar ordem', self.save)
        _small(self.buttons, 'Calibrar de novo', self.restart, width=130).pack(side='left', padx=(8, 0))

    def restart(self):
        self.answers, self.step = {}, 0
        self.ask_next()

    def render_list(self, show_arrows):
        holder = getattr(self, 'list_frame', None)
        if holder is not None and holder.winfo_exists():
            holder.destroy()
        self.list_frame = holder = tk.Frame(self.body, bg=BG)
        holder.pack(fill='x', pady=(10, 0))
        for i, address in enumerate(self.order):
            card = RoundBox(holder, pad=8, radius=12)
            card.pack(fill='x', pady=(0, 6))
            row = card.body
            _label(row, str(i + 1), size=14, bold=True, fg=ACCENT_SOFT).pack(side='left', padx=(6, 12))
            texts = tk.Frame(row, bg=SURFACE)
            texts.pack(side='left', fill='x', expand=True)
            _label(texts, f'Encaixe {i + 1}', bold=True, size=10).pack(anchor='w')
            _label(texts, f'Endereço {address}', fg=MUTED, size=8).pack(anchor='w')
            if show_arrows:
                _small(row, '↓', lambda i=i: self.move(i, 1), width=34).pack(side='right')
                _small(row, '↑', lambda i=i: self.move(i, -1), width=34).pack(side='right', padx=6)
            _small(row, 'Piscar', lambda a=address: self.pc.ram.identify(a), width=70).pack(side='right')

    def move(self, i, step):
        j = i + step
        if 0 <= j < len(self.order):
            self.order[i], self.order[j] = self.order[j], self.order[i]
            self.render_list(show_arrows=True)

    def save(self):
        if self.order:
            self.on_save(self.order)
        self.close()


class ConflictsWindow:
    """Lista o que interfere nos LEDs, com instruções e ações."""

    def __init__(self, root, actions):
        self.actions = actions  # stop, remove(cmds, findings), settings, recheck
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
        when = time.strftime('%H:%M:%S')
        serious = [f for f in findings if f.get('severity') != 'leftover']
        self.state.set(f'Verificado às {when}: ' + (
            ', '.join(f['name'] for f in serious) + ' ainda interferindo.' if serious else
            'nenhum programa interferindo nos LEDs.'
            + (' Há restos inativos (remover é opcional).' if findings else '')))
        if not serious:
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
            severity = f.get('severity', 'active' if f['active'] else 'installed')
            badge, colour = {'active': ('ATIVO AGORA', DANGER), 'installed': ('INSTALADO', WARN),
                             'leftover': ('RESTOS INATIVOS · OPCIONAL', MUTED)}[severity]
            _label(head, badge, fg=colour, bold=True).pack(side='right')
            if severity == 'installed':
                _label(card.body, 'Não está rodando agora, mas pode voltar a mudar as cores quando '
                       'o Windows o iniciar.', fg=MUTED, wraplength=500).pack(anchor='w', pady=(6, 0))
            if severity == 'leftover':
                _label(card.body, 'O app e o serviço já foram removidos. Sobraram componentes ocultos '
                       '(não aparecem em Configurações nem na Loja) que nada mais inicia, então não '
                       'mudam as cores. Pode deixar como está ou remover para limpar.',
                       fg=MUTED, wraplength=500).pack(anchor='w', pady=(6, 0))
            if f['running']:
                _label(card.body, 'Rodando: ' + ', '.join(sorted(set(f['running']))), fg=MUTED,
                       wraplength=500).pack(anchor='w', pady=(6, 0))
            if f['services']:
                _label(card.body, 'Serviços: ' + ', '.join(
                    n + (' (rodando)' if r else ' (ligado)') for n, r in f['services']),
                    fg=MUTED, wraplength=500).pack(anchor='w', pady=(4, 0))
            grouped = {}
            for name, cmd in f['installed']:
                grouped.setdefault(name, []).append(cmd)
            if grouped:
                every = [c for cmds in grouped.values() for c in cmds]
                top = tk.Frame(card.body, bg=SURFACE)
                top.pack(fill='x', pady=(10, 0))
                _label(top, f'{len(grouped)} componente(s) instalado(s)', fg=TEXT_2,
                       bold=True).pack(side='left')
                optional = f.get('severity') == 'leftover'
                _small(top, 'Remover todos', lambda c=every, f=f: self.actions['remove'](c, [f]),
                       fill=SURFACE_3 if optional else WARN, fg=TEXT if optional else '#2a1c05',
                       width=120).pack(side='right')
            for name, cmds in grouped.items():
                row = tk.Frame(card.body, bg=SURFACE)
                row.pack(fill='x', pady=(6, 0))
                _label(row, '• ' + name).pack(side='left')
                _small(row, 'Desinstalar', lambda c=cmds, f=f: self.actions['remove'](c, [f])).pack(side='right')
            for pkg in f['store']:
                row = tk.Frame(card.body, bg=SURFACE)
                row.pack(fill='x', pady=(6, 0))
                _label(row, '• ' + pkg.split('_')[0] + ' (Microsoft Store)').pack(side='left')
                _small(row, 'Abrir', self.actions['settings']).pack(side='right')
            if severity == 'leftover':
                _label(card.body, 'Dica: na BIOS, deixe "Download & Install ARMOURY CRATE app" em '
                       'Disabled para o Windows não reinstalar o Armoury Crate.',
                       fg=MUTED, wraplength=500).pack(anchor='w', pady=(10, 0))
                continue
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
        DayChips(f, days).pack(fill='x', pady=(10, 0))
        action = tk.StringVar(value='apply')
        ChipGrid(f, action, ACTIONS, columns=3, chip_h=30, chip_fill=SURFACE_3, radius=CHIP_R).pack(fill='x', pady=(10, 0))
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
        ChipGrid(f, when, WHEN, columns=2, chip_h=30, chip_fill=SURFACE_3, radius=CHIP_R).pack(fill='x', pady=(10, 0))
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

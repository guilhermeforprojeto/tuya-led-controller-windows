"""Rotinas por horário e perfis por jogo/app (lógica pura, testável).

Rotina:  {'id', 'enabled', 'time': 'HH:MM', 'days': [0..6] (0 = segunda),
          'action': 'apply' | 'on' | 'off', 'selection': {...}}
Perfil:  {'id', 'enabled', 'process': 'jogo.exe', 'label', 'when': 'open' | 'focus',
          'selection': {...}}
"""
import re
import uuid

DAY_NAMES = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
ACTIONS = [('apply', 'Aplicar cor/efeito'), ('on', 'Ligar tudo'), ('off', 'Desligar tudo')]
WHEN = [('open', 'Enquanto estiver aberto'), ('focus', 'Só em primeiro plano')]


def new_id():
    return uuid.uuid4().hex[:10]


def valid_time(text):
    m = re.fullmatch(r'\s*(\d{1,2}):(\d{2})\s*', text or '')
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None
    return f'{int(m.group(1)):02d}:{m.group(2)}'


def due_routines(routines, now, last_run):
    """Rotinas que devem rodar agora. last_run: {id: 'AAAA-MM-DD HH:MM'} (atualizado)."""
    stamp = now.strftime('%Y-%m-%d %H:%M')
    hhmm = now.strftime('%H:%M')
    due = []
    for r in routines:
        if not r.get('enabled', True) or r.get('time') != hhmm:
            continue
        if now.weekday() not in r.get('days', range(7)):
            continue
        if last_run.get(r['id']) == stamp:
            continue
        last_run[r['id']] = stamp
        due.append(r)
    return due


def pick_profile(profiles, running, foreground):
    """Primeiro perfil ativo da lista (a ordem é a prioridade).
    running: nomes de processo em minúsculas; foreground: nome do app em foco."""
    for p in profiles:
        if not p.get('enabled', True):
            continue
        name = p.get('process', '').lower()
        if not name:
            continue
        if p.get('when') == 'focus':
            if foreground == name:
                return p
        elif name in running:
            return p
    return None


def describe_selection(sel, effects):
    names = {k: n for k, n, *_ in effects}
    mode = sel.get('mode')
    if mode == 'white':
        text = f"Branco {round(sel.get('temperature', 500) / 10)}% frio"
    elif mode == 'effect':
        text = names.get(sel.get('effect'), 'Efeito')
        if sel.get('effect') in ('static', 'breathing', 'flashing', 'chase'):
            text += ' ' + sel.get('colour', '').upper()
    else:
        text = sel.get('colour', '').upper()
    return f"{text} · {sel.get('brightness', 100)}%"


def describe_days(days):
    days = sorted(days)
    if days == list(range(7)):
        return 'Todos os dias'
    if days == list(range(5)):
        return 'Seg a Sex'
    if days == [5, 6]:
        return 'Fim de semana'
    return ', '.join(DAY_NAMES[d] for d in days)


class ProfileSwitcher:
    """Lembra as cores de antes do jogo/app para voltar quando ele fechar."""

    def __init__(self):
        self.active = None  # id do perfil aplicado

    def decide(self, profile):
        """Devolve ('apply', perfil), ('restore', None) ou None se nada mudou."""
        new = profile['id'] if profile else None
        if new == self.active:
            return None
        self.active = new
        return ('apply', profile) if profile else ('restore', None)

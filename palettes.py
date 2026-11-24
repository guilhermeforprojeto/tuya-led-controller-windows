"""Cores sugeridas, com nome, pensadas para LED.

LED não mostra cor escura: o brilho é controlado à parte, então só o tom
(matiz) e a saturação importam. Por isso as sugestões são cores vivas ou
pastéis; as cores do ano da Pantone são aproximações em HEX e, no LED,
aparecem mais vivas que no papel.
"""

GROUPS = [
    ('vivas', 'Vivas', [
        ('Vermelho', '#ff1a1a'), ('Laranja', '#ff6a00'), ('Âmbar', '#ffb000'),
        ('Lima', '#a6ff00'), ('Verde', '#00e05a'), ('Ciano', '#00e1ff'),
        ('Azul', '#1f5bff'), ('Violeta', '#8a2bff'), ('Magenta', '#ff1fd2'),
        ('Rosa', '#ff4d8d')]),
    ('aconchego', 'Aconchego', [
        ('Vela', '#ff8c2e'), ('Pôr do sol', '#ff5a36'), ('Mel', '#ffc24d'),
        ('Pêssego', '#ffb08a'), ('Rosé', '#ff8fa3'), ('Lavanda', '#b79cff'),
        ('Coral', '#ff6f61'), ('Cereja', '#e0245e')]),
    ('foco', 'Foco', [
        ('Gelo', '#d6ecff'), ('Céu', '#6cc4ff'), ('Menta', '#7dffcf'),
        ('Água', '#34d6c9'), ('Lua', '#e8e4ff'), ('Oceano', '#0a84ff'),
        ('Aurora', '#5cffa8'), ('Neblina', '#a9c4e8')]),
    ('pantone', 'Pantone', [
        ('Cloud Dancer · 2026', '#f0eee9'), ('Mocha Mousse · 2025', '#a47864'),
        ('Peach Fuzz · 2024', '#ffbe98'), ('Viva Magenta · 2023', '#be3455'),
        ('Very Peri · 2022', '#6667ab'), ('Illuminating · 2021', '#f5df4d'),
        ('Classic Blue · 2020', '#0f4c81'), ('Living Coral · 2019', '#ff6f61'),
        ('Ultra Violet · 2018', '#5f4b8b'), ('Greenery · 2017', '#88b04b')]),
]

# Atalhos da tela principal e do painel da bandeja (cores que o LED faz bem).
FAVOURITES = ['#8a2bff', '#ff1fd2', '#ff1a1a', '#ff8c2e', '#ffb000', '#00e05a', '#00e1ff', '#1f5bff']

_NAMES = {}
for _, _, colours in GROUPS:
    for name, hex_ in colours:
        _NAMES.setdefault(hex_.lower(), name)


def name_for(hex_colour):
    """Nome da cor se ela for uma das sugestões; senão ''."""
    return _NAMES.get((hex_colour or '').lower(), '')


def remember(recent, hex_colour, limit=8):
    """Põe a cor no começo da lista de recentes, sem repetir."""
    hex_colour = hex_colour.lower()
    return [hex_colour] + [c for c in recent if c.lower() != hex_colour][:limit - 1]

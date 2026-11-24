"""Formas com canto contínuo (squircle), usadas na interface e no ícone.

O arredondado comum é um quarto de círculo colado numa reta; aqui cada canto
é um quarto de superelipse, que começa suave na reta e fecha aos poucos.
"""
import math

EXPONENT = 5      # 2 = círculo; maior = mais "quadrado" no meio do canto
STRETCH = 1.25    # a curva contínua ocupa um trecho maior que o raio nominal
STEPS = 10


def concentric(outer_radius, gap, minimum=4):
    """Raio de dentro para ficar concêntrico ao de fora."""
    return max(outer_radius - gap, minimum)


def squircle_points(x0, y0, x1, y1, radius, steps=STEPS):
    """Pontos de um retângulo com cantos contínuos, em sentido horário."""
    w, h = x1 - x0, y1 - y0
    k = max(0.0, min(radius * STRETCH, w / 2, h / 2))
    if k == 0:
        return [x0, y0, x1, y0, x1, y1, x0, y1]
    e = 2 / EXPONENT
    corners = [(x1 - k, y0 + k, 1, -1, -90), (x1 - k, y1 - k, 1, 1, 0),
               (x0 + k, y1 - k, -1, 1, 90), (x0 + k, y0 + k, -1, -1, 180)]
    points = []
    for cx, cy, sx, sy, start in corners:
        for i in range(steps + 1):
            t = math.radians(start + 90 * i / steps)
            c, s = math.cos(t), math.sin(t)
            points.append(cx + k * math.copysign(abs(c) ** e, c))
            points.append(cy + k * math.copysign(abs(s) ** e, s))
    return points

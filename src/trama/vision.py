"""Visão normal humana: luz e linha de visão; sem IA, mapa narrativo ou Pygame.

PHB 2024, Vision and Light; DMG 2024, p. 45, Line of Sight.
O teste geométrico amostra cantos da origem e pontos do espaço de destino.
Essa discretização é uma aproximação explícita da regra geométrica do DMG.
"""

from dataclasses import dataclass
import logging

from trama.spatial import Grid, Position

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Visibility:
    visible: frozenset[Position]
    lightly_obscured: frozenset[Position] = frozenset()


def _points(p: Position, *, corners_only: bool = False) -> tuple[tuple[float, float], ...]:
    # Evita que a própria parede lateral do observador invalide um raio em t=0.
    inset = 0.000001
    corners = ((p.x + inset, p.y + inset), (p.x + 1 - inset, p.y + inset),
               (p.x + inset, p.y + 1 - inset), (p.x + 1 - inset, p.y + 1 - inset))
    if corners_only:
        return corners
    return (*corners, (p.x + .5, p.y + .5),
            (p.x + inset, p.y + .5), (p.x + 1 - inset, p.y + .5),
            (p.x + .5, p.y + inset), (p.x + .5, p.y + 1 - inset))


def _intersects(start: tuple[float, float], end: tuple[float, float], cell: Position) -> bool:
    """Interseção segmento/retângulo fechado; tocar uma quina também bloqueia."""
    low, high = 0.0, 1.0
    for a, b, minimum in ((start[0], end[0], cell.x), (start[1], end[1], cell.y)):
        delta = b - a
        if abs(delta) < 1e-12:
            if a < minimum or a > minimum + 1:
                return False
            continue
        first, second = (minimum - a) / delta, (minimum + 1 - a) / delta
        low = max(low, min(first, second))
        high = min(high, max(first, second))
        if low > high:
            return False
    return high > 0 and low < 1


def line_of_sight(origin: Position, target: Position, opaque: frozenset[Position]) -> bool:
    if origin == target:
        return True
    blockers = tuple(p for p in opaque if p not in {origin, target}
                     and min(origin.x, target.x) - 1 <= p.x <= max(origin.x, target.x) + 1
                     and min(origin.y, target.y) - 1 <= p.y <= max(origin.y, target.y) + 1)
    return any(
        not any(_intersects(start, end, blocker) for blocker in blockers)
        for start in _points(origin, corners_only=True) for end in _points(target)
    )


def field_of_view(
    grid: Grid, origin: Position, *, opaque: frozenset[Position] = frozenset(),
    dim: frozenset[Position] = frozenset(), dark: frozenset[Position] = frozenset(),
) -> Visibility:
    """Sem cone de orientação ou limite artificial de distância.

    Luz fraca permite ver, com obscurecimento leve. Escuridão é obscurecimento
    pesado para este observador sem sentidos especiais. Superfícies de obstáculos
    podem ser vistas; células além delas não. Não calcula Percepção ou furtividade.
    """
    if not grid.contains(origin):
        raise ValueError("Observador fora do mapa.")
    if dim & dark or any(not grid.contains(p) for p in opaque | dim | dark):
        raise ValueError("Dados de visão inválidos.")
    visible = frozenset(
        p for y in range(grid.height) for x in range(grid.width)
        if (p := Position(x, y)) not in dark and line_of_sight(origin, p, opaque | dark)
    )
    result = Visibility(visible, visible & dim)
    logger.debug("vision.calculated", extra={"data": {"origin": origin, "visible": visible,
                 "lightly_obscured": result.lightly_obscured}})
    return result

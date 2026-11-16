"""Requisitos espaciais publicados pelas ações; preparação sem efeitos.

Cada sessão informa posições que satisfazem a sua ação. Este coordenador só
calcula a caminhada: não abre barreiras, destranca, usa Dash ou gasta poderes.
"""

from dataclasses import dataclass

from trama.application.intents import MovementIntent
from trama.application.routing import path_to_cells
from trama.movement import MovementError
from trama.spatial import Position


@dataclass(frozen=True)
class SpatialRequirement:
    kind: str
    target_id: str
    cells: frozenset[Position]

    def context(self) -> dict:
        return {'kind': self.kind, 'target_id': self.target_id,
                'valid_positions': [[p.x + 1, p.y + 1] for p in sorted(self.cells, key=lambda p: (p.y, p.x))]}


@dataclass(frozen=True)
class PreparedMovement:
    intent: MovementIntent
    path: tuple[Position, ...]


def prepare_movement(session, intent, requirement: SpatialRequirement | None) -> PreparedMovement | None:
    if (requirement is None or not getattr(intent, 'allow_approach', True)
            or session.state.position in requirement.cells):
        return None
    grid = session.navigation_grid()
    try:
        path = path_to_cells(grid, session.state.position, requirement.cells)
    except MovementError:
        if session.scene is None:
            raise
        # Prevê até onde se pode ir quando outra passagem barra o caminho.
        # A execução usa o mapa real e para nela; nenhuma porta é aberta aqui.
        architectural = session.scene.open_passages_grid
        path = path_to_cells(architectural, session.state.position, requirement.cells)
    return PreparedMovement(MovementIntent((), False, '', requirement.target_id), path)

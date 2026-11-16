"""Traduz o estado validado para dados de interpretação, filtrando criaturas ocultas."""

from trama.actions import ActionBudget
from trama.creatures import Creature
from trama.movement import MovementState
from trama.scene import Scene
from trama.spatial import Grid
from trama.vision import Visibility
from trama.distances import CELL_METERS


def build_context(
    grid: Grid, state: MovementState, scene: Scene | None = None,
    creatures: tuple[Creature, ...] = (), visibility: Visibility | None = None,
    budget: ActionBudget = ActionBudget(),
) -> dict:
    visible = visibility.visible if visibility else frozenset()
    context = {
        "map": {"columns": grid.width, "rows": grid.height,
                "distance_unit": "meters", "cell_size_meters": float(CELL_METERS),
                "blocked": [[p.x + 1, p.y + 1] for p in sorted(grid.blocked, key=lambda p: (p.y, p.x))],
                "difficult": [[p.x + 1, p.y + 1] for p in sorted(grid.difficult, key=lambda p: (p.y, p.x))]},
        "character": {"column": state.position.x + 1, "row": state.position.y + 1,
                      "speed_meters": float(state.effective_speed_meters), "remaining_meters": float(state.remaining_meters),
                      "dash_used": state.dash_used, "turn": state.turn,
                      "dash_uses": state.dash_uses, "protected_movement_meters": float(state.free_meters),
                      "species": "human", "darkvision": False,
                      "free_interaction_used": budget.free_interaction_used,
                      "action_used": budget.action_used},
        "visible_creatures": [{"id": c.id, "name": c.name,
                               "number": number,
                               "column": c.position.x + 1, "row": c.position.y + 1,
                               "hostile": c.hostile}
                              for number, c in enumerate(creatures, 1) if c.position in visible],
    }
    if scene is not None:
        if scene.movement_grid != grid:
            raise ValueError("O cenário não corresponde à grade enviada.")
        context["map"]["scene"] = {
            "areas": [{"id": a.id, "name": a.name, "description": a.description,
                       "column": a.x + 1, "row": a.y + 1,
                       "width_meters": float(a.width * CELL_METERS),
                       "height_meters": float(a.height * CELL_METERS)} for a in scene.areas],
            "passages": [{"id": p.id, "name": p.name, "kind": p.kind,
                          "column": p.position.x + 1, "row": p.position.y + 1,
                          "is_open": p.is_open, "locked": p.locked,
                          "visible": p.position in visible, "connects": list(p.connects)}
                         for p in scene.passages],
            "objects": [{"id": o.id, "name": o.name, "kind": o.kind, "description": o.description,
                         "column": o.position.x + 1, "row": o.position.y + 1,
                         "attachment": {"surface": o.attachment.surface, "side": o.attachment.side},
                         "blocks_movement": o.blocks_movement, "blocks_vision": o.blocks_vision,
                         "visible": o.position in visible} for o in scene.objects],
        }
        area = scene.area_at(state.position)
        context["character"]["current_area"] = area.id if area else None
    return context

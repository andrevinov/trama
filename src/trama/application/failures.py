"""Impedimentos auditáveis calculados pela aplicação, sem SDK ou interface."""

from copy import deepcopy
from dataclasses import dataclass

from trama.spatial import Position


def coordinates(position: Position | None) -> list[int] | None:
    return [position.x + 1, position.y + 1] if position is not None else None


def actor_position(session, actor_id: str) -> Position | None:
    if actor_id == session.encounter.player_id:
        return session.state.position
    return next((c.position for c in (*session.creatures, *session.observers) if c.id == actor_id), None)


def action_reference(action, actor_id: str) -> dict:
    return {"actor_id": getattr(action, "actor_id", actor_id),
            "operation": getattr(action, "operation", "move"),
            "target_id": getattr(action, "target_id", None),
            "destination": coordinates(getattr(action, "destination", None))}


@dataclass(frozen=True)
class ExecutionFailure:
    actor_id: str
    actor_name: str
    operation: str
    code: str
    message: str
    cause: str
    origin: Position | None
    destination: Position | None
    position_after: Position | None
    obstacle: dict | None = None
    skipped_actions: tuple[dict, ...] = ()
    target_id: str | None = None

    def context(self) -> dict:
        return {"actor_id": self.actor_id, "actor_name": self.actor_name,
                "operation": self.operation, "code": self.code, "message": self.message,
                "cause": self.cause, "origin": coordinates(self.origin),
                "destination": coordinates(self.destination), "position_after": coordinates(self.position_after),
                "target_id": self.target_id,
                "obstacle": deepcopy(self.obstacle), "skipped_actions": deepcopy(list(self.skipped_actions))}


def action_failure(session, action, message: str, *, origin: Position | None,
                   code: str = "invalid_action", blocked_position: Position | None = None) -> ExecutionFailure:
    """Anota o motivo conhecido e a geometria existente, sem deduzir causas do texto."""
    actor_id = getattr(action, "actor_id", session.encounter.player_id)
    sheet = session.encounter.sheets.get(actor_id)
    observer = next((o for o in session.observers if o.id == actor_id), None)
    destination = getattr(action, "destination", None) or blocked_position
    obstacle = None
    probe = blocked_position or destination
    if probe is not None:
        occupant = next((c for c in (*session.creatures, *session.observers) if c.position == probe and c.id != actor_id), None)
        passage = next((p for p in session.scene.passages if p.position == probe), None) if session.scene else None
        obj = next((o for o in session.scene.objects if o.position == probe and o.blocks_movement), None) if session.scene else None
        if occupant is not None:
            obstacle = {"kind": "occupied_cell", "actor_id": occupant.id, "name": occupant.name,
                        "at_zero_hp": occupant.id in session.encounter.states and session.encounter.states[occupant.id].hp == 0}
        elif probe == session.state.position and actor_id != session.encounter.player_id:
            obstacle = {"kind": "occupied_cell", "actor_id": session.encounter.player_id,
                        "name": session.encounter.player_sheet.name,
                        "at_zero_hp": session.encounter.states[session.encounter.player_id].hp == 0}
        elif passage is not None and not passage.is_open:
            obstacle = {"kind": "closed_passage", "id": passage.id, "name": passage.name}
        elif obj is not None:
            obstacle = {"kind": "scene_object", "id": obj.id, "name": obj.name,
                        "blocks_movement": obj.blocks_movement, "blocks_vision": obj.blocks_vision}
        elif probe in session.grid.blocked:
            obstacle = {"kind": "blocked_cell"}
        elif not session.grid.contains(probe):
            obstacle = {"kind": "out_of_bounds"}
        if obstacle:
            obstacle["position"] = coordinates(probe)
    cause = message
    if code in {"destination_blocked", "blocked_cell"} and obstacle:
        cell = f"({probe.x + 1},{probe.y + 1})"
        if obstacle["kind"] == "occupied_cell":
            cause = f"A casa {cell} está ocupada por {obstacle['name']}" + (" (0 PV)." if obstacle["at_zero_hp"] else ".")
        elif obstacle["kind"] == "closed_passage":
            cause = f"{obstacle['name']} está fechada na casa {cell}."
        elif obstacle["kind"] == "scene_object":
            cause = f"{obstacle['name']} impede a passagem na casa {cell}."
        else:
            cause = f"A casa {cell} é bloqueada no mapa e não pode ser ocupada."
    return ExecutionFailure(actor_id, sheet.name if sheet else observer.name if observer else actor_id,
                            getattr(action, "operation", "move"), code, message, cause,
                            origin, destination, actor_position(session, actor_id), obstacle,
                            target_id=getattr(action, "target_id", None))

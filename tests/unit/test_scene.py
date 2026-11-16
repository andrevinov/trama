from dataclasses import replace

import pytest

from trama.application.session import GameSession
from trama.application.intents import MovementIntent
from trama.movement import Grid, MovementError, MovementRequest, MovementState, Position, apply_movement
from trama.scene import Scene
from trama.application.routing import path_to


def sample_scene():
    return Scene.from_data({
        "width": 11, "height": 7,
        "areas": [
            {"id": "cell", "name": "Cela", "x": 1, "y": 1, "width": 2, "height": 5},
            {"id": "corridor", "name": "Corredor", "x": 4, "y": 1, "width": 3, "height": 5},
            {"id": "guard_room", "name": "Sala dos Guardas", "x": 8, "y": 1, "width": 2, "height": 5},
        ],
        "passages": [
            {"id": "cell_gate", "name": "Grade da Cela", "kind": "gate", "position": [3, 3],
             "is_open": True, "locked": False, "connects": ["cell", "corridor"]},
            {"id": "guard_door", "name": "Porta da Sala dos Guardas", "kind": "door", "position": [7, 3],
             "is_open": False, "locked": False, "connects": ["corridor", "guard_room"]},
        ],
    })


def test_named_gate_stops_on_reachable_side():
    scene = sample_scene()
    session = GameSession(scene.grid, MovementState(Position(1, 3)), scene)
    result = session.execute(MovementIntent((), False, "", "cell_gate"))
    assert result.state.position == Position(2, 3)
    assert result.cost_meters == 1.5
    assert scene.passages[0].is_open


def test_gate_can_be_crossed_to_enter_corridor():
    scene = sample_scene()
    session = GameSession(scene.grid, MovementState(Position(1, 3)), scene)
    result = session.execute(MovementIntent((), False, "", "corridor"))
    assert result.state.position == Position(4, 3)
    assert Position(3, 3) in result.path
    assert result.cost_meters == 4.5


def test_run_to_closed_unlocked_door_stops_outside(enter_turn_mode):
    scene = sample_scene()
    session = GameSession(scene.grid, MovementState(Position(1, 3)), scene)
    enter_turn_mode(session)
    result = session.execute(MovementIntent((), True, "", "guard_door"))
    assert result.state.position == Position(6, 3)
    assert result.state.dash_used
    assert result.state.remaining_meters == 10.5
    assert not scene.passages[1].is_open
    assert not scene.passages[1].locked


def test_closed_door_blocks_room_even_when_unlocked():
    scene = sample_scene()
    session = GameSession(scene.grid, MovementState(Position(6, 3)), scene)
    result = session.execute(MovementIntent((), False, "", "guard_room"))
    assert "fechada" in result.stop_reason
    blocked = apply_movement(scene.grid, session.state, MovementRequest((Position(7, 3),)))
    assert "bloqueada" in blocked.stop_reason
    assert session.state == session.initial_state


def test_approach_door_from_guard_room_uses_inside_face():
    scene = sample_scene()
    assert path_to(scene, Position(9, 3), "guard_door") == (Position(8, 3),)


def test_shortest_route_detours_around_wall_without_cutting_corners():
    scene = sample_scene()
    # Starting near the top of the cell forces a detour to the gate opening.
    path = path_to(scene, Position(1, 1), "corridor")
    result = apply_movement(scene.grid, MovementState(Position(1, 1)), MovementRequest(path))
    assert result.state.position == Position(4, 3)
    assert Position(2, 3) in result.path
    assert Position(3, 3) in result.path
    assert result.cost_meters == 6


def test_route_uses_lowest_movement_cost_not_fewest_squares():
    scene = sample_scene()
    # Three expensive cells make a small detour preferable.
    grid = Grid(5, 5, difficult=frozenset(Position(x, 2) for x in (1, 2, 3)))
    from trama.scene import Area
    scene = Scene(grid, (Area("goal", "Destino", 4, 2, 1, 1),), ())
    path = path_to(scene, Position(0, 2), "goal")
    result = apply_movement(grid, MovementState(Position(0, 2)), MovementRequest(path))
    assert result.cost_meters == 6
    assert all(p not in grid.difficult for p in path)


def test_named_route_still_requires_remaining_movement(enter_turn_mode):
    scene = sample_scene()
    session = GameSession(scene.grid, MovementState(Position(1, 3), speed_meters=3), scene)
    enter_turn_mode(session)
    result = session.execute(MovementIntent((), False, "", "guard_door"))
    assert "insuficiente" in result.stop_reason
    assert session.state.position == Position(3, 3)
    assert session.state.remaining_meters == 0


def test_arriving_at_current_destination_is_a_noop():
    scene = sample_scene()
    session = GameSession(scene.grid, MovementState(Position(2, 3)), scene)
    result = session.execute(MovementIntent((), False, "", "cell_gate"))
    assert result.cost_meters == 0
    assert session.state == session.initial_state


def test_unknown_destination_and_target_without_scene_are_rejected():
    scene = sample_scene()
    with pytest.raises(MovementError, match="não existe"):
        path_to(scene, Position(1, 3), "invented_room")
    session = GameSession(scene.grid, MovementState(Position(1, 3)))
    with pytest.raises(MovementError, match="não tem destinos"):
        session.execute(MovementIntent((), False, "", "cell_gate"))


def test_destinations_cannot_override_named_route_with_segments():
    from trama.application.intents import MovementSegment
    with pytest.raises(ValueError, match="não os dois"):
        MovementIntent((MovementSegment("north", 1),), False, "", "cell_gate")


def test_scene_validates_passage_states_and_identifiers():
    scene = sample_scene()
    with pytest.raises(ValueError, match="identificadores únicos"):
        replace(scene, areas=(*scene.areas, scene.areas[0]))
    with pytest.raises(ValueError, match="bloqueio"):
        replace(scene, passages=(replace(scene.passages[0], is_open=False), scene.passages[1]))

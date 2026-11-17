"""Objetos do mapa atravessam a sessão, contexto e Pygame reais, sem rede."""

from dataclasses import replace
import json
from pathlib import Path

import pygame
import pytest

from conftest import sourced_plan
from trama.application.authorization import PlanAuthorizationError, validate_player_plan
from trama.application.conversation import Conversation
from trama.application.dungeon import DungeonSession
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, MovementSegment, RuleIntent
from trama.application.interpretation_context import compact_context
from trama.application.routing import path_to
from trama.application.preparation import SpatialRequirement, prepare_movement
from trama.application.session import GameSession
from trama.application.world import WorldAction
from trama.application.world_resolution import WorldExecutor
from trama.creatures import Creature
from trama.movement import MovementError, MovementState
from trama.scene import Scene
from trama.spatial import Position
from trama.ui.movement_window import ACCENT, GOLD, GRID_ORIGIN, WINDOW_SIZE, MovementWindow

SCENARIO = Path(__file__).resolve().parents[2] / 'src/trama/scenarios/dungeon_escape.json'


def corridor_scene(*, blocks_movement, blocks_vision):
    return Scene.from_data({
        'width': 7, 'height': 3,
        'areas': [dict(id='a', name='A', x=0, y=1, width=3, height=1),
                  dict(id='b', name='B', x=4, y=1, width=3, height=1)],
        'passages': [dict(id='door', name='Porta', kind='door', position=[3, 1],
                          is_open=True, locked=False, connects=['a', 'b'])],
        'objects': [dict(id='fixture', name='Obstáculo', position=[3, 1],
                         blocks_movement=blocks_movement, blocks_vision=blocks_vision)],
    })


def test_real_dungeon_wall_torches_allow_standing_in_all_their_cells(dice):
    session = DungeonSession.from_data(json.loads(SCENARIO.read_text()), roller=dice(20))
    torches = session.scene.objects
    assert len(torches) == 4
    session.execute(RuleIntent('hide'))
    session.execute(MovementIntent((), False, '', 'corridor'))
    for torch in reversed(torches):
        assert torch.attachment.surface == 'wall' and torch.attachment.side == 'east'
        # Visitar a mesma coluna de cada tocha, sem trocar cenário ou regras.
        dx = torch.position.x - session.state.position.x
        dy = torch.position.y - session.state.position.y
        segments = tuple(MovementSegment(direction, abs(amount))
                         for amount, direction in ((dx, 'east' if dx > 0 else 'west'),
                                                   (dy, 'south' if dy > 0 else 'north')) if amount)
        result = session.execute(MovementIntent(segments, False, ''))
        assert result.stop_reason is None
        assert session.state.position == torch.position
        assert torch.position not in session.grid.blocked | session.scene.opaque


@pytest.mark.parametrize('blocks_movement,blocks_vision', [(True, False), (False, True), (True, True)])
def test_session_resolves_object_effects_and_explains_actual_blocker(blocks_movement, blocks_vision):
    scene = corridor_scene(blocks_movement=blocks_movement, blocks_vision=blocks_vision)
    session = GameSession(scene.movement_grid, MovementState(Position(2, 1)), scene)
    assert (Position(4, 1) in session.visibility.visible) == (not blocks_vision)
    conversation = Conversation(session)
    report = conversation.execute(ActionPlan((MovementIntent((MovementSegment('east', 2),), False, ''),)))
    if blocks_movement:
        assert session.state.position == Position(2, 1)
        assert report.status == 'blocked'
        assert report.failures[0].obstacle['id'] == 'fixture'
        assert 'Obstáculo' in report.failures[0].cause
    else:
        assert session.state.position == Position(4, 1)
        assert report.progress


def test_named_routing_does_not_plan_through_blocking_object_in_open_passage():
    scene = corridor_scene(blocks_movement=True, blocks_vision=False)
    with pytest.raises(MovementError, match='caminho'):
        path_to(scene, Position(2, 1), 'b')


@pytest.mark.parametrize('blocks_movement', [False, True])
def test_contextual_route_and_npc_route_share_object_collision(blocks_movement):
    scene = corridor_scene(blocks_movement=blocks_movement, blocks_vision=False)
    session = GameSession(scene.movement_grid, MovementState(Position(0, 1)), scene,
                          (Creature('guard', 'Guarda', Position(6, 1), hostile=False),))
    # Este caso isola colisões; uma abordagem hostil é verificada em test_parley.
    requirement = SpatialRequirement('inside', 'b', frozenset({Position(5, 1)}))
    action = WorldAction('guard', 'move', 'O guarda avança.', destination=Position(1, 1))
    if blocks_movement:
        with pytest.raises(MovementError):
            prepare_movement(session, DoorIntent('open', 'door'), requirement)
        with pytest.raises(MovementError):
            WorldExecutor(session).execute(action)
        assert session.creatures[0].position == Position(6, 1)
    else:
        assert prepare_movement(session, DoorIntent('open', 'door'), requirement).path[-1] == Position(5, 1)
        assert WorldExecutor(session).execute(action)['changed']
        assert session.creatures[0].position == Position(1, 1)


def test_door_operations_and_reset_keep_objects_blocking():
    scene = corridor_scene(blocks_movement=True, blocks_vision=False)
    session = GameSession(scene.movement_grid, MovementState(Position(2, 1)), scene)
    session.execute(DoorIntent('close', 'door'))
    assert Position(3, 1) in session.grid.blocked & session.scene.opaque
    session.execute(DoorIntent('open', 'door'))
    assert Position(3, 1) in session.grid.blocked
    assert Position(3, 1) not in session.scene.opaque
    session.reset()
    assert session.grid == scene.movement_grid
    assert session.scene.objects == scene.objects


def test_ai_contexts_and_map_projection_describe_visible_wall_torches():
    session = DungeonSession.from_data(json.loads(SCENARIO.read_text()))
    context = session.interpreter_context()
    all_objects = context['world']['map']['scene']['objects']
    assert len(all_objects) == 4
    visible = [o for o in all_objects if o['visible']]
    assert visible and len(visible) < len(all_objects)
    assert compact_context(context)['map']['scene']['objects'] == visible
    perception = Conversation(session).narration_context(initial=True)['perception']
    assert perception['visible_scene_objects'] == visible
    markers = [m for m in session.map_view()['markers'] if m['kind'] == 'scene_object']
    assert {m['id'] for m in markers} == {o['id'] for o in visible}
    for obj in visible:
        assert obj['attachment'] == dict(surface='wall', side='east')
        assert not obj['blocks_movement'] and not obj['blocks_vision']
    prompt = 'Vou até a tocha.'
    plan = sourced_plan(ActionPlan((MovementIntent((), False, '', visible[0]['id']),)), prompt)
    validate_player_plan(prompt, plan, context)
    report = Conversation(session).execute(plan)
    assert report.progress
    hidden_id = next(o['id'] for o in all_objects if not o['visible'])
    hidden = sourced_plan(ActionPlan((MovementIntent((), False, '', hidden_id),)), prompt)
    with pytest.raises(PlanAuthorizationError, match='visível'):
        validate_player_plan(prompt, hidden, context)


def test_pygame_draws_wall_torch_at_edge_leaving_character_center_clear(monkeypatch):
    monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
    pygame.init()
    try:
        screen = pygame.display.set_mode(WINDOW_SIZE)
        session = DungeonSession.from_data(json.loads(SCENARIO.read_text()))
        # Snapshot visual: personagem na casa da tocha mais próxima.
        torch = session.scene.objects[-1]
        session.state = replace(session.state, position=torch.position)
        window = MovementWindow(session, None, 'offline')
        window.draw(screen)
        size = window.cell_size
        cx = GRID_ORIGIN[0] + torch.position.x * size + size // 2
        cy = GRID_ORIGIN[1] + torch.position.y * size + size // 2
        assert screen.get_at((cx, cy))[:3] == ACCENT
        assert screen.get_at((cx + size // 2 - 2, cy))[:3] == GOLD
    finally:
        pygame.quit()

"""Fixação e efeitos espaciais independentes, sem IA ou interface."""

from dataclasses import replace
from decimal import Decimal

import pytest

from trama.movement import MovementError, step_cost
from trama.scene import Area, Attachment, Passage, Scene, SceneObject
from trama.spatial import Grid, Position
from trama.vision import field_of_view


def room(*objects):
    cells = frozenset(Position(x, y) for y in range(5) for x in range(7))
    area = Area('room', 'Sala', 1, 1, 5, 3)
    return Scene(Grid(7, 5, cells - area.cells), (area,), (), objects=objects)


@pytest.mark.parametrize('blocks_movement,blocks_vision', [
    (False, False), (True, False), (False, True), (True, True),
])
def test_object_movement_and_visibility_are_independent(blocks_movement, blocks_vision):
    obj = SceneObject('fixture', 'Objeto', Position(3, 2),
                      blocks_movement=blocks_movement, blocks_vision=blocks_vision)
    scene = room(obj)
    assert obj.position not in scene.grid.blocked  # Terreno não se confunde com objeto.
    assert (obj.position in scene.movement_grid.blocked) == blocks_movement
    if blocks_movement:
        with pytest.raises(MovementError):
            step_cost(scene.movement_grid, Position(2, 2), obj.position)
    else:
        assert step_cost(scene.movement_grid, Position(2, 2), obj.position) == Decimal('1.5')
    view = field_of_view(scene.movement_grid, Position(2, 2), opaque=scene.opaque)
    assert (Position(4, 2) in view.visible) == (not blocks_vision)
    assert obj.position in view.visible  # A superfície do obstáculo continua visível.


@pytest.mark.parametrize('position,side', [
    (Position(3, 1), 'north'), (Position(5, 2), 'east'),
    (Position(3, 3), 'south'), (Position(1, 2), 'west'),
])
def test_wall_attachment_preserves_floor_and_wall(position, side):
    obj = SceneObject('torch', 'Tocha', position, 'torch', Attachment('wall', side))
    scene = room(obj)
    assert scene.movement_grid == scene.grid
    assert scene.opaque == room().opaque
    assert obj.position not in scene.movement_grid.blocked


@pytest.mark.parametrize('surface,side', [
    ('ceiling', None), ('wall', None), ('wall', 'up'), ('floor', 'east'),
])
def test_invalid_attachment_is_rejected(surface, side):
    with pytest.raises(ValueError, match='Fixação'):
        Attachment(surface, side)


@pytest.mark.parametrize('obj', [
    SceneObject('fixture', 'Objeto', Position(7, 2)),
    SceneObject('fixture', 'Objeto', Position(0, 2)),
    SceneObject('fixture', 'Objeto', Position(3, 2), attachment=Attachment('wall', 'east')),
])
def test_object_requires_floor_and_wall_when_attached(obj):
    with pytest.raises(ValueError):
        room(obj)


def test_object_ids_share_namespace_with_named_places():
    with pytest.raises(ValueError, match='identificadores únicos'):
        room(SceneObject('room', 'Objeto', Position(3, 2)))


@pytest.mark.parametrize('field', ['blocks_movement', 'blocks_vision'])
def test_blocking_flags_must_be_booleans(field):
    with pytest.raises(ValueError, match='Objeto'):
        SceneObject('fixture', 'Objeto', Position(3, 2), **{field: 'false'})


def test_coincident_objects_combine_effects_and_do_not_erase_difficult_terrain():
    position = Position(3, 2)
    scene = room(SceneObject('fence', 'Cerca', position, blocks_movement=True),
                 SceneObject('curtain', 'Cortina', position, blocks_vision=True))
    scene = replace(scene, grid=replace(scene.grid, difficult=frozenset({position})))
    assert position in scene.movement_grid.blocked
    assert position in scene.opaque
    assert position not in scene.movement_grid.difficult
    assert position in replace(scene, objects=()).movement_grid.difficult


@pytest.mark.parametrize('kind', ['door', 'gate'])
def test_door_changes_and_route_forecast_preserve_object_layers(kind):
    data = {
        'width': 7, 'height': 3,
        'areas': [dict(id='a', name='A', x=0, y=1, width=3, height=1),
                  dict(id='b', name='B', x=4, y=1, width=3, height=1)],
        'passages': [dict(id='passage', name='Passagem', kind=kind, position=[3, 1],
                          is_open=False, locked=False, connects=['a', 'b'])],
        'objects': [dict(id='box', name='Caixa', position=[3, 1],
                         blocks_movement=True, blocks_vision=True)],
    }
    closed = Scene.from_data(data)
    opened = closed.with_passage('passage', True)
    reclosed = opened.with_passage('passage', False)
    for scene in (closed, opened, reclosed):
        assert Position(3, 1) in scene.movement_grid.blocked
        assert Position(3, 1) in scene.opaque
        assert Position(3, 1) in scene.open_passages_grid.blocked
    assert Position(3, 1) not in opened.grid.blocked


def test_transparent_object_does_not_make_closed_door_transparent():
    a = Area('a', 'A', 0, 0, 1, 1)
    b = Area('b', 'B', 2, 0, 1, 1)
    passage = Passage('door', 'Porta', 'door', Position(1, 0), False, False, ('a', 'b'))
    scene = Scene(Grid(3, 1, frozenset({passage.position})), (a, b), (passage,),
                  objects=(SceneObject('fence', 'Cerca', passage.position, blocks_movement=True),))
    assert passage.position in scene.opaque
    assert passage.position not in scene.with_passage('door', True).opaque


def test_wall_may_be_map_boundary():
    obj = SceneObject('torch', 'Tocha', Position(0, 0), 'torch', Attachment('wall', 'west'))
    assert Scene(Grid(2, 2), (), (), objects=(obj,)).movement_grid == Grid(2, 2)

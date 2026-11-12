import pytest

from trama.spatial import Grid, Position
from trama.vision import field_of_view, line_of_sight


def test_open_lit_space_has_no_cone_or_fixed_distance_limit():
    grid = Grid(40, 3)
    view = field_of_view(grid, Position(20, 1))
    assert len(view.visible) == 120
    assert Position(0, 1) in view.visible
    assert Position(39, 1) in view.visible


def test_wall_surface_is_visible_but_space_behind_it_is_not():
    wall = frozenset(Position(2, y) for y in range(5))
    view = field_of_view(Grid(5, 5, blocked=wall), Position(0, 2), opaque=wall)
    assert Position(2, 2) in view.visible
    assert Position(3, 2) not in view.visible
    assert Position(4, 0) not in view.visible


def test_pillar_casts_shadow_without_hiding_whole_room():
    pillar = frozenset({Position(2, 2)})
    view = field_of_view(Grid(5, 5), Position(0, 2), opaque=pillar)
    assert Position(4, 2) not in view.visible
    assert Position(4, 0) in view.visible


def test_closed_diagonal_corner_does_not_leak_vision():
    walls = frozenset({Position(1, 0), Position(0, 1)})
    assert not line_of_sight(Position(0, 0), Position(1, 1), walls)


def test_dim_light_is_visible_and_marked_lightly_obscured():
    dim = frozenset({Position(2, 1)})
    view = field_of_view(Grid(3, 3), Position(1, 1), dim=dim)
    assert dim <= view.visible
    assert view.lightly_obscured == dim


def test_normal_human_vision_cannot_see_in_darkness():
    dark = frozenset({Position(2, 1)})
    view = field_of_view(Grid(3, 3), Position(1, 1), dark=dark)
    assert Position(2, 1) not in view.visible


def test_heavily_obscured_strip_blocks_normal_vision():
    dark = frozenset(Position(2, y) for y in range(3))
    view = field_of_view(Grid(5, 3), Position(0, 1), dark=dark)
    assert Position(4, 1) not in view.visible


@pytest.mark.parametrize("origin,kwargs", [
    (Position(-1, 0), {}),
    (Position(0, 0), {"opaque": frozenset({Position(3, 0)})}),
    (Position(0, 0), {"dim": frozenset({Position(1, 1)}), "dark": frozenset({Position(1, 1)})}),
])
def test_invalid_vision_inputs(origin, kwargs):
    with pytest.raises(ValueError):
        field_of_view(Grid(3, 3), origin, **kwargs)

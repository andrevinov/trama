import pytest

from trama.reactions import provokes_opportunity
from trama.spatial import Position


@pytest.mark.parametrize("origin,destination,options,expected", [
    ((1, 0), (2, 0), {}, True),
    ((1, 1), (2, 2), {}, True),
    ((2, 0), (1, 0), {}, False),
    ((1, 0), (1, 1), {}, False),
    ((1, 0), (2, 0), {"visible": False}, False),
    ((1, 0), (2, 0), {"protected": True}, False),
    ((1, 0), (2, 0), {"uses_movement": False}, False),
])
def test_opportunity_only_before_visible_creature_leaves_reach(origin, destination, options, expected):
    assert provokes_opportunity(Position(0, 0), Position(*origin), Position(*destination),
                                **{"visible": True, **options}) is expected

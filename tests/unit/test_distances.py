from decimal import Decimal

import pytest

from trama.distances import feet_to_meters, format_meters, meters, meters_to_squares, to_meters
from trama.movement import MovementState
from trama.spatial import Position


@pytest.mark.parametrize("feet,expected", [(5, "1.5"), (15, "4.5"), (30, "9"), (60, "18")])
def test_feet_conversion_uses_dnd_convention(feet, expected):
    assert feet_to_meters(feet) == Decimal(expected)


@pytest.mark.parametrize("distance,unit", [(3, "meters"), (10, "feet"), (2, "squares")])
def test_all_input_units_normalize_to_meters(distance, unit):
    result = to_meters(distance, unit)
    assert result == Decimal("3")
    assert meters_to_squares(result) == 2


def test_default_input_unit_is_meters():
    assert to_meters(9) == Decimal("9")


def test_fractional_distances_are_exact_and_not_rounded_to_squares():
    state = MovementState(Position(0, 0), speed_meters=2.1, spent_meters=1.5)
    assert state.remaining_meters == Decimal("0.6")
    with pytest.raises(ValueError, match="casas inteiras"):
        meters_to_squares(2)


@pytest.mark.parametrize("value", [True, -1, float("inf"), float("nan"), "9", None])
def test_invalid_meter_values_are_rejected(value):
    with pytest.raises(ValueError):
        meters(value)
    with pytest.raises(ValueError):
        MovementState(Position(0, 0), speed_meters=value)


@pytest.mark.parametrize("value,expected", [(0, "0 m"), (9, "9 m"), (1.5, "1,5 m"),
                                           (Decimal("7.500"), "7,5 m"), (30, "30 m")])
def test_display_uses_meters_with_decimal_comma(value, expected):
    assert format_meters(value) == expected


def test_unknown_unit_is_rejected():
    with pytest.raises(ValueError, match="Unidade"):
        to_meters(1, "yards")

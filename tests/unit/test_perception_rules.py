"""Contratos de sentidos e valores passivos independentes da aplicação."""

from decimal import Decimal

import pytest

from trama.perception import Noise, Senses, observers_from_data
from trama.spatial import Position


@pytest.mark.parametrize('values', [
    {'sight_range_meters': -1}, {'hearing_range_meters': True}, {'darkvision_meters': float('nan')},
    {'wake_range_meters': -1}, {'perception_bonus': True}, {'sleeping': 1},
    {'searching': 'yes'}, {'response': 'attack'}, {'can_hear': None},
])
def test_invalid_sensory_profiles_are_rejected(values):
    with pytest.raises(ValueError):
        Senses(**values)


@pytest.mark.parametrize('advantage,disadvantage,total', [(False, False, 13), (True, False, 18), (False, True, 8), (True, True, 13)])
def test_passive_uses_bonus_and_cancellation_of_advantage(advantage, disadvantage, total):
    assert Senses(advantage=advantage, disadvantage=disadvantage).passive(3) == total


def test_hearing_reference_and_noise_categories_are_explicit_and_deterministic():
    senses = Senses()
    assert senses.sight_range_meters is None
    assert [senses.hearing_range_meters * Noise('p', Position(0, 0), volume).multiplier
            for volume in ('quiet', 'normal', 'loud')] == [Decimal('10.5'), Decimal('21'), Decimal('105')]


def test_noncombat_observer_has_its_own_profile_and_bonus_without_fighter():
    observer, = observers_from_data([{'id': 'civilian', 'name': 'Civil', 'position': [2, 3],
                                     'senses': {'perception_bonus': 4, 'sleeping': True}}])
    assert observer.senses.passive(observer.senses.perception_bonus) == 14
    assert observer.senses.sleeping and observer.position == Position(2, 3)

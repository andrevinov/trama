"""Capacidades sensoriais e estímulos; sem cenário, ficha de classe ou IA.

PHB/DMG 2024: Passive Perception, Hide, Search e Audible Distance.
Alcances auditivos fixos usam 7 como referência de 2d6; política do Trama.
"""

from dataclasses import asdict, dataclass
from decimal import Decimal

from trama.distances import meters
from trama.spatial import Position


@dataclass(frozen=True)
class Senses:
    sight_range_meters: Decimal | None = None
    hearing_range_meters: Decimal = Decimal('21')
    darkvision_meters: Decimal = Decimal('0')
    perception_bonus: int | None = None
    can_see: bool = True
    can_hear: bool = True
    advantage: bool = False
    disadvantage: bool = False
    sleeping: bool = False
    searching: bool = False
    wake_range_meters: Decimal = Decimal('9')
    response: str = 'observe'

    def __post_init__(self):
        for name in ('sight_range_meters', 'hearing_range_meters', 'darkvision_meters', 'wake_range_meters'):
            value = getattr(self, name)
            if name != 'sight_range_meters' or value is not None:
                object.__setattr__(self, name, meters(value))
        if (self.perception_bonus is not None and type(self.perception_bonus) is not int
                or any(type(getattr(self, name)) is not bool for name in
                       ('can_see', 'can_hear', 'advantage', 'disadvantage', 'sleeping', 'searching'))
                or self.response not in {'observe', 'challenge'}):
            raise ValueError('Capacidades sensoriais inválidas.')

    def passive(self, bonus, *, visual_disadvantage=False):
        advantage = self.advantage
        disadvantage = self.disadvantage or visual_disadvantage
        return 10 + bonus + (5 if advantage and not disadvantage else
                             -5 if disadvantage and not advantage else 0)

    def context(self, bonus):
        return {**{k: float(v) if isinstance(v, Decimal) else v for k, v in asdict(self).items()},
                'perception_bonus': bonus, 'passive_perception': self.passive(bonus)}


@dataclass(frozen=True)
class Observer:
    """NPC sem ficha de combate, como um prisioneiro ou civil."""
    id: str
    name: str
    position: Position
    senses: Senses = Senses(perception_bonus=0)

    def __post_init__(self):
        if (not isinstance(self.id, str) or not self.id or not isinstance(self.name, str) or not self.name
                or not isinstance(self.position, Position) or not isinstance(self.senses, Senses)):
            raise ValueError('Observador inválido.')


def observers_from_data(data):
    return tuple(Observer(item['id'], item['name'], Position(*item['position']),
                          Senses(**{'perception_bonus': 0, **item.get('senses', {})})) for item in data)


@dataclass(frozen=True)
class Noise:
    actor_id: str
    position: Position
    volume: str = 'normal'
    reason: str = 'Ruído.'

    def __post_init__(self):
        if (not isinstance(self.actor_id, str) or not self.actor_id or not isinstance(self.position, Position)
                or self.volume not in {'quiet', 'normal', 'loud'} or not self.reason.strip()):
            raise ValueError('Estímulo auditivo inválido.')

    @property
    def multiplier(self):
        return {'quiet': Decimal('.5'), 'normal': Decimal('1'), 'loud': Decimal('5')}[self.volume]

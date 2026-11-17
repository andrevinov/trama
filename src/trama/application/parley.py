"""Abordagem e Influence antes de combate; contratos comuns a qualquer cenário."""

from dataclasses import dataclass

from trama.spatial import Position


@dataclass(frozen=True)
class Parley:
    actor_id: str
    demand: str
    player_position: Position
    npc_position: Position
    status: str = 'pending'

    def context(self):
        return dict(actor_id=self.actor_id, demand=self.demand, status=self.status,
                    player_position=[self.player_position.x + 1, self.player_position.y + 1],
                    npc_position=[self.npc_position.x + 1, self.npc_position.y + 1])


@dataclass(frozen=True)
class InfluenceRequest:
    willingness: str
    skill: str | None = None
    attitude: str = 'indifferent'

    def __post_init__(self):
        if (self.willingness not in {'willing', 'unwilling', 'hesitant'}
                or self.attitude not in {'friendly', 'indifferent', 'hostile'}
                or (self.willingness == 'hesitant') != (self.skill is not None)
                or self.skill not in {None, 'persuasion', 'deception', 'intimidation', 'performance'}):
            raise ValueError('Julgamento de Influence inválido.')

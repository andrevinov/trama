"""Abordagem e Influence antes de combate; contratos comuns a qualquer cenário."""

from dataclasses import dataclass
from copy import deepcopy

from trama.spatial import Position
from trama.social import DispositionAssessment


@dataclass(frozen=True)
class Parley:
    actor_id: str
    demand: str
    player_position: Position
    npc_position: Position
    status: str = 'pending'
    concession: dict | None = None

    def context(self):
        return dict(actor_id=self.actor_id, demand=self.demand, status=self.status,
                    player_position=[self.player_position.x + 1, self.player_position.y + 1],
                    npc_position=[self.npc_position.x + 1, self.npc_position.y + 1], concession=deepcopy(self.concession))


@dataclass(frozen=True)
class InfluenceRequest:
    willingness: str | None = None
    skill: str | None = None
    attitude: str = 'indifferent'
    assessment: DispositionAssessment | None = None

    def __post_init__(self):
        if (self.willingness not in {None, 'willing', 'unwilling', 'hesitant'}
                or self.attitude not in {'friendly', 'indifferent', 'hostile'}
                or self.assessment is not None and not isinstance(self.assessment, DispositionAssessment)
                or self.skill not in {None, 'persuasion', 'deception', 'intimidation', 'performance'}):
            raise ValueError('Julgamento de Influence inválido.')

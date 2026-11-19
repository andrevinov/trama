"""Decisões do Mundo; contratos sem SDK, Pygame ou alterações de estado."""

from dataclasses import dataclass
from typing import Protocol

from trama.spatial import Position
from trama.application.parley import InfluenceRequest
from trama.difficulty import Adjudication
from trama.agency import IntentDecision
from trama.conversation_state import ConversationUpdate
from trama.opinions import OptionAssessment
from trama.relationships import RelationshipEpisode
from trama.bonds import BondUpdate


class WorldError(ValueError):
    pass


@dataclass(frozen=True)
class PerceptionCheck:
    actor_id: str
    dc: int
    reason: str

    def __post_init__(self):
        if (not isinstance(self.actor_id, str) or not self.actor_id or type(self.dc) is not int
                or not 1 <= self.dc <= 30 or not isinstance(self.reason, str) or not self.reason.strip()):
            raise WorldError("Teste de Percepção do Mundo inválido.")


@dataclass(frozen=True)
class WorldAction:
    actor_id: str
    operation: str
    text: str
    target_id: str | None = None
    destination: Position | None = None
    weapon: str = "greatsword"
    influence: InfluenceRequest | None = None
    volume: str = "normal"
    memory_ids: tuple[str, ...] = ()
    conversation: ConversationUpdate | None = None

    def __post_init__(self):
        if (self.conversation is not None and (not isinstance(self.conversation, ConversationUpdate)
                or self.operation != 'say')
                or not isinstance(self.memory_ids, tuple) or len(self.memory_ids) > 6
                or any(not isinstance(id, str) or not id or len(id) > 160 for id in self.memory_ids)
                or len(set(self.memory_ids)) != len(self.memory_ids)
                or self.memory_ids and self.operation not in {'say', 'influence'}
                or not isinstance(self.actor_id, str) or not self.actor_id
                or self.volume not in {'quiet', 'normal', 'loud'}
                or (self.operation != 'say' and self.volume != 'normal')
                or self.operation not in {"describe", "say", "move", "open", "close", "attack", "wait", "start_conflict", "end_conflict", "parley", "influence", "search", "resume_activity"}
                or not isinstance(self.text, str) or not self.text.strip() or len(self.text) > 2000
                or self.weapon not in {"greatsword", "flail", "javelin", "longsword", "unarmed"}
                or (self.operation == "move") != isinstance(self.destination, Position)
                or (self.target_id is not None and (not isinstance(self.target_id, str) or not self.target_id))
                or (self.influence is not None and not isinstance(self.influence, InfluenceRequest))
                or (self.operation == "influence") != isinstance(self.influence, InfluenceRequest)
                or (self.operation in {"open", "close", "attack", "search"}) != (self.target_id is not None)):
            raise WorldError("Ação do Mundo inválida.")


@dataclass(frozen=True)
class WorldReaction:
    step_index: int
    after_squares: int | None
    actions: tuple[WorldAction, ...]
    interrupt: bool = False
    reason: str = ""
    check: PerceptionCheck | None = None
    opinions: tuple[OptionAssessment, ...] = ()
    episodes: tuple[RelationshipEpisode, ...] = ()
    bonds: tuple[BondUpdate, ...] = ()

    def __post_init__(self):
        if (type(self.step_index) is not int or not 0 <= self.step_index < 10
                or (self.after_squares is not None and (type(self.after_squares) is not int or self.after_squares < 0))
                or not 0 <= len(self.actions) <= 10 or not (self.actions or self.opinions or self.episodes or self.bonds)
                or not isinstance(self.bonds, tuple) or len(self.bonds) > 8
                or any(not isinstance(b, BondUpdate) for b in self.bonds)
                or not isinstance(self.episodes, tuple) or len(self.episodes) > 8
                or any(not isinstance(e, RelationshipEpisode) for e in self.episodes)
                or not isinstance(self.opinions, tuple) or len(self.opinions) > 4
                or any(not isinstance(o, OptionAssessment) for o in self.opinions)
                or (self.opinions or self.episodes or self.bonds) and (self.after_squares is not None or self.check is not None)
                or type(self.interrupt) is not bool
                or not all(isinstance(action, WorldAction) for action in self.actions)
                or not isinstance(self.reason, str) or (self.interrupt and not self.reason.strip())
                or (self.check is not None and not isinstance(self.check, PerceptionCheck))):
            raise WorldError("Resposta do Mundo inválida.")


@dataclass(frozen=True)
class WorldPlan:
    reactions: tuple[WorldReaction, ...] = ()
    adjudications: tuple[Adjudication, ...] = ()
    intent: IntentDecision | None = None

    def __post_init__(self):
        if self.intent is not None and not isinstance(self.intent, IntentDecision):
            raise WorldError('Intenção do NPC inválida.')
        if len(self.reactions) > 10 or not all(isinstance(r, WorldReaction) for r in self.reactions):
            raise WorldError("O Mundo excedeu o limite de respostas por mensagem.")
        if (not isinstance(self.adjudications, tuple) or len(self.adjudications) > 32
                or any(not isinstance(a, Adjudication) for a in self.adjudications)
                or len({a.request_id for a in self.adjudications}) != len(self.adjudications)):
            raise WorldError('Avaliações de dificuldade inválidas ou repetidas.')


class WorldDirector(Protocol):
    def decide(self, context: dict) -> WorldPlan: ...

"""Decisões do Mundo; contratos sem SDK, Pygame ou alterações de estado."""

from dataclasses import dataclass
from typing import Protocol

from trama.spatial import Position


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

    def __post_init__(self):
        if (not isinstance(self.actor_id, str) or not self.actor_id
                or self.operation not in {"describe", "say", "move", "open", "close", "attack", "wait", "start_conflict", "end_conflict"}
                or not isinstance(self.text, str) or not self.text.strip() or len(self.text) > 2000
                or self.weapon not in {"greatsword", "flail", "javelin", "longsword", "unarmed"}
                or (self.operation == "move") != isinstance(self.destination, Position)
                or (self.target_id is not None and (not isinstance(self.target_id, str) or not self.target_id))
                or (self.operation in {"open", "close", "attack"}) != (self.target_id is not None)):
            raise WorldError("Ação do Mundo inválida.")


@dataclass(frozen=True)
class WorldReaction:
    step_index: int
    after_squares: int | None
    actions: tuple[WorldAction, ...]
    interrupt: bool = False
    reason: str = ""
    check: PerceptionCheck | None = None

    def __post_init__(self):
        if (type(self.step_index) is not int or not 0 <= self.step_index < 10
                or (self.after_squares is not None and (type(self.after_squares) is not int or self.after_squares < 0))
                or not 1 <= len(self.actions) <= 10 or type(self.interrupt) is not bool
                or not all(isinstance(action, WorldAction) for action in self.actions)
                or not isinstance(self.reason, str) or (self.interrupt and not self.reason.strip())
                or (self.check is not None and not isinstance(self.check, PerceptionCheck))):
            raise WorldError("Resposta do Mundo inválida.")


@dataclass(frozen=True)
class WorldPlan:
    reactions: tuple[WorldReaction, ...] = ()

    def __post_init__(self):
        if len(self.reactions) > 10 or not all(isinstance(r, WorldReaction) for r in self.reactions):
            raise WorldError("O Mundo excedeu o limite de respostas por mensagem.")


class WorldDirector(Protocol):
    def decide(self, context: dict) -> WorldPlan: ...

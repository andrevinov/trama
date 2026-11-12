"""Contratos das intenções, independentes do provedor de IA e dos executores."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from trama.distances import CELL_METERS, meters


DIRECTIONS = {
    "north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0),
    "northeast": (1, -1), "northwest": (-1, -1),
    "southeast": (1, 1), "southwest": (-1, 1),
}


@dataclass(frozen=True)
class MovementSegment:
    direction: str
    squares: int
    remainder_meters: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.direction not in DIRECTIONS:
            raise ValueError("Direção inválida.")
        object.__setattr__(self, "remainder_meters", meters(self.remainder_meters))
        if (type(self.squares) is not int or not 0 <= self.squares <= 10000
                or self.remainder_meters >= CELL_METERS
                or (self.squares == 0 and self.remainder_meters == 0)):
            raise ValueError("Segmento de movimento inválido.")


@dataclass(frozen=True)
class MovementIntent:
    segments: tuple[MovementSegment, ...]
    dash: bool
    clarification: str
    target_id: str | None = None

    def __post_init__(self) -> None:
        if (len(self.segments) > 10 or type(self.dash) is not bool
                or not isinstance(self.clarification, str)):
            raise ValueError("Intenção de movimento inválida.")
        if self.target_id is not None and (not isinstance(self.target_id, str) or not self.target_id):
            raise ValueError("Destino inválido.")
        if self.target_id is not None and self.segments:
            raise ValueError("Use um destino nomeado ou segmentos, não os dois.")
        if self.clarification and (self.segments or self.dash or self.target_id):
            raise ValueError("Um pedido de esclarecimento não pode mover o personagem.")


@dataclass(frozen=True)
class DoorIntent:
    operation: str
    target_id: str

    def __post_init__(self) -> None:
        if self.operation not in {"open", "close"} or not isinstance(self.target_id, str) or not self.target_id:
            raise ValueError("Intenção de porta inválida.")


PlayerIntent = MovementIntent | DoorIntent


@dataclass(frozen=True)
class ActionPlan:
    steps: tuple[PlayerIntent, ...]

    def __post_init__(self) -> None:
        if (not 1 <= len(self.steps) <= 10
                or not all(isinstance(step, (MovementIntent, DoorIntent)) for step in self.steps)):
            raise ValueError("Um pedido deve conter entre 1 e 10 operações.")


class InterpretationError(ValueError):
    """Falha de interpretação, independente do provedor."""


class IntentInterpreter(Protocol):
    def interpret(self, prompt: str, context: dict) -> ActionPlan: ...



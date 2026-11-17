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
    allow_approach: bool = True

    def __post_init__(self) -> None:
        if (self.operation not in {"open", "close"} or not isinstance(self.target_id, str)
                or not self.target_id or type(self.allow_approach) is not bool):
            raise ValueError("Intenção de porta inválida.")


@dataclass(frozen=True)
class RuleIntent:
    operation: str
    target_id: str | None = None
    weapon: str = "greatsword"
    use_inspiration: bool = False
    allow_approach: bool = True

    def __post_init__(self) -> None:
        if (self.operation not in {"start_combat", "end_turn", "attack", "second_wind", "action_surge", "hide"}
                or self.weapon not in {"greatsword", "flail", "javelin", "longsword", "unarmed"}
                or type(self.use_inspiration) is not bool or type(self.allow_approach) is not bool
                or (self.target_id is not None and (not isinstance(self.target_id, str) or not self.target_id))
                or (self.operation == "attack" and not self.target_id)
                or (self.operation != "attack" and (self.target_id or self.use_inspiration))):
            raise ValueError("Operação de combate inválida.")


NARRATIVE_OPERATIONS = ("look", "speak", "wait", "challenge")


@dataclass(frozen=True)
class NarrativeIntent:
    text: str
    operation: str = "look"
    target_id: str | None = None
    volume: str = "normal"

    def __post_init__(self):
        if (self.volume not in {"quiet", "normal", "loud"}
                or (self.operation not in {"speak", "challenge"} and self.volume != "normal") or not isinstance(self.text, str) or not self.text.strip() or len(self.text) > 2000
                or self.operation not in NARRATIVE_OPERATIONS or self.target_id is not None):
            raise ValueError("Intenção narrativa inválida.")


SCENARIO_OPERATIONS = ("investigate", "take", "drop", "wear", "conceal", "unlock",
                       "listen", "sneak", "wake", "deceive", "escape")


@dataclass(frozen=True)
class ScenarioIntent:
    """Interação concreta; o cenário valida alvo, alcance e efeitos."""

    operation: str
    target_id: str
    allow_approach: bool = True

    def __post_init__(self):
        if (self.operation not in SCENARIO_OPERATIONS or not isinstance(self.target_id, str)
                or not self.target_id or type(self.allow_approach) is not bool):
            raise ValueError("Interação de cenário inválida.")


PlayerIntent = MovementIntent | DoorIntent | RuleIntent | NarrativeIntent | ScenarioIntent


REQUEST_KINDS = ("execute", "question", "negated", "quoted", "narrative_detail", "unsupported", "conditional", "unclear")
PLAN_OPERATIONS = ("hide", "move", "open", "close", "attack", "end_turn", "second_wind", "action_surge",
                   *NARRATIVE_OPERATIONS, *SCENARIO_OPERATIONS, "clarify", "dash", "inspiration")


@dataclass(frozen=True)
class RequestPart:
    text: str
    kind: str
    operations: tuple[str, ...] = ()
    step_indices: tuple[int, ...] = ()

    def __post_init__(self):
        if (not isinstance(self.text, str) or not self.text.strip() or len(self.text) > 2000
                or self.kind not in REQUEST_KINDS or len(self.operations) > 30 or len(self.step_indices) > 10
                or any(op not in PLAN_OPERATIONS for op in self.operations)
                or any(type(i) is not int or not 0 <= i < 10 for i in self.step_indices)):
            raise ValueError("Origem de etapa inválida.")


@dataclass(frozen=True)
class ActionPlan:
    steps: tuple[PlayerIntent, ...]
    request_parts: tuple[RequestPart, ...] = ()

    def __post_init__(self) -> None:
        if (len(self.steps) > 10 or (not self.steps and not self.request_parts)
                or not all(isinstance(step, (MovementIntent, DoorIntent, RuleIntent, NarrativeIntent, ScenarioIntent)) for step in self.steps)
                or len(self.request_parts) > 20 or not all(isinstance(p, RequestPart) for p in self.request_parts)):
            raise ValueError("Plano deve conter até 10 operações e até 20 trechos de origem.")


class InterpretationError(ValueError):
    """Falha de interpretação, independente do provedor."""


class IntentInterpreter(Protocol):
    def interpret(self, prompt: str, context: dict) -> ActionPlan: ...



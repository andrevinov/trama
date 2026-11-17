"""Criaturas posicionadas no mundo; sem comportamento ou regras de combate."""

from dataclasses import dataclass
import logging

from trama.spatial import Position
from trama.perception import Senses

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Creature:
    id: str
    name: str
    position: Position
    hostile: bool = True
    senses: Senses = Senses()

    def __post_init__(self) -> None:
        if not self.id or not self.name or type(self.hostile) is not bool or not isinstance(self.senses, Senses):
            raise ValueError("Criatura inválida.")


def creatures_from_data(data: list[dict]) -> tuple[Creature, ...]:
    result = tuple(Creature(item["id"], item["name"], Position(*item["position"]),
                          item.get("hostile", True), Senses(**item.get("senses", {}))) for item in data)
    logger.debug("creatures.loaded", extra={"data": {"creatures": result}})
    return result

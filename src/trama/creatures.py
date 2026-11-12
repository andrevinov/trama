"""Criaturas posicionadas no mundo; sem comportamento ou regras de combate."""

from dataclasses import dataclass

from trama.spatial import Position


@dataclass(frozen=True)
class Creature:
    id: str
    name: str
    position: Position
    hostile: bool = True

    def __post_init__(self) -> None:
        if not self.id or not self.name or type(self.hostile) is not bool:
            raise ValueError("Criatura inválida.")


def creatures_from_data(data: list[dict]) -> tuple[Creature, ...]:
    return tuple(Creature(item["id"], item["name"], Position(*item["position"]),
                          item.get("hostile", True)) for item in data)

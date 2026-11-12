"""Coordenadas e grade compartilhadas; sem regras de turno ou interface."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    x: int
    y: int

    def __post_init__(self) -> None:
        if type(self.x) is not int or type(self.y) is not int:
            raise ValueError("Coordenadas devem ser inteiras.")


@dataclass(frozen=True)
class Grid:
    width: int
    height: int
    blocked: frozenset[Position] = frozenset()
    difficult: frozenset[Position] = frozenset()

    def __post_init__(self) -> None:
        if (type(self.width) is not int or type(self.height) is not int
                or self.width <= 0 or self.height <= 0):
            raise ValueError("A grade deve ter dimensões inteiras positivas.")
        if any(not self.contains(p) for p in self.blocked | self.difficult):
            raise ValueError("Terreno fora da grade.")
        if self.blocked & self.difficult:
            raise ValueError("Uma casa bloqueada não pode ser terreno difícil.")

    def contains(self, position: Position) -> bool:
        return 0 <= position.x < self.width and 0 <= position.y < self.height



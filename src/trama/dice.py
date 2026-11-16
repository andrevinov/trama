"""Rolagens locais injetáveis; nenhum modelo de IA escolhe os resultados."""

from dataclasses import dataclass
from random import Random
from typing import Protocol
import logging

logger = logging.getLogger(__name__)


class Roller(Protocol):
    def roll(self, sides: int) -> int: ...


class RandomRoller:
    def __init__(self, random: Random | None = None) -> None:
        self.random = random or Random()

    def roll(self, sides: int) -> int:
        return self.random.randint(1, sides)


def roll_die(roller: Roller, sides: int) -> int:
    result = roller.roll(sides)
    if type(result) is not int or not 1 <= result <= sides:
        logger.error("dice.invalid_result", extra={"data": {"sides": sides, "result": result}})
        raise ValueError("Resultado de dado inválido.")
    logger.debug("dice.rolled", extra={"data": {"sides": sides, "result": result}})
    return result


@dataclass(frozen=True)
class D20Roll:
    dice: tuple[int, ...]
    selected: int
    modifier: int
    advantage: bool = False
    disadvantage: bool = False

    @property
    def natural(self) -> int:
        return self.dice[self.selected]

    @property
    def total(self) -> int:
        return self.natural + self.modifier


def roll_d20(roller: Roller, modifier: int = 0, *, advantage=False, disadvantage=False) -> D20Roll:
    dice = tuple(roll_die(roller, 20) for _ in range(2 if advantage != disadvantage else 1))
    selected = dice.index(max(dice) if advantage else min(dice)) if len(dice) == 2 else 0
    result = D20Roll(dice, selected, modifier, advantage, disadvantage)
    logger.debug("dice.d20_resolved", extra={"data": {"roll": result, "natural": result.natural, "total": result.total}})
    return result

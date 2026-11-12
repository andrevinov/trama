"""Falas on/off e contrato de narração, sem provedor ou estado de jogo."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Speech:
    on: str = ""
    off: str = ""

    @property
    def text(self) -> str:
        return "\n\n".join(part for part in (self.on, f"[{self.off}]" if self.off else "") if part)


def split_speech(text: str) -> Speech:
    """Somente texto fora de colchetes pode propor ações no mundo."""
    on, off, buffer = [], [], []
    depth = 0
    for char in text:
        if char == "[":
            if depth == 0:
                on.append("".join(buffer))
                buffer = []
            else:
                buffer.append(char)
            depth += 1
        elif char == "]":
            if depth == 0:
                raise ValueError("Há um colchete de fechamento sem abertura.")
            depth -= 1
            if depth == 0:
                off.append("".join(buffer))
                buffer = []
            else:
                buffer.append(char)
        else:
            buffer.append(char)
    if depth:
        raise ValueError("Feche os colchetes da fala em off antes de enviar.")
    on.append("".join(buffer))
    return Speech("\n".join(p.strip() for p in on if p.strip()),
                  "\n".join(p.strip() for p in off if p.strip()))


@dataclass(frozen=True)
class DialogueMessage:
    role: str
    speech: Speech


class NarrationError(ValueError):
    """Falha na narração; a execução já realizada deve ser preservada."""


class Narrator(Protocol):
    def narrate(self, context: dict) -> Speech: ...

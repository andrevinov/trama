"""Falas on/off e contrato de narração, sem provedor ou estado de jogo."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Speech:
    on: str = ""
    off: str = ""

    def __post_init__(self):
        if not isinstance(self.on, str) or not isinstance(self.off, str):
            raise ValueError('Os canais on/off devem conter texto.')

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

    def __post_init__(self):
        if (self.role not in ('player', 'narrator') or not isinstance(self.speech, Speech)
                or not (self.speech.on.strip() or self.speech.off.strip())):
            raise ValueError('Mensagem deve identificar player/narrator e conter fala on ou off.')
        if self.role == 'player' and len(self.speech.on) + len(self.speech.off) > 2000:
            raise ValueError('A mensagem do jogador excede 2000 caracteres.')

    @classmethod
    def from_data(cls, data: dict) -> 'DialogueMessage':
        """Lê histórico registrado sem reinterpretar texto nem aceitar instruções de sistema."""
        if (not isinstance(data, dict) or not {'role', 'on'} <= data.keys()
                or data.keys() - {'role', 'on', 'off'}):
            raise ValueError('Histórico deve conter somente role, on e off opcional.')
        return cls(data['role'], Speech(data['on'], data.get('off', '')))


class NarrationError(ValueError):
    """Falha na narração; a execução já realizada deve ser preservada."""


class Narrator(Protocol):
    def narrate(self, context: dict) -> Speech: ...

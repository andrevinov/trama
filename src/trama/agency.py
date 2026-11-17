"""Intenção contextual de um NPC: decisão do Mundo, efeitos validados pelo motor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class IntentDecision:
    actor_id: str
    goal: str
    activity: str
    waiting_for: str | None

    def __post_init__(self):
        if (not isinstance(self.actor_id, str) or not self.actor_id.strip() or len(self.actor_id) > 120
                or any(not isinstance(v, str) or not v.strip() or len(v) > 300 for v in (self.goal, self.activity))
                or self.waiting_for is not None and (not isinstance(self.waiting_for, str)
                    or not self.waiting_for.strip() or len(self.waiting_for) > 300)):
            raise ValueError('Intenção do NPC inválida.')

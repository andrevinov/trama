"""Intenção contextual de um NPC: decisão do Mundo, efeitos validados pelo motor."""

from dataclasses import dataclass

INITIATIVES = ('respond', 'listen', 'clarify', 'contest', 'insist', 'counteroffer',
               'accept', 'reject', 'close', 'start_conflict', 'suspend', 'resume', 'investigate', 'protect', 'leave')


@dataclass(frozen=True)
class IntentDecision:
    actor_id: str
    goal: str
    activity: str
    waiting_for: str | None
    initiative: str | None = None
    reason: str | None = None
    opinion_ids: tuple[str, ...] = ()

    def __post_init__(self):
        if (not isinstance(self.actor_id, str) or not self.actor_id.strip() or len(self.actor_id) > 120
                or any(not isinstance(v, str) or not v.strip() or len(v) > 300 for v in (self.goal, self.activity))
                or self.waiting_for is not None and (not isinstance(self.waiting_for, str)
                    or not self.waiting_for.strip() or len(self.waiting_for) > 300)
                or self.initiative is not None and self.initiative not in INITIATIVES
                or self.reason is not None and (not isinstance(self.reason, str) or not self.reason.strip()
                                                or len(self.reason) > 500)
                or (self.initiative is None) != (self.reason is None)
                or self.opinion_ids and self.initiative is None
                or not isinstance(self.opinion_ids, tuple) or len(self.opinion_ids) > 4
                or len(set(self.opinion_ids)) != len(self.opinion_ids)
                or any(not isinstance(id, str) or not id.strip() or len(id) > 120 for id in self.opinion_ids)):
            raise ValueError('Intenção do NPC inválida.')

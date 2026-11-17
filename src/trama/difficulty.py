"""Contratos de adjudicação contextual. CDs de regras fixas não entram aqui.

PHB 2024: Typical Difficulty Classes, Advantage/Disadvantage e Passive Perception.
O Mestre escolhe dificuldade e circunstâncias; Python valida e resolve os dados.
"""

from dataclasses import asdict, dataclass

DIFFICULTY_CLASSES = dict(very_easy=5, easy=10, moderate=15, hard=20, very_hard=25, nearly_impossible=30)


@dataclass(frozen=True)
class Adjudication:
    request_id: str
    outcome: str
    difficulty: str | None
    advantage: bool
    disadvantage: bool
    fact_ids: tuple[str, ...]
    reason: str

    def __post_init__(self):
        if (not isinstance(self.request_id, str) or not self.request_id or len(self.request_id) > 200
                or self.outcome not in {'automatic', 'check', 'impossible'}
                or (self.outcome == 'check' and self.difficulty not in DIFFICULTY_CLASSES)
                or (self.outcome != 'check' and self.difficulty is not None)
                or type(self.advantage) is not bool or type(self.disadvantage) is not bool
                or (self.outcome != 'check' and (self.advantage or self.disadvantage))
                or not isinstance(self.fact_ids, tuple) or not 1 <= len(self.fact_ids) <= 12
                or any(not isinstance(id, str) or not id for id in self.fact_ids)
                or len(set(self.fact_ids)) != len(self.fact_ids)
                or not isinstance(self.reason, str) or not self.reason.strip() or len(self.reason) > 500):
            raise ValueError('Avaliação contextual inválida: informe resultado, dificuldade e fatos válidos.')

    @property
    def dc(self):
        return DIFFICULTY_CLASSES.get(self.difficulty)

    def context(self):
        return {**asdict(self), 'dc': self.dc}

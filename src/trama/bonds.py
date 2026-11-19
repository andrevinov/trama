"""Vínculos direcionais qualitativos; política do Trama, sem pontos ou relógio."""

from dataclasses import dataclass

from trama.knowledge import Claim, MemorySource
from trama.social import text


BOND_KINDS = ('friendship', 'attraction', 'infatuation', 'love')
ROMANTIC_KINDS = frozenset(BOND_KINDS[1:])
BOND_STATES = ('absent', 'active', 'ended')


class BondError(ValueError):
    pass


@dataclass(frozen=True)
class BondEvidence:
    memory_id: str
    claim: Claim
    source: MemorySource
    acquired_at: int

    def __post_init__(self):
        if (not text(self.memory_id, 160) or not isinstance(self.claim, Claim)
                or not isinstance(self.source, MemorySource)
                or type(self.acquired_at) is not int or self.acquired_at < 0):
            raise BondError('Fonte de vínculo inválida.')

    @classmethod
    def from_memory(cls, memory):
        return cls(memory.id, memory.claim, memory.source, memory.acquired_at)


@dataclass(frozen=True)
class Bond:
    kind: str
    state: str = 'absent'
    reason: str = 'Nenhum vínculo declarado.'
    sources: tuple[BondEvidence, ...] = ()
    revision: int = 0

    def __post_init__(self):
        if (self.kind not in BOND_KINDS or self.state not in BOND_STATES or not text(self.reason)
                or not isinstance(self.sources, tuple) or len(self.sources) > 8
                or any(not isinstance(s, BondEvidence) for s in self.sources)
                or len({s.memory_id for s in self.sources}) != len(self.sources)
                or type(self.revision) is not int or self.revision < 0):
            raise BondError('Vínculo exige tipo, estado, motivo e fontes válidos.')


@dataclass(frozen=True)
class BondUpdate:
    owner_id: str
    target_id: str
    kind: str
    state: str
    reason: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self):
        if (not text(self.owner_id, 120) or not text(self.target_id, 120) or self.owner_id == self.target_id
                or self.kind not in BOND_KINDS or self.state not in {'active', 'ended'} or not text(self.reason)
                or not isinstance(self.evidence_ids, tuple) or not 1 <= len(self.evidence_ids) <= 8
                or any(not text(id, 160) for id in self.evidence_ids)
                or len(set(self.evidence_ids)) != len(self.evidence_ids)):
            raise BondError('Interpretação de vínculo inválida; informe fontes próprias.')


def bond_update_from_data(data):
    try:
        data = dict(data)
        if not isinstance(data.get('evidence_ids'), (tuple, list)):
            raise BondError('Fontes do vínculo devem ser uma lista.')
        data['evidence_ids'] = tuple(data['evidence_ids'])
        return BondUpdate(**data)
    except (TypeError, KeyError) as error:
        raise BondError('Dados de vínculo inválidos.') from error


def initial_bonds(rows, owner, memories):
    if not isinstance(rows, list):
        raise BondError('bonds deve ser uma lista de vínculos declarados.')
    result = []
    try:
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'kind', 'state', 'reason', 'memory_ids'}:
                raise BondError('Vínculo inicial exige tipo, estado, motivo e memórias.')
            ids = row['memory_ids']
            if (not isinstance(ids, list) or len(ids) > 8 or any(not text(id, 160) for id in ids)
                    or len(set(ids)) != len(ids) or row['state'] != 'absent' and not ids):
                raise BondError('Vínculo inicial precisa de história própria, sem fontes repetidas.')
            sources = []
            for id in ids:
                memory = memories.get(id)
                if memory is None or memory.owner_id != owner:
                    raise BondError('A história inicial pertence ao próprio dono do vínculo.')
                sources.append(BondEvidence.from_memory(memory))
            result.append(Bond(row['kind'], row['state'], row['reason'], tuple(sources)))
        if len({b.kind for b in result}) != len(result):
            raise BondError('Tipo de vínculo inicial repetido.')
        return tuple(result)
    except (KeyError, TypeError) as error:
        raise BondError('Vínculos iniciais inválidos.') from error


def adult_ids_from_data(data):
    """Elegibilidade explícita do autor; não infere idade por nome ou papel."""
    result = []
    for actor in (dict(data.get('player', {}), id='player'), *data.get('creatures', []), *data.get('observers', [])):
        value = actor.get('adult', False)
        if type(value) is not bool:
            raise BondError('adult deve ser um booleano explícito no cenário.')
        if value:
            result.append(actor['id'])
    return tuple(result)

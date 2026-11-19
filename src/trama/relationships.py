"""Relações direcionais, episódios percebidos e parcela nas opções; política do Trama.

Escala/pesos escolhidos pelo usuário em 19/11/2026. Variações por episódio
definidas no passo 6, sem inferir reciprocidade ou sentimentos do jogador.
"""

from dataclasses import asdict, dataclass, replace

from trama.knowledge import Claim, MemorySource
from trama.social import bounded, text
from trama.bonds import Bond, BondError, BOND_KINDS, ROMANTIC_KINDS, initial_bonds


DIMENSIONS = ('trust', 'affection')
LEVEL_LIMIT = 5
DIMENSION_WEIGHT = 2
RELATIONSHIP_CAP = 12


class RelationshipError(ValueError):
    pass


@dataclass(frozen=True)
class RelationshipEvidence:
    memory_id: str
    claim: Claim
    interest_id: str | None
    source: MemorySource

    def __post_init__(self):
        if (not text(self.memory_id, 160) or not isinstance(self.claim, Claim)
                or self.interest_id is not None and not text(self.interest_id, 80)
                or not isinstance(self.source, MemorySource)):
            raise RelationshipError('Fonte da relação inválida.')


@dataclass(frozen=True)
class RelationshipDimension:
    value: int
    reason: str
    sources: tuple[RelationshipEvidence, ...] = ()

    def __post_init__(self):
        if (type(self.value) is not int or not -LEVEL_LIMIT <= self.value <= LEVEL_LIMIT
                or not text(self.reason) or not isinstance(self.sources, tuple)
                or any(not isinstance(s, RelationshipEvidence) for s in self.sources)
                or len({(s.claim, s.interest_id) for s in self.sources}) != len(self.sources)):
            raise RelationshipError('Dimensão da relação exige valor entre -5 e 5, motivo e fontes sem repetição.')


@dataclass(frozen=True)
class Relationship:
    owner_id: str
    target_id: str
    trust: RelationshipDimension
    affection: RelationshipDimension
    declared: bool = True
    bonds: tuple[Bond, ...] = ()

    def __post_init__(self):
        if (not text(self.owner_id, 120) or not text(self.target_id, 120) or self.owner_id == self.target_id
                or not isinstance(self.trust, RelationshipDimension)
                or not isinstance(self.affection, RelationshipDimension) or type(self.declared) is not bool
                or not isinstance(self.bonds, tuple) or any(not isinstance(b, Bond) for b in self.bonds)
                or len({b.kind for b in self.bonds}) != len(self.bonds)):
            raise RelationshipError('Relação exige dono, destinatário distinto e duas dimensões válidas.')


@dataclass(frozen=True)
class RelationshipEffect:
    target_id: str
    dimension: str
    effect: int
    reason: str

    def __post_init__(self):
        if (not text(self.target_id, 120) or self.dimension not in DIMENSIONS
                or type(self.effect) is not int or self.effect not in {-1, 0, 1} or not text(self.reason)):
            raise RelationshipError('Impacto contextual da relação inválido.')


def relationships_from_data(data, memories):
    """Dados do autor; a IA não define níveis nem cria fontes durante a partida."""
    if 'relationships' in data.get('player', {}):
        raise RelationshipError('Este recorte não atribui confiança ou afeto ao personagem do jogador.')
    by_id = {m.id: m for m in memories}
    result = []
    try:
        for actor in (*data.get('creatures', []), *data.get('observers', [])):
            rows = actor.get('relationships', [])
            if not isinstance(rows, list):
                raise RelationshipError('relationships deve ser uma lista.')
            for row in rows:
                if (not isinstance(row, dict) or set(row) - {'target_id', *DIMENSIONS, 'bonds'}
                        or not {'target_id', *DIMENSIONS} <= row.keys()):
                    raise RelationshipError('Declare destinatário, confiança e afeto na relação inicial.')
                dimensions = {}
                for name in DIMENSIONS:
                    if not isinstance(row[name], dict):
                        raise RelationshipError('Cada dimensão deve declarar valor, motivo e fontes.')
                    values = dict(row[name])
                    sources = values.pop('sources', [])
                    if not isinstance(sources, list):
                        raise RelationshipError('Fontes da relação devem ser uma lista.')
                    if len(sources) > 8:
                        raise RelationshipError('Uma dimensão inicial admite até oito fontes.')
                    links = []
                    for link in sources:
                        if not isinstance(link, dict) or set(link) != {'memory_id', 'interest_id'}:
                            raise RelationshipError('Fonte exige memória e interesse resumido pela relação.')
                        memory = by_id.get(link['memory_id'])
                        if memory is None or memory.owner_id != actor['id']:
                            raise RelationshipError('A fonte da relação deve ser memória do próprio NPC.')
                        links.append(RelationshipEvidence(memory.id, memory.claim, link['interest_id'], memory.source))
                    dimensions[name] = RelationshipDimension(**values, sources=tuple(links))
                result.append(Relationship(actor['id'], row['target_id'], **dimensions,
                    bonds=initial_bonds(row.get('bonds', []), actor['id'], by_id)))
        return tuple(result)
    except (TypeError, KeyError, AttributeError) as error:
        raise RelationshipError('Dados de relações iniciais inválidos.') from error


class RelationshipState:
    """Níveis direcionais e episódios em processo; valores individuais são imutáveis."""

    def __init__(self, relationships, profiles, player_id, memories, adult_ids=()):
        self._owners = frozenset(profiles)
        self._actors = self._owners | {player_id}
        self.player_id = player_id
        self.adult_ids = frozenset(adult_ids)
        if not self.adult_ids <= self._actors:
            raise BondError('Elegibilidade adulta pertence a personagem inexistente.')
        self._rows = {}
        by_id = {m.id: m for m in memories}
        initial_revision = max((m.acquired_at for m in by_id.values()), default=0)
        for row in relationships:
            if (not isinstance(row, Relationship) or row.owner_id not in self._owners
                    or row.target_id not in self._actors or (row.owner_id, row.target_id) in self._rows):
                raise RelationshipError('Relação duplicada ou entre personagens inexistentes; o jogador não recebe sentimentos.')
            interests = {i.id: i for i in profiles[row.owner_id].persona.interests}
            for name in DIMENSIONS:
                if len(getattr(row, name).sources) > 8:
                    raise RelationshipError('Uma dimensão inicial admite até oito fontes.')
                for source in getattr(row, name).sources:
                    memory = by_id.get(source.memory_id)
                    interest = interests.get(source.interest_id)
                    if (memory is None or memory.owner_id != row.owner_id or memory.claim != source.claim
                            or memory.source != source.source or source.interest_id is not None
                            and (interest is None or not interest.relevant(memory))):
                        raise RelationshipError('Fonte da relação sem memória própria e âncora pertinente ao interesse.')
            row = replace(row, bonds=tuple(replace(b, revision=initial_revision) for b in row.bonds))
            self._rows[(row.owner_id, row.target_id)] = row
            for bond in row.bonds:
                if bond.kind in ROMANTIC_KINDS and bond.state != 'absent' and not self.romance_eligible(row.owner_id, row.target_id):
                    raise BondError('Vínculo amoroso inicial exige ambos adultos declarados.')
                if any(s.memory_id not in by_id or by_id[s.memory_id].owner_id != row.owner_id
                       or s != type(s).from_memory(by_id[s.memory_id])
                       or not (by_id[s.memory_id].source.actor_id == row.target_id
                           or by_id[s.memory_id].claim.subject_id == row.target_id
                           or row.target_id in by_id[s.memory_id].entities) for s in bond.sources):
                    raise BondError('Fonte inicial de vínculo sem memória própria correspondente.')
        self._initial = dict(self._rows)
        self._episodes = {}
        self._history = []
        self._bond_history = []
        self._bond_keys = set()

    def romance_eligible(self, owner, target):
        return owner in self.adult_ids and target in self.adult_ids

    def bond(self, owner, target, kind):
        return next((b for b in self.get(owner, target).bonds if b.kind == kind), Bond(kind))

    @staticmethod
    def bond_key(update, sources):
        return (update.owner_id, update.target_id, update.kind, update.state,
                frozenset((s.claim, s.source.kind, s.source.event_id) for s in sources))

    def bond_reused(self, update, sources):
        before = self.bond(update.owner_id, update.target_id, update.kind)
        return (self.bond_key(update, sources) in self._bond_keys or
                before.state == update.state and
                {(s.claim, s.source.kind, s.source.event_id) for s in before.sources} ==
                {(s.claim, s.source.kind, s.source.event_id) for s in sources})

    def record_bond(self, update, sources, revision):
        before = self.bond(update.owner_id, update.target_id, update.kind)
        after = Bond(update.kind, update.state, update.reason, tuple(sources), revision)
        row = self.get(update.owner_id, update.target_id)
        self._rows[(row.owner_id, row.target_id)] = replace(row, declared=True,
            bonds=tuple(b for b in row.bonds if b.kind != update.kind) + (after,))
        self._bond_keys.add(self.bond_key(update, sources))
        entry = dict(id=f'bond_change_{len(self._bond_history)+1}', owner_id=row.owner_id,
            target_id=row.target_id, kind=update.kind, before=asdict(before), after=asdict(after), reason=update.reason)
        self._bond_history.append(entry)
        return entry

    def bond_history(self, owner, target=None):
        from copy import deepcopy
        return deepcopy([e for e in self._bond_history if e['owner_id'] == owner
                         and (target is None or e['target_id'] == target)])

    def get(self, owner_id, target_id):
        if owner_id not in self._owners or target_id not in self._actors or owner_id == target_id:
            raise RelationshipError('O impacto exige relação direcional de NPC para outro personagem da cena.')
        neutral = RelationshipDimension(0, 'Nenhuma relação inicial declarada.')
        return self._rows.get((owner_id, target_id), Relationship(owner_id, target_id, neutral, neutral, declared=False))

    def basis(self, owner_id):
        if owner_id not in self._owners:
            raise RelationshipError('Somente NPCs têm relações privadas neste recorte.')
        return [asdict(row) for row in self._rows.values() if row.owner_id == owner_id]

    def context(self, owner_id):
        result = self.basis(owner_id)
        for row in result:
            for name in DIMENSIONS:
                dimension = row[name]
                dimension['source_count'] = len(dimension['sources'])
                dimension['sources'] = dimension['sources'][-8:]
            row['episodes'] = self.history(owner_id, row['target_id'])[-4:]
            row['bonds'] = {k: asdict(self.bond(owner_id, row['target_id'], k)) for k in BOND_KINDS}
            row['bond_history'] = self.bond_history(owner_id, row['target_id'])[-4:]
        return result

    def history(self, owner_id, target_id=None):
        from copy import deepcopy
        result = deepcopy([e for e in self._history if e['owner_id'] == owner_id
                           and (target_id is None or e['target_id'] == target_id)])
        for entry in result:
            entry['sources'] = [asdict(s) for s in entry['sources']]
        return result

    def record_episode(self, owner_id, update, memory, sources, commitment=None):
        """Um saldo por episódio/fato; confirmação e correção substituem sua parcela."""
        before = self.get(owner_id, update.target_id)
        identity = (('commitment', commitment['conversation_id'], commitment['proposal_id'],
                     commitment['version'], commitment['term_id']) if commitment else
                    ('fact', memory.claim.subject_id, memory.claim.predicate))
        key = owner_id, update.target_id, *identity
        previous = self._episodes.get(key)
        if previous and previous['kind'] == update.kind:
            return dict(previous, reused=True)
        if update.kind == 'correction':
            if not previous or previous['claim']['value'] == memory.claim.value:
                raise RelationshipError('Correção exige episódio anterior e evidência que o contradiga.')
        elif previous and previous['kind'] not in {'suspicion', 'correction'}:
            raise RelationshipError('Esse episódio já foi interpretado; não o reaplique com outro rótulo.')
        delta = dict(EPISODE_DELTAS[update.kind])
        initial = self._initial.get((owner_id, update.target_id))
        if initial:
            for name in DIMENSIONS:
                if any(s.claim == memory.claim for s in getattr(initial, name).sources):
                    delta[name] = 0  # O cenário já incorporou esse episódio nessa dimensão.
        episode_id = previous['episode_id'] if previous else f'episode_{len(self._episodes) + 1}'
        entry = dict(id=f'relationship_change_{len(self._history) + 1}', episode_id=episode_id,
            owner_id=owner_id, target_id=update.target_id, kind=update.kind, reason=update.reason,
            evidence_id=memory.id, claim=asdict(memory.claim), source=asdict(memory.source),
            delta=delta, sources=tuple(sources), commitment=commitment, reused=False)
        if previous and previous.get('commitment') and commitment and previous['commitment'] != commitment:
            raise RelationshipError('A mesma evidência não cumpre dois compromissos distintos.')
        self._episodes[key] = entry
        dimensions = {}
        for name in DIMENSIONS:
            base = getattr(initial, name) if initial else RelationshipDimension(0, 'Nenhuma relação inicial declarada.')
            related = [e for e in self._episodes.values() if e['owner_id'] == owner_id and e['target_id'] == update.target_id]
            value = bounded(base.value + sum(e['delta'][name] for e in related), LEVEL_LIMIT)
            evidence = {(s.claim, s.interest_id): s for s in base.sources}
            for event in related:
                if event['delta'][name]:
                    evidence.update({(s.claim, s.interest_id): s for s in event['sources']})
            dimensions[name] = RelationshipDimension(value, update.reason, tuple(evidence.values()))
        self._rows[(owner_id, update.target_id)] = replace(before, **dimensions, declared=True)
        entry['before'] = {name: getattr(before, name).value for name in DIMENSIONS}
        entry['after'] = {name: dimensions[name].value for name in DIMENSIONS}
        self._history.append(entry)
        return dict(entry)


# Variações nominais por episódio; a escala e os pesos do passo 5 permanecem.
EPISODE_DELTAS = {
    'promise_kept': dict(trust=1, affection=0),
    'costly_help': dict(trust=1, affection=2),
    'betrayal_discovered': dict(trust=-2, affection=-1),
    'care_shown': dict(trust=0, affection=1),
    'suspicion': dict(trust=-1, affection=0),
    'correction': dict(trust=0, affection=0),
}


@dataclass(frozen=True)
class RelationshipEpisode:
    owner_id: str
    target_id: str
    kind: str
    evidence_id: str
    reason: str
    interest_ids: tuple[str, ...] = ()
    conversation_id: str | None = None
    proposal_id: str | None = None
    version: int | None = None
    term_id: str | None = None

    def __post_init__(self):
        if (not text(self.owner_id, 120) or not text(self.target_id, 120) or self.owner_id == self.target_id
                or self.kind not in EPISODE_DELTAS or not text(self.evidence_id, 160) or not text(self.reason)
                or not isinstance(self.interest_ids, tuple) or len(self.interest_ids) > 8
                or any(not text(i, 80) for i in self.interest_ids)
                or len(set(self.interest_ids)) != len(self.interest_ids)
                or any(v is not None and not text(v, 120) for v in
                       (self.conversation_id, self.proposal_id, self.term_id))
                or self.version is not None and (type(self.version) is not int or self.version < 1)
                or self.kind == 'promise_kept' and not all((self.conversation_id, self.proposal_id, self.term_id))):
            raise RelationshipError('Episódio relacional inválido ou compromisso não identificado.')


def episode_from_data(value):
    try:
        value = dict(value)
        if not isinstance(value.get('interest_ids', ()), (list, tuple)):
            raise RelationshipError('Aspectos do episódio devem ser uma lista.')
        value['interest_ids'] = tuple(value.get('interest_ids', ()))
        return RelationshipEpisode(**value)
    except (TypeError, KeyError) as error:
        raise RelationshipError('Dados de episódio inválidos.') from error


def evaluate_relationships(owner_id, terms, state):
    """Soma impactos por destinatário/dimensão; níveis e limites vêm do código."""
    contributions = {}
    for term in terms:
        for impact in term.relationship_effects:
            if state is None:
                raise RelationshipError('A avaliação contextual exige o estado de relações da sessão.')
            relationship = state.get(owner_id, impact.target_id)
            dimension = getattr(relationship, impact.dimension)
            key = impact.target_id, impact.dimension
            entry = contributions.setdefault(key, dict(owner_id=owner_id, target_id=impact.target_id,
                dimension=impact.dimension, value=dimension.value, weight=DIMENSION_WEIGHT,
                declared=relationship.declared, origin_reason=dimension.reason,
                sources=[asdict(s) for s in dimension.sources], impacts=[]))
            entry['impacts'].append(dict(term_id=term.term_id, effect=impact.effect, reason=impact.reason))
    excluded = {}
    for (target, name), entry in contributions.items():
        entry['raw_effect'] = sum(e['effect'] for e in entry['impacts'])
        entry['effect'] = bounded(entry['raw_effect'], 1)
        entry['score'] = entry['value'] * entry['weight'] * entry['effect']
        if entry['score']:
            for source in getattr(state.get(owner_id, target), name).sources:
                excluded.setdefault((source.claim, source.interest_id), []).append(f'{owner_id}:{target}:{name}')
    raw = sum(e['score'] for e in contributions.values())
    return dict(score=bounded(raw, RELATIONSHIP_CAP), raw=raw, contributions=list(contributions.values())), excluded

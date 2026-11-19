"""Memórias de personagens: crenças com origem, independentes da verdade do mundo.

Política do Trama, não uma regra de D&D. O índice e a seleção não usam IA.
"""

from collections import defaultdict
from dataclasses import asdict, dataclass
import json
import re
import unicodedata


class KnowledgeError(ValueError):
    pass


def _text(value, maximum=500):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def terms(text):
    normalized = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))
    return frozenset(w for w in re.findall(r'\w+', normalized) if len(w) > 2)


@dataclass(frozen=True)
class Claim:
    subject_id: str
    predicate: str
    value: str

    def __post_init__(self):
        if not all(_text(v, 120) for v in (self.subject_id, self.predicate, self.value)):
            raise KnowledgeError('Afirmação exige assunto, relação e valor curtos.')


@dataclass(frozen=True)
class MemorySource:
    kind: str
    event_id: str
    actor_id: str | None = None
    memory_id: str | None = None

    def __post_init__(self):
        if (self.kind not in {'observation', 'report', 'inference', 'habit'} or not _text(self.event_id, 160)
                or self.actor_id is not None and not _text(self.actor_id, 120)
                or self.memory_id is not None and not _text(self.memory_id, 160)
                or self.kind == 'report' and self.actor_id is None):
            raise KnowledgeError('Origem de memória inválida.')


@dataclass(frozen=True)
class Memory:
    id: str
    owner_id: str
    claim: Claim
    text: str
    source: MemorySource
    when: str
    context: str
    entities: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    shareable: bool = True
    acquired_at: int = 0

    def __post_init__(self):
        if (not _text(self.id, 160) or not _text(self.owner_id, 120) or not isinstance(self.claim, Claim)
                or not isinstance(self.source, MemorySource) or not _text(self.text, 700)
                or not _text(self.when, 200) or not _text(self.context, 500)
                or type(self.shareable) is not bool or type(self.acquired_at) is not int or self.acquired_at < 0
                or any(not isinstance(v, tuple) or len(v) > 16 or len(set(v)) != len(v)
                       or any(not _text(x, 120) for x in v) for v in (self.entities, self.topics))):
            raise KnowledgeError('Memória contextual inválida.')

    def data(self):
        return {**asdict(self), 'entities': list(self.entities), 'topics': list(self.topics)}


def memory_from_data(data, owner_id=None):
    if not isinstance(data, dict):
        raise KnowledgeError('Uma memória deve ser um registro contextual.')
    try:
        values = dict(data)
        if owner_id is not None:
            if 'owner_id' in values:
                raise KnowledgeError('O dono da memória vem do personagem que a declara.')
            values['owner_id'] = owner_id
            values['id'] = f"{owner_id}:{values['id']}"
        values['claim'] = Claim(**values['claim'])
        values['source'] = MemorySource(**values['source'])
        for key in ('entities', 'topics'):
            value = values.get(key, [])
            if not isinstance(value, (list, tuple)):
                raise KnowledgeError('Entidades e assuntos devem ser listas.')
            values[key] = tuple(value)
        return Memory(**values)
    except (KeyError, TypeError) as error:
        raise KnowledgeError('Dados de memória inválidos.') from error


def initial_memories(data):
    result = []
    for actor in (*data.get('creatures', []), *data.get('observers', [])):
        memories = actor.get('knowledge', [])
        if not isinstance(memories, list):
            raise KnowledgeError('knowledge deve ser uma lista de memórias contextuais.')
        result.extend(memory_from_data(m, actor['id']) for m in memories)
    return tuple(result)


class KnowledgeStore:
    """Histórico por dono, com índices de entidades, assuntos e palavras.

    Observação nova substitui a crença ativa do mesmo assunto/relação. Relatos
    conflitantes coexistem; nenhuma atualização consulta a verdade global.
    """

    def __init__(self, memories=()):
        self._memories = {}
        self._owners = defaultdict(list)
        self._active = defaultdict(set)
        self._index = defaultdict(set)
        self._slots = defaultdict(set)
        self._superseded = {}
        self._sequence = 0
        for memory in memories:
            self._insert(memory)

    def _insert(self, memory):
        if not isinstance(memory, Memory) or memory.id in self._memories:
            raise KnowledgeError('Memória inválida ou id duplicado.')
        self._memories[memory.id] = memory
        self._sequence = max(self._sequence, memory.acquired_at)
        self._owners[memory.owner_id].append(memory.id)
        self._active[memory.owner_id].add(memory.id)
        self._slots[(memory.owner_id, memory.claim.subject_id, memory.claim.predicate)].add(memory.id)
        entities = {*memory.entities, memory.claim.subject_id, memory.claim.value}
        for kind, values in (('entity', entities), ('topic', memory.topics),
                             ('word', terms(' '.join((memory.text, memory.context, memory.when, *entities, *memory.topics))))):
            for value in values:
                self._index[(memory.owner_id, kind, value)].add(memory.id)
        return memory

    @property
    def revision(self):
        return self._sequence

    def get(self, owner_id, memory_id):
        memory = self._memories.get(memory_id)
        if memory is None or memory.owner_id != owner_id:
            raise KnowledgeError('O personagem não possui a memória citada.')
        return memory

    def active(self, owner_id):
        return tuple(self._memories[id] for id in sorted(self._active.get(owner_id, ())))

    def learn(self, owner_id, claim, text, source, *, when, context, entities=(), topics=(), shareable=True,
              replace_existing=False):
        if not isinstance(claim, Claim) or not isinstance(source, MemorySource):
            raise KnowledgeError('Aquisição exige uma afirmação e uma origem válidas.')
        slot = (owner_id, claim.subject_id, claim.predicate)
        active = [self._memories[id] for id in self._slots.get(slot, ()) if id not in self._superseded]
        for old in active:
            # Perceber repetidamente a mesma coisa não produz lembranças por frame.
            if (not replace_existing and source.kind == 'observation' and old.claim == claim and old.source.kind == source.kind
                    and all(m.claim == claim for m in active)):
                return old
        self._sequence += 1
        while f'{owner_id}:memory:{self._sequence}' in self._memories:
            self._sequence += 1
        memory = Memory(f'{owner_id}:memory:{self._sequence}', owner_id, claim, text, source,
                        when, context, tuple(entities), tuple(topics), shareable, self._sequence)
        self._insert(memory)
        if source.kind == 'observation' or replace_existing:
            for old in active:
                self._superseded[old.id] = memory.id
                self._active[owner_id].discard(old.id)
        return memory

    def select(self, owner_id, *, entities=(), topics=(), query='', limit=6, max_chars=3500):
        """Consulta limitada, determinística; nunca envia o histórico inteiro."""
        if type(limit) is not int or not 0 <= limit <= 20 or type(max_chars) is not int or max_chars < 0:
            raise KnowledgeError('Limites de recuperação inválidos.')
        if limit == 0:
            return ()
        scores = defaultdict(int)
        for kind, values, weight in (('entity', set(entities), 5), ('topic', set(topics), 4), ('word', terms(query), 1)):
            for value in values:
                for id in self._index.get((owner_id, kind, value), ()):
                    if id not in self._superseded:
                        scores[id] += weight
        if not entities and not topics and not query.strip():
            for id in self._owners.get(owner_id, ())[-limit:]:
                if id not in self._superseded:
                    scores[id] = 0
        chosen, size = [], 0
        for id in sorted(scores, key=lambda id: (-scores[id], -self._memories[id].acquired_at, id)):
            memory = self._memories[id]
            # Limite do conteúdo serializado, inclusive proveniência, não só texto.
            cost = len(json.dumps(memory.data(), ensure_ascii=False))
            if size + cost > max_chars:
                continue
            chosen.append(memory)
            size += cost
            if len(chosen) >= limit:
                break
        return tuple(chosen)

    def export(self):
        return {'memories': [m.data() for m in self._memories.values()], 'superseded': dict(self._superseded)}

    @classmethod
    def restore(cls, data):
        try:
            if set(data) != {'memories', 'superseded'}:
                raise KnowledgeError('Arquivo de memórias inválido.')
            store = cls(memory_from_data(m) for m in data['memories'])
            for old, new in data['superseded'].items():
                a, b = store._memories[old], store._memories[new]
                if (a.owner_id, a.claim.subject_id, a.claim.predicate) != (b.owner_id, b.claim.subject_id, b.claim.predicate):
                    raise KnowledgeError('Substituição de crença inválida.')
                visited, cursor = {old}, new
                while cursor in data['superseded']:
                    if cursor in visited:
                        raise KnowledgeError('Ciclo de substituições de crenças.')
                    visited.add(cursor)
                    cursor = data['superseded'][cursor]
                if cursor in visited:
                    raise KnowledgeError('Ciclo de substituições de crenças.')
            store._superseded = dict(data['superseded'])
            for old in store._superseded:
                store._active[store._memories[old].owner_id].discard(old)
            return store
        except (KeyError, TypeError, AttributeError) as error:
            raise KnowledgeError('Arquivo de memórias inválido.') from error

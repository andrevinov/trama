"""Alinhamento e disposição social; pontuação é política do Trama, sem IA ou dados.

PHB 2024 descreve nove alinhamentos e Influence. Não fornece esta soma: pesos,
limiares e limites abaixo são o recorte solicitado para o Trama.
"""

from dataclasses import asdict, dataclass

from trama.knowledge import Claim


ALIGNMENTS = {
    'lawful_good': (1, 1), 'neutral_good': (0, 1), 'chaotic_good': (-1, 1),
    'lawful_neutral': (1, 0), 'neutral': (0, 0), 'chaotic_neutral': (-1, 0),
    'lawful_evil': (1, -1), 'neutral_evil': (0, -1), 'chaotic_evil': (-1, -1),
    'unaligned': (0, 0),
}
GOALS = ('listen', 'release', 'access', 'information')


class SocialError(ValueError):
    pass


def text(value, maximum=500):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def strings(value, maximum=16):
    return (isinstance(value, tuple) and len(value) <= maximum
            and all(text(v, 120) for v in value) and len(set(value)) == len(value))


@dataclass(frozen=True)
class Interest:
    id: str
    description: str
    weight: int
    evidence_topics: tuple[str, ...] = ()
    evidence_predicates: tuple[str, ...] = ()

    def __post_init__(self):
        if (not text(self.id, 80) or not text(self.description) or type(self.weight) is not int
                or not 1 <= self.weight <= 4 or not strings(self.evidence_topics) or not strings(self.evidence_predicates)):
            raise SocialError('Interesse da persona inválido.')

    def relevant(self, memory):
        return bool(set(memory.topics) & set(self.evidence_topics)
                    or memory.claim.predicate in self.evidence_predicates)


@dataclass(frozen=True)
class Persona:
    name: str
    role: str
    background: str
    interests: tuple[Interest, ...] = ()

    def __post_init__(self):
        if (not text(self.name, 120) or not text(self.role, 120) or not text(self.background, 800)
                or not isinstance(self.interests, tuple) or len(self.interests) > 8
                or any(not isinstance(i, Interest) for i in self.interests)
                or len({i.id for i in self.interests}) != len(self.interests)):
            raise SocialError('Persona inválida.')


@dataclass(frozen=True)
class SocialProfile:
    alignment: str
    persona: Persona

    def __post_init__(self):
        if self.alignment not in ALIGNMENTS or not isinstance(self.persona, Persona):
            raise SocialError('Perfil social exige alinhamento e persona válidos.')

    def context(self):
        return asdict(self)


def profile_from_data(data, name):
    try:
        values = dict(data)
        persona = dict(values.pop('persona', dict(name=name, role='NPC', background='Preserva sua integridade.',
            interests=[dict(id='safety', description='Preservar sua integridade.', weight=2)])))
        interests = []
        for item in persona.pop('interests', []):
            item = dict(item)
            for key in ('evidence_topics', 'evidence_predicates'):
                value = item.get(key, [])
                if not isinstance(value, (list, tuple)):
                    raise SocialError('Âncoras de evidência devem ser listas.')
                item[key] = tuple(value)
            interests.append(Interest(**item))
        return SocialProfile(persona=Persona(**persona, interests=tuple(interests)),
                             **{'alignment': 'neutral', **values})
    except (TypeError, KeyError) as error:
        raise SocialError('Dados de perfil social inválidos.') from error


def profiles_from_data(data):
    return {a['id']: profile_from_data(a.get('social', {}), a['name'])
            for a in (*data.get('creatures', []), *data.get('observers', []))}


@dataclass(frozen=True)
class PersonaEffect:
    interest_id: str
    effect: int
    reason: str

    def __post_init__(self):
        if not text(self.interest_id, 80) or type(self.effect) is not int or self.effect not in {-1, 0, 1} or not text(self.reason):
            raise SocialError('Efeito da solicitação sobre a persona inválido.')


@dataclass(frozen=True)
class MemoryEffect:
    claim: Claim
    interest_id: str
    effect: int
    reason: str

    def __post_init__(self):
        if (not isinstance(self.claim, Claim) or not text(self.interest_id, 80)
                or type(self.effect) is not int or self.effect not in {-1, 0, 1} or not text(self.reason)):
            raise SocialError('Efeito da memória inválido.')


@dataclass(frozen=True)
class DispositionAssessment:
    goal: str
    target_id: str
    description: str
    order: int
    morality: int
    alignment_reason: str
    persona_effects: tuple[PersonaEffect, ...]
    memory_effects: tuple[MemoryEffect, ...]
    accepted_reply: str
    refused_reply: str
    conditions: tuple[str, ...] = ()

    def __post_init__(self):
        if (self.goal not in GOALS or not text(self.target_id, 120) or not text(self.description)
                or any(type(v) is not int or v not in {-1, 0, 1} for v in (self.order, self.morality))
                or not text(self.alignment_reason) or not text(self.accepted_reply, 700) or not text(self.refused_reply, 700)
                or not strings(self.conditions, 6)
                or not isinstance(self.persona_effects, tuple) or len(self.persona_effects) > 8
                or any(not isinstance(e, PersonaEffect) for e in self.persona_effects)
                or not isinstance(self.memory_effects, tuple) or len(self.memory_effects) > 6
                or any(not isinstance(e, MemoryEffect) for e in self.memory_effects)
                or len({e.interest_id for e in self.persona_effects}) != len(self.persona_effects)):
            raise SocialError('Avaliação de disposição inválida.')
        if len({(e.claim, e.interest_id) for e in self.memory_effects}) != len(self.memory_effects):
            raise SocialError('A avaliação repete o mesmo fato para o mesmo interesse; liste cada vínculo uma única vez.')

    @property
    def key(self):
        # Na abordagem atual, ouvir é sempre ouvir o jogador interlocutor.
        # Referir-se ao ouvinte ou ao falante não cria outro pedido.
        return self.goal, 'interlocutor' if self.goal == 'listen' else self.target_id


def assessment_from_data(data):
    try:
        values = dict(data)
        values['persona_effects'] = tuple(PersonaEffect(**e) for e in values['persona_effects'])
        values['memory_effects'] = tuple(MemoryEffect(Claim(**e['claim']), e['interest_id'], e['effect'], e['reason'])
                                         for e in values['memory_effects'])
        values['conditions'] = tuple(values.get('conditions', []))
        return DispositionAssessment(**values)
    except (TypeError, KeyError) as error:
        raise SocialError('Dados de avaliação de disposição inválidos.') from error


def bounded(value, maximum):
    return max(-maximum, min(maximum, value))


def evaluate_disposition(profile, assessment, memories):
    """IA descreve impactos; pesos, referências e classe final são do código."""
    interests = {i.id: i for i in profile.persona.interests}
    if {e.interest_id for e in assessment.persona_effects} != set(interests):
        raise SocialError('Avalie cada interesse da persona exatamente uma vez.')
    law, good = ALIGNMENTS[profile.alignment]
    alignment = law * assessment.order + good * assessment.morality
    persona = [dict(interest_id=e.interest_id, effect=e.effect, weight=interests[e.interest_id].weight,
                    score=e.effect * interests[e.interest_id].weight, reason=e.reason) for e in assessment.persona_effects]
    evidence = {}
    for effect in assessment.memory_effects:
        interest = interests.get(effect.interest_id)
        matches = [m for m in memories if m.claim == effect.claim]
        if interest is None or not matches:
            raise SocialError('A avaliação cita interesse ou memória que o NPC não conhece.')
        memory = max(matches, key=lambda m: m.acquired_at)
        if not interest.relevant(memory):
            raise SocialError('Memória sem vínculo com as âncoras do interesse citado.')
        weight = 2 if memory.source.kind in {'observation', 'habit'} else 1
        contribution = evidence.setdefault(effect.claim, dict(memory_id=memory.id, claim=asdict(memory.claim),
            source=asdict(memory.source), weight=weight, impacts=[]))
        contribution['impacts'].append(dict(interest_id=interest.id, effect=effect.effect, reason=effect.reason))
    for contribution in evidence.values():
        # Um fato pode afetar vários interesses. Consequências no mesmo sentido
        # não multiplicam sua força; consequências opostas se compensam.
        contribution['effect'] = bounded(sum(e['effect'] for e in contribution['impacts']), 1)
        contribution['score'] = contribution['weight'] * contribution['effect']
    contributions = list(evidence.values())
    persona_score = bounded(sum(e['score'] for e in persona), 6)
    memory_score = bounded(sum(e['score'] for e in contributions), 3)
    total = alignment + persona_score + memory_score
    return dict(willingness='willing' if total >= 3 else 'unwilling' if total <= -3 else 'hesitant', total=total,
                components=dict(alignment=alignment, persona=persona_score, memories=memory_score),
                alignment_reason=assessment.alignment_reason, persona_effects=persona, memory_effects=contributions,
                goal=assessment.goal, target_id=assessment.target_id, description=assessment.description,
                conditions=list(assessment.conditions))

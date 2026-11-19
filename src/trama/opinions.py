"""Opiniões sobre opções e termos: política do Trama, sem dados ou decisão de agir."""

from dataclasses import asdict, dataclass

from trama.knowledge import Claim
from trama.social import (ALIGNMENTS, MemoryEffect, PersonaEffect, SocialError,
                          bounded, evaluate_basis, text)
from trama.relationships import RelationshipEffect, evaluate_relationships


@dataclass(frozen=True)
class TermAssessment:
    term_id: str
    description: str
    order: int
    morality: int
    alignment_reason: str
    persona_effects: tuple[PersonaEffect, ...]
    memory_effects: tuple[MemoryEffect, ...] = ()
    kind: str | None = None
    actor_id: str | None = None
    execution_order: int | None = None
    relationship_effects: tuple[RelationshipEffect, ...] = ()

    def __post_init__(self):
        if (not text(self.term_id, 120) or not text(self.description, 400)
                or any(type(v) is not int or v not in {-1, 0, 1} for v in (self.order, self.morality))
                or not text(self.alignment_reason)
                or not isinstance(self.persona_effects, tuple) or len(self.persona_effects) > 8
                or any(not isinstance(e, PersonaEffect) for e in self.persona_effects)
                or len({e.interest_id for e in self.persona_effects}) != len(self.persona_effects)
                or not isinstance(self.memory_effects, tuple) or len(self.memory_effects) > 6
                or any(not isinstance(e, MemoryEffect) for e in self.memory_effects)
                or len({(e.claim, e.interest_id) for e in self.memory_effects}) != len(self.memory_effects)):
            raise SocialError('Avaliação de termo inválida ou repetida.')
        if (self.kind is not None and self.kind not in {'request', 'counterpart', 'condition'}
                or self.actor_id is not None and not text(self.actor_id, 120)
                or self.execution_order is not None and (type(self.execution_order) is not int
                                                         or not 1 <= self.execution_order <= 8)):
            raise SocialError('Estrutura hipotética do termo inválida.')
        if (not isinstance(self.relationship_effects, tuple) or len(self.relationship_effects) > 8
                or any(not isinstance(e, RelationshipEffect) for e in self.relationship_effects)
                or len({(e.target_id, e.dimension) for e in self.relationship_effects}) != len(self.relationship_effects)):
            raise SocialError('Avalie cada vínculo destinatário/dimensão uma única vez por termo.')


@dataclass(frozen=True)
class OptionAssessment:
    actor_id: str
    conversation_id: str  # id conhecido ou latest, resolvido após a fala real
    kind: str
    description: str
    terms: tuple[TermAssessment, ...]
    proposal_id: str | None = None
    version: int | None = None
    option_id: str | None = None  # rótulo privado das alternativas/expectativas

    def __post_init__(self):
        if (not text(self.actor_id, 120) or not text(self.conversation_id, 120)
                or self.kind not in {'proposal', 'alternative', 'no_agreement'}
                or not text(self.description)
                or not isinstance(self.terms, tuple) or not 1 <= len(self.terms) <= 8
                or any(not isinstance(t, TermAssessment) for t in self.terms)
                or len({t.term_id for t in self.terms}) != len(self.terms)
                or self.version is not None and (type(self.version) is not int or self.version < 1)
                or self.proposal_id is not None and not text(self.proposal_id, 120)
                or self.option_id is not None and not text(self.option_id, 120)
                or self.kind in {'proposal', 'alternative'} and self.proposal_id is None
                or self.kind == 'proposal' and self.option_id is not None
                or self.kind != 'proposal' and self.option_id is None
                or self.kind == 'no_agreement' and (self.proposal_id is not None or self.version is not None)):
            raise SocialError('Opção exige proposta conhecida, alternativa vinculada ou expectativa sem acordo.')


def option_from_data(data):
    try:
        values = dict(data)
        terms = []
        for item in values['terms']:
            item = dict(item)
            item['persona_effects'] = tuple(PersonaEffect(**e) for e in item['persona_effects'])
            item['memory_effects'] = tuple(MemoryEffect(Claim(**e['claim']), e['interest_id'], e['effect'], e['reason'])
                                           for e in item['memory_effects'])
            item['relationship_effects'] = tuple(RelationshipEffect(**e) for e in item.get('relationship_effects', []))
            terms.append(TermAssessment(**item))
        return OptionAssessment(**{**values, 'terms': tuple(terms)})
    except (TypeError, KeyError) as error:
        raise SocialError('Dados de opinião inválidos.') from error


def evaluate_option(profile, assessment, memories, relationships=None):
    """Conserva contribuições contrárias antes da compensação e dos limites globais."""
    terms = []
    persona, evidence = {}, {}
    relation, excluded = evaluate_relationships(assessment.actor_id, assessment.terms, relationships)
    for term in assessment.terms:
        basis = evaluate_basis(profile, term, memories, excluded_memory_effects=excluded)
        basis.pop('willingness')  # Um termo isolado não é uma decisão de aceitar.
        terms.append(dict(term_id=term.term_id, description=term.description,
                          order=term.order, morality=term.morality, kind=term.kind,
                          actor_id=term.actor_id, execution_order=term.execution_order,
                          relationship_effects=[asdict(e) for e in term.relationship_effects], **basis))
        for impact in basis['persona_effects']:
            entry = persona.setdefault(impact['interest_id'], dict(
                interest_id=impact['interest_id'], weight=impact['weight'], impacts=[]))
            entry['impacts'].append(dict(term_id=term.term_id, effect=impact['effect'], reason=impact['reason']))
        for contribution in basis['memory_effects']:
            key = Claim(**contribution['claim'])
            entry = evidence.setdefault(key, {**contribution, 'impacts': []})
            entry['impacts'].extend(dict(impact, term_id=term.term_id) for impact in contribution['impacts'])
    for entry in (*persona.values(), *evidence.values()):
        entry['raw_effect'] = sum(e['effect'] for e in entry['impacts'] if e.get('counted', True))
        entry['effect'] = bounded(entry['raw_effect'], 1)
        entry['score'] = entry['effect'] * entry['weight']
    law, good = ALIGNMENTS[profile.alignment]
    raw_order = sum(t.order for t in assessment.terms)
    raw_morality = sum(t.morality for t in assessment.terms)
    alignment = law * bounded(raw_order, 1) + good * bounded(raw_morality, 1)
    raw_persona = sum(e['score'] for e in persona.values())
    raw_memories = sum(e['score'] for e in evidence.values())
    components = dict(alignment=alignment, persona=bounded(raw_persona, 6), memories=bounded(raw_memories, 3),
                      relationships=relation['score'])
    total = sum(components.values())
    return dict(total=total, inclination='favorable' if total >= 3 else 'unfavorable' if total <= -3 else 'mixed',
                components=components, raw=dict(order=raw_order, morality=raw_morality,
                    persona=raw_persona, memories=raw_memories, relationships=relation['raw']),
                terms=terms, persona_effects=list(persona.values()), memory_effects=list(evidence.values()),
                relationship_effects=relation['contributions'])

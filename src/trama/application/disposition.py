"""Avaliação social, evidência relevante e reutilização de resultados por pedido."""

from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
import logging

from trama.actions import ActionError
from trama.characters import ability_check
from trama.social import SocialError, evaluate_disposition, profile_from_data
from trama.opinions import evaluate_option
from trama.relationships import DIMENSION_WEIGHT, LEVEL_LIMIT, RELATIONSHIP_CAP

logger = logging.getLogger(__name__)


def signature(memory):
    return (memory.claim.subject_id, memory.claim.predicate, memory.claim.value.casefold().strip(),
            memory.source.kind, memory.source.actor_id)


def opinion_basis_key(profile, memories, relationships=()):
    def stable(value):
        if isinstance(value, dict):
            return {k: stable(v) for k, v in value.items() if k != 'event_id'}
        if isinstance(value, (tuple, list)):
            return [stable(v) for v in value]
        return value
    def evidence_signature(m):
        return (m.claim.subject_id, m.claim.predicate, m.claim.value,
                m.source.kind, m.source.actor_id, tuple(sorted(m.topics)))
    latest = {}
    for memory in memories:
        if memory.claim not in latest or memory.acquired_at > latest[memory.claim].acquired_at:
            latest[memory.claim] = memory
    eligible = lambda values: sorted({evidence_signature(m) for m in values
        if any(i.relevant(m) for i in profile.persona.interests)}, key=repr)
    data = dict(profile=asdict(profile), memories=eligible(memories), selected_sources=eligible(latest.values()),
                relationships=stable(relationships))
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class DispositionSystem:
    def __init__(self, session, profiles):
        self.session = session
        self.profiles = {o.id: profiles.get(o.id) or profile_from_data({}, o.name)
                         for o in (*session.creatures, *session.observers)}
        if set(profiles) - set(self.profiles):
            raise SocialError('Perfil social pertence a NPC inexistente.')
        self.decisions = {}
        self.opinions = []
        self._opinion_cache = {}

    def opinion_context(self, actor_id):
        """Últimas opções privadas; histórico completo e motivos permanecem nos logs."""
        result = deepcopy([v for v in self.opinions if v['actor_id'] == actor_id][-4:])
        # O contexto conserva motivos por termo, sem duplicá-los na agregação.
        for option in result:
            option['current'] = self.opinion_is_current(option)
            option.pop('persona_effects', None)
            option.pop('memory_effects', None)
        while len(result) > 1 and len(json.dumps(result, ensure_ascii=False)) > 24000:
            result.pop(0)
        return result

    def opinion_is_current(self, opinion):
        actor = opinion['actor_id']
        if opinion.get('basis_key') != opinion_basis_key(self.profiles[actor], self.session.knowledge.store.active(actor),
                                                      self.session.relationships.basis(actor)):
            return False
        try:
            frame = self.session.conversations.engagement(actor, opinion['conversation_id'])
            if frame['status'] != 'active':
                return False
            if opinion.get('proposal_id'):
                basis = self.session.conversations.opinion_basis(actor, opinion['conversation_id'], opinion['proposal_id'])
                return (not basis['withdrawn'] and basis['version'] == opinion['version']
                        and basis['terms'] == opinion['proposal_terms'])
            return True
        except ValueError:
            return False

    def assess_options(self, assessments):
        # O lote inteiro é validado antes de gravar qualquer opinião.
        prepared = []
        for assessment in assessments:
            actor = assessment.actor_id
            if actor not in self.profiles:
                raise ActionError('A opinião pertence a um NPC inexistente.')
            try:
                basis = self.session.conversations.opinion_basis(actor, assessment.conversation_id,
                    assessment.proposal_id, assessment.version)
                terms = assessment.terms
                if assessment.kind == 'proposal':
                    known = basis['terms']
                    by_id = {t['id']: t for t in known}
                    resolved = []
                    for term in terms:
                        ref = term.term_id
                        if ref.startswith('at:') and ref[3:] in {str(n) for n in range(1, len(known) + 1)}:
                            ref = known[int(ref[3:]) - 1]['id']
                        if ref not in by_id or term.description != by_id[ref]['text']:
                            raise SocialError('A opinião deve citar o id e o texto literal de cada termo conhecido.')
                        resolved.append(replace(term, term_id=ref, kind=by_id[ref]['kind'],
                            actor_id=by_id[ref]['actor_id'], execution_order=by_id[ref]['order']))
                    if len(resolved) != len(known) or {t.term_id for t in resolved} != set(by_id):
                        raise SocialError('Avalie todos os termos da versão exatamente uma vez.')
                    terms = tuple(resolved)
                resolved_assessment = replace(assessment, terms=terms, conversation_id=basis['conversation_id'],
                    proposal_id=basis.get('proposal_id'), version=basis.get('version'))
                profile = self.profiles[actor]
                memories = self.session.knowledge.store.active(actor)
                evaluation = evaluate_option(profile, resolved_assessment, memories, self.session.relationships)
            except ValueError as error:
                raise ActionError(str(error)) from error
            # Equivalência conservadora: mesmos termos literais normalizados e estrutura.
            # Não presume equivalência de paráfrases nem amplia o cache de Influence.
            canonical = (basis.get('terms', []) if assessment.kind == 'proposal' else
                [dict(text=t.description, id=t.term_id, kind=t.kind,
                      actor_id=t.actor_id, order=t.execution_order) for t in terms])
            canonical = [{k: (' '.join(v.split()) if k == 'text' else v)
                          for k, v in t.items() if k != 'id' or assessment.kind != 'proposal'} for t in canonical]
            basis_key = opinion_basis_key(profile, memories, self.session.relationships.basis(actor))
            cache_data = dict(actor=actor, conversation_id=basis['conversation_id'], kind=assessment.kind,
                option_id=assessment.option_id, proposer_id=basis.get('proposer_id'), terms=canonical, basis_key=basis_key,
                alternative_base=basis.get('terms') if assessment.kind == 'alternative' else None)
            digest = hashlib.sha256(json.dumps(cache_data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if any(key == digest for key, _ in prepared):
                raise ActionError('O lote repete a mesma opção equivalente.')
            previous = self._opinion_cache.get(digest)
            value = dict(evaluation, actor_id=actor, **basis, kind=assessment.kind,
                option_id=assessment.option_id, description=assessment.description,
                expectation=assessment.kind == 'no_agreement', fingerprint=digest, reused=False)
            # basis.terms descreve a proposta; a avaliação detalhada deve permanecer em terms.
            value['proposal_terms'] = basis.get('terms', [])
            value['terms'] = evaluation['terms']
            if previous:
                value = dict(deepcopy(previous), **{k: v for k, v in basis.items() if k != 'terms'}, reused=True)
                # IDs de termos de uma oferta repetida podem ser novos, embora o conteúdo seja igual.
                if assessment.kind == 'proposal':
                    mapping = {old['id']: new['id'] for old, new in zip(previous['proposal_terms'], basis['terms'])}
                    def rebind(item):
                        if isinstance(item, dict):
                            return {k: mapping.get(v, v) if k == 'term_id' else rebind(v) for k, v in item.items()}
                        return [rebind(v) for v in item] if isinstance(item, list) else item
                    value = rebind(value)
                    value['proposal_terms'] = basis['terms']
                    descriptions = {t['id']: t['text'] for t in basis['terms']}
                    for term in value['terms']:
                        term['description'] = descriptions[term['term_id']]
            value.update(id=f'opinion_{len(self.opinions) + len(prepared) + 1}', basis_key=basis_key)
            prepared.append((digest, value))
        for digest, value in prepared:
            self._opinion_cache[digest] = deepcopy(value)
            self.opinions.append(deepcopy(value))
            logger.info('social.option_evaluated', extra={'data': value})
            self.session.agency.acknowledge_knowledge(value['actor_id'])
        return deepcopy([v for _, v in prepared])

    def context(self, actor_ids):
        return {'profiles': [dict(actor_id=id, **self.profiles[id].context()) for id in actor_ids if id in self.profiles],
                'relationships': [r for id in actor_ids if id in self.profiles
                                  for r in self.session.bonds.context(id)],
                'opinions': [v for id in actor_ids for v in self.opinion_context(id)],
                'decisions': [deepcopy(v['event']) for k, v in self.decisions.items() if k[0] in actor_ids][-8:],
                'policy': {'willing_at': 3, 'unwilling_at': -3, 'alignment_cap': 2,
                           'persona_cap': 6, 'memory_cap': 3, 'relationship_range': [-LEVEL_LIMIT, LEVEL_LIMIT],
                           'relationship_weight': DIMENSION_WEIGHT, 'relationship_cap': RELATIONSHIP_CAP,
                           'same_request': 'Reutilizar resultado sem nova informação relevante; não rerrolar por reformulação.'}}

    def resolve(self, actor_id, request, reason):
        s = self.session
        assessment = request.assessment
        if assessment is None:
            raise ActionError('A disposição inicial exige avaliação de alinhamento, persona e memórias.')
        known_targets = {s.encounter.player_id, *self.profiles}
        if s.scene is not None:
            known_targets.update(o.id for o in s.scene.objects)
        if assessment.target_id not in known_targets:
            raise ActionError('A disposição exige um alvo conhecido na cena.')
        profile = self.profiles[actor_id]
        memories = s.knowledge.store.active(actor_id)
        try:
            evaluation = evaluate_disposition(profile, assessment, memories)
        except SocialError as error:
            raise ActionError(str(error)) from error
        eligible = {signature(m) for m in memories if any(i.relevant(m) for i in profile.persona.interests)}
        cited = {signature(m) for m in memories for e in assessment.memory_effects if e.effect and m.claim == e.claim}
        key = actor_id, *assessment.key
        previous = self.decisions.get(key)
        novel = cited - previous['known'] if previous else set()
        if previous and not novel:
            previous['known'] |= eligible
            event = deepcopy(previous['event'])
            event.update(reused=True, reevaluated=False, relevant_change=False)
            s.agency.acknowledge_knowledge(actor_id)
            return event
        willingness = evaluation['willingness']
        event = dict(operation='influence', actor_id=actor_id, text=reason, changed=True, perceptible=True,
                     willingness=willingness, skill=request.skill, attitude=request.attitude,
                     disposition=evaluation, reused=False, reevaluated=previous is not None,
                     relevant_change=bool(novel))
        accepted = willingness == 'willing'
        if willingness == 'hesitant':
            if request.skill is None:
                raise ActionError('Um NPC hesitante exige a perícia apropriada para Influence.')
            dc = max(15, s.encounter.sheets[actor_id].abilities.intelligence) if actor_id in s.encounter.sheets else 15
            player = s.encounter.player_id
            state, roll, total = ability_check(s.encounter.player_sheet, s.encounter.states[player], request.skill,
                dc, s.encounter.roller, advantage=request.attitude == 'friendly', disadvantage=request.attitude == 'hostile')
            s.encounter.states[player] = state
            accepted = total >= dc
            event.update(dc=dc, dice=list(roll.dice), total=total, passed=accepted,
                         advantage=roll.advantage, disadvantage=roll.disadvantage)
        event.update(accepted=accepted,
                     response_text=assessment.accepted_reply if accepted else assessment.refused_reply,
                     concession=(dict(goal=assessment.goal, target_id=assessment.target_id,
                                      description=assessment.description, conditions=list(assessment.conditions)) if accepted else None))
        self.decisions[key] = {'known': eligible, 'event': deepcopy(event)}
        logger.info('social.disposition_resolved', extra={'data': event})
        s.agency.acknowledge_knowledge(actor_id)
        return event

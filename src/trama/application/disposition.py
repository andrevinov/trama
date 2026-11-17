"""Avaliação social, evidência relevante e reutilização de resultados por pedido."""

from copy import deepcopy
import logging

from trama.actions import ActionError
from trama.characters import ability_check
from trama.social import SocialError, evaluate_disposition, profile_from_data

logger = logging.getLogger(__name__)


def signature(memory):
    return (memory.claim.subject_id, memory.claim.predicate, memory.claim.value.casefold().strip(),
            memory.source.kind, memory.source.actor_id)


class DispositionSystem:
    def __init__(self, session, profiles):
        self.session = session
        self.profiles = {o.id: profiles.get(o.id) or profile_from_data({}, o.name)
                         for o in (*session.creatures, *session.observers)}
        if set(profiles) - set(self.profiles):
            raise SocialError('Perfil social pertence a NPC inexistente.')
        self.decisions = {}

    def context(self, actor_ids):
        return {'profiles': [dict(actor_id=id, **self.profiles[id].context()) for id in actor_ids if id in self.profiles],
                'decisions': [deepcopy(v['event']) for k, v in self.decisions.items() if k[0] in actor_ids][-8:],
                'policy': {'willing_at': 3, 'unwilling_at': -3, 'alignment_cap': 2,
                           'persona_cap': 6, 'memory_cap': 3,
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
        return event

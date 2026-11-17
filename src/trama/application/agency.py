"""Acompanhamento de interlocutores no modo narrado; sem relógio de tempo real."""

from copy import deepcopy
from dataclasses import asdict
import logging

from trama.actions import ActionError
from trama.agency import IntentDecision

logger = logging.getLogger(__name__)


class AgencySystem:
    def __init__(self, session):
        self.session = session
        self.intents = {}

    def engage(self, actor_id, waiting_for):
        self.intents[actor_id] = dict(actor_id=actor_id, goal='Concluir a abordagem e obter uma resposta.',
            activity='Aguardando resposta à abordagem.', waiting_for=waiting_for[:300],
            unattended_interactions=0, waits_used=0)

    def answered(self, actor_id, reply):
        if actor_id in self.intents:
            self.intents[actor_id].update(activity='Acompanhando a negociação em curso.',
                waiting_for=reply[:300], unattended_interactions=0, waits_used=0)

    def pending(self, report, previous):
        s = self.session
        meaningful = report.progress or any(e['operation'] in {'speak','challenge','wait'} for e in report.events)
        if s.encounter.combat or not meaningful:
            return []
        acted = {e.get('actor_id') for e in report.world_events if e['operation'] in
                 {'say', 'influence', 'parley', 'move', 'start_conflict', 'resume_activity'}}
        result = []
        for actor in previous:
            if actor not in self.intents or actor in acted:
                continue
            try:
                observer = s.perception.observer(actor)
            except ActionError:
                self.close(actor)
                continue
            if s.perception.sleeping(observer):
                continue
            # Uma troca só provoca acompanhamento se chegar ao NPC por algum
            # sentido. Lembrança de posição não é visão ou audição atuais.
            heard = any(actor in e['heard_by'] for e in s.knowledge.communications[-8:]
                        if e['sequence'] > previous[actor])
            if not s.npc_sees_player(actor) and not heard:
                continue
            self.intents[actor]['unattended_interactions'] += 1
            result.append(actor)
        return result

    def checkpoint(self):
        sequence = self.session.knowledge.communication_sequence
        return {actor: sequence for actor in self.intents}

    def context(self, actor):
        intent = deepcopy(self.intents[actor])
        intent['can_wait'] = intent['waits_used'] == 0
        observer = self.session.perception.observer(actor)
        visible_player = self.session.npc_sees_player(actor)
        return dict(actor_id=actor, intent=intent, sees_player=visible_player,
            observed_player_position=([self.session.state.position.x + 1, self.session.state.position.y + 1]
                                      if visible_player else None),
            communications=self.session.knowledge.communications_for(actor),
            policy='Uma decisão após a interação resolvida. Palavras inaudíveis não são conhecimento. '
                   'Uma espera fundamentada por resposta; novas esperas exigem resposta real ao NPC.')

    def validate(self, actor, plan):
        decision = plan.intent
        if not isinstance(decision, IntentDecision) or decision.actor_id != actor or actor not in self.intents:
            raise ActionError('O acompanhamento exige uma intenção do NPC solicitado.')
        actions = [a for r in plan.reactions for a in r.actions]
        allowed = {'say', 'wait', 'start_conflict', 'resume_activity'}
        if (not actions or len(actions) > 3 or any(a.actor_id != actor or a.operation not in allowed for a in actions)
                or any(r.step_index != 0 or r.after_squares is not None or r.interrupt or r.check for r in plan.reactions)):
            raise ActionError('O acompanhamento exige ações próprias, após a interação, sem movimento ou ataque gratuitos.')
        waiting = any(a.operation == 'wait' for a in actions)
        if waiting and (len(actions) != 1 or self.intents[actor]['waits_used'] or decision.waiting_for is None):
            raise ActionError('Uma espera precisa de motivo e não pode ser renovada sem resposta ao NPC.')
        terminal = [i for i, a in enumerate(actions) if a.operation in {'start_conflict','resume_activity'}]
        if len(terminal) > 1 or terminal and terminal[0] != len(actions)-1:
            raise ActionError('A mudança de situação encerra o acompanhamento deste NPC.')
        for action in actions:
            if action.operation == 'say':
                self.session.knowledge.references(actor, action.memory_ids)
            if action.operation == 'resume_activity' and (not self.session.parley_pending
                    or self.session.parley.actor_id != actor):
                raise ActionError('Esse NPC não participa de uma conversa ativa para encerrar.')
        return actions

    def apply(self, decision, actions):
        if decision.actor_id not in self.intents:
            return  # A conversa foi encerrada ou começou combate.
        current = self.intents[decision.actor_id]
        current.update(asdict(decision))
        if any(a.operation == 'wait' for a in actions):
            current['waits_used'] += 1
        logger.info('agency.intent_updated', extra={'data': current.copy()})

    def close(self, actor):
        self.intents.pop(actor, None)

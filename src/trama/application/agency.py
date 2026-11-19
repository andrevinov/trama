"""Acompanhamento de interlocutores no modo narrado; sem relógio de tempo real."""

from copy import deepcopy
from dataclasses import asdict
import logging

from trama.actions import ActionError
from trama.agency import IntentDecision
from trama.observability import new_id

logger = logging.getLogger(__name__)


class AgencySystem:
    def __init__(self, session):
        self.session = session
        self.intents = {}
        self._offered = set()
        self._attempted = set()
        self._noticed = set()
        self._event_keys = set()
        self._pending_events = {}
        self._review_events = {}

    def _event(self, actor, key, data):
        if actor not in self.session.social.profiles:
            return
        frame = self.session.conversations.current_engagement(actor)
        if actor not in self.intents and frame is None:
            return
        if key in self._event_keys:
            return
        self._event_keys.add(key)
        self._pending_events.setdefault(actor, []).append(data)
        logger.info('agency.event_noticed', extra={'data': dict(actor_id=actor, **data)})

    def notice_memory(self, memory, position=None):
        s, actor = self.session, memory.owner_id
        if actor not in s.social.profiles or memory.claim.predicate in {
                'relationship_episode', 'relationship_bond', 'conversation_pending', 'conversation_commitment'}:
            return
        relevant = [i.id for i in s.social.profiles[actor].persona.interests if i.relevant(memory)]
        boundary = (memory.claim.predicate.startswith('romance_boundary:') and
                    (memory.claim.subject_id == actor or memory.claim.predicate == 'romance_boundary:' + actor))
        if not relevant and memory.claim.predicate != 'observed_injury' and not boundary:
            return
        key = (actor, memory.claim, memory.source.kind, memory.source.actor_id,
               memory.source.event_id if memory.source.kind == 'observation' else None)
        self._event(actor, key, dict(event_id=memory.source.event_id, kind='knowledge',
            memory_id=memory.id, interest_ids=relevant,
            position=[position.x + 1, position.y + 1] if position is not None else None))

    def notice_noise(self, actor, event_id, position=None):
        self._event(actor, (actor, event_id), dict(event_id=event_id, kind='noise',
            text='Ruído forte percebido; a causa e o autor não estão comprovados.',
            position=[position.x + 1, position.y + 1] if position is not None else None))

    def next_review(self, excluded):
        if self.session.encounter.combat:
            return None
        for actor in tuple(self._pending_events):
            if actor in excluded:
                continue
            try:
                observer = self.session.perception.observer(actor)
            except ActionError:
                self._pending_events.pop(actor)
                continue
            if self.session.perception.sleeping(observer):
                continue
            frame = self.session.conversations.current_engagement(actor)
            if frame is None and self.intents.get(actor, {}).get('conversation_id'):
                self.close(actor)
                self._pending_events.pop(actor)
                continue
            if frame is None and actor not in self.intents:
                self._pending_events.pop(actor)
                continue
            if actor not in self.intents:
                self.engage(actor, 'Reconsiderar um acontecimento percebido.')
                if frame:
                    self.intents[actor]['conversation_id'] = frame['conversation_id']
            batch = self._pending_events.pop(actor)
            self._review_events[actor] = batch[-4:]
            self.intents[actor].update(opportunity_id=new_id(), waits_used=0, event_opportunity=True)
            logger.info('agency.review_requested', extra={'data': dict(actor_id=actor,
                opportunity_id=self.intents[actor]['opportunity_id'], event_ids=[e['event_id'] for e in batch])})
            return actor
        return None

    def acknowledge_knowledge(self, actor):
        """A avaliação já executada considerou a base atual; não repetir a chamada."""
        remaining = [e for e in self._pending_events.get(actor, ()) if e['kind'] != 'knowledge']
        if remaining:
            self._pending_events[actor] = remaining
        else:
            self._pending_events.pop(actor, None)

    def acknowledge_preparation(self):
        """Os estímulos da preparação já integram a situação inicial, sem reencená-los."""
        self._pending_events.clear()
        self._review_events.clear()

    def engage(self, actor_id, waiting_for):
        self.intents[actor_id] = dict(actor_id=actor_id, goal='Concluir a abordagem e obter uma resposta.',
            activity='Aguardando resposta à abordagem.', waiting_for=waiting_for[:300],
            unattended_interactions=0, waits_used=0)

    def answered(self, actor_id, reply):
        if actor_id in self.intents:
            self.intents[actor_id].update(activity='Acompanhando a conversa em curso.',
                waiting_for=reply[:300], unattended_interactions=0, waits_used=0)

    def register_contribution(self, event_id, speaker):
        """Participação nasce da comunicação real, inclusive na preparação de situações."""
        if speaker != self.session.encounter.player_id:
            return []
        frames = self.session.conversations.engagements_for(event_id, speaker)
        for frame in frames:
            actor = frame['actor_id']
            if frame['status'] != 'active' or actor not in self.session.social.profiles:
                continue
            current = self.intents.get(actor)
            if current is None or current.get('conversation_id') != frame['conversation_id']:
                self.engage(actor, 'Uma contribuição do interlocutor.')
                self.intents[actor].update(conversation_id=frame['conversation_id'],
                    goal='Conduzir a conversa conforme seus interesses.', activity='Ouviu o interlocutor.')
        return frames

    def active(self, actor):
        current = self.intents.get(actor)
        return bool(current and (not current.get('conversation_id') or
            self.session.conversations.engagement(actor, current['conversation_id'])['status'] == 'active'
            or current.get('event_opportunity') and
            self.session.conversations.engagement(actor, current['conversation_id'])['status'] == 'suspended'))

    def pending(self, report, previous):
        s = self.session
        meaningful = report.progress or any(e['operation'] in {'speak','challenge','wait'} for e in report.events)
        if s.encounter.combat or not meaningful:
            return []
        acted = {e.get('actor_id') for e in report.world_events if e['operation'] in
                 {'say', 'wait', 'influence', 'parley', 'move', 'start_conflict', 'resume_activity'}}
        candidates = dict(previous)
        for event in report.events:
            if event['operation'] not in {'speak', 'challenge'} or not event.get('event_id'):
                continue
            for frame in self.register_contribution(event['event_id'], s.encounter.player_id):
                actor = frame['actor_id']
                if frame['status'] != 'active' or actor not in s.social.profiles:
                    continue
                if (actor, event['event_id']) in self._noticed:
                    continue
                self._noticed.add((actor, event['event_id']))
                current = self.intents[actor]
                if frame['responded'] or frame['continues']:
                    current.update(waits_used=0, unattended_interactions=0)
                if frame['objective']:
                    current.update({k: frame['objective'][k] for k in ('goal', 'waiting_for')})
                candidates.setdefault(actor, event['sequence'] - 1)
        for actor, current in tuple(self.intents.items()):
            if not self.active(actor):
                cid = current.get('conversation_id')
                if not cid or s.conversations.engagement(actor, cid)['status'] == 'closed':
                    self.close(actor)
        for event in report.events:
            if event['operation'] == 'gesture' and event.get('received'):
                actor = event['target_id']
                responded = any(e.get('actor_id') == actor and e['operation'] in {'say', 'wait', 'influence'}
                    and e.get('step_index') == event.get('step_index') and e.get('after_squares') is None
                    for e in report.world_events)
                if responded:
                    acted.add(actor)
                else:
                    acted.discard(actor)
                    if actor not in self.intents:
                        self.engage(actor, 'Responder ao gesto percebido.')
                        self.intents[actor].update(goal='Decidir como responder ao gesto observado, sem obediência automática.',
                                                  one_shot=True)
                    candidates.setdefault(actor, event['sequence'] - 1)
        result = []
        for actor in candidates:
            if actor not in self.intents or not self.active(actor) or actor in acted:
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
                        if e['sequence'] > candidates[actor])
            if not s.npc_sees_player(actor) and not heard:
                continue
            opportunity = report.execution_id or id(report)
            if (actor, opportunity) in self._offered:
                continue
            self._offered.add((actor, opportunity))
            self.intents[actor]['opportunity_id'] = opportunity
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
            events=[self._event_context(actor, e) for e in self._review_events.get(actor, ())],
            departure_targets=self.departure_targets(actor),
            policy='Uma decisão após a interação resolvida. Palavras inaudíveis não são conhecimento. '
                   'Uma espera fundamentada; nova fala dirigida na conversa pode renovar a escuta. '
                   'Conversas paralelas e passagem de tempo não a renovam.')

    def departure_targets(self, actor):
        """Um destino livre e visto em cada outra área; sem revelar posições ocultas."""
        s = self.session
        if s.scene is None or actor not in s.encounter.sheets:
            return []
        observer = s.perception.observer(actor)
        current = s.scene.area_at(observer.position)
        occupied = {s.state.position, *(o.position for o in s.perception.observers())}
        result = []
        for area in s.scene.areas:
            if current and area.id == current.id:
                continue
            cells = [p for p in area.cells if p not in s.grid.blocked and p not in occupied
                     and s.perception.sees(observer, p)]
            if cells:
                target = min(cells, key=lambda p: (max(abs(p.x-observer.position.x), abs(p.y-observer.position.y)), p.y, p.x))
                result.append(dict(area_id=area.id, name=area.name, position=[target.x+1, target.y+1]))
        return result[:8]

    def _event_context(self, actor, event):
        result = deepcopy(event)
        if event.get('memory_id'):
            result['memory'] = self.session.knowledge.store.get(actor, event['memory_id']).data()
            result['current'] = any(m.id == event['memory_id'] for m in self.session.knowledge.store.active(actor))
        return result

    def validate(self, actor, plan):
        decision = plan.intent
        if not isinstance(decision, IntentDecision) or decision.actor_id != actor or actor not in self.intents:
            raise ActionError('O acompanhamento exige uma intenção do NPC solicitado.')
        actions = [a for r in plan.reactions for a in r.actions]
        allowed = {'say', 'wait', 'start_conflict', 'resume_activity'}
        if self.intents[actor].get('event_opportunity'):
            allowed |= {'move', 'search'}
        if decision.initiative == 'leave':
            allowed.add('move')
        if (not actions or len(actions) > 3 or any(a.actor_id != actor or a.operation not in allowed for a in actions)
                or any(r.step_index != 0 or r.after_squares is not None or r.interrupt or r.check
                       or r.opinions or r.episodes or r.bonds for r in plan.reactions)):
            raise ActionError('O acompanhamento exige ações próprias, após a interação, sem movimento ou ataque gratuitos.')
        waiting = any(a.operation == 'wait' for a in actions)
        listening = decision.initiative == 'listen' and [a.operation for a in actions] in (['wait'], ['say', 'wait'])
        if waiting and (not listening and len(actions) != 1 or self.intents[actor]['waits_used'] or decision.waiting_for is None):
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
        self._validate_choice(actor, decision, actions)
        physical = [a for a in actions if a.operation in {'move', 'search'}]
        if decision.initiative == 'leave':
            if (not self.intents[actor].get('conversation_id') or self.session.parley_pending
                    or [a.operation for a in actions] != ['say', 'move']
                    or not actions[0].conversation or actions[0].conversation.status != 'closed'
                    or decision.waiting_for is not None
                    or [actions[1].destination.x+1, actions[1].destination.y+1] not in
                       [t['position'] for t in self.departure_targets(actor)]):
                raise ActionError('Sair exige despedida, conversa comum e destino livre percebido em outra área.')
        elif physical:
            if len(physical) > 1 or decision.initiative not in {'investigate', 'protect'}:
                raise ActionError('Investigar/proteger permite uma operação física suportada por incidente.')
            positions = [e['position'] for e in self._review_events.get(actor, ()) if e.get('position')]
            for action in physical:
                if action.operation == 'move' and not any(
                        max(abs(action.destination.x + 1 - p[0]), abs(action.destination.y + 1 - p[1])) <= 1
                        for p in positions):
                    raise ActionError('O deslocamento precisa de localização percebida do incidente; ruído não revela coordenadas ocultas.')
        return actions

    def _validate_choice(self, actor, decision, actions):
        current = self.intents[actor]
        opportunity = current.get('opportunity_id')
        if opportunity is not None and (actor, opportunity) in self._attempted:
            raise ActionError('O NPC já decidiu nesta oportunidade de acompanhamento.')
        cid = current.get('conversation_id')
        status = self.session.conversations.engagement(actor, cid)['status'] if cid else 'active'
        if status != 'active' and not (status == 'suspended' and current.get('event_opportunity')):
            raise ActionError('A conversa precisa estar ativa ou ter incidente percebido para reconsideração.')
        if cid and decision.initiative is None:
            raise ActionError('Uma conversa comum exige iniciativa e motivo privados explícitos.')
        if cid and any(a.conversation and a.conversation.conversation_id not in {None, cid} for a in actions):
            raise ActionError('A iniciativa só pode atualizar a conversa acompanhada nesta oportunidade.')
        offered = {o['id']: o for o in self.session.social.opinion_context(actor)
                   if o['current'] and (cid is None or o['conversation_id'] == cid)}
        if any(id not in offered for id in decision.opinion_ids):
            raise ActionError('A iniciativa cita opinião desconhecida, desatualizada ou de outra conversa.')
        if decision.initiative is None:
            return  # Leitura local dos acompanhamentos anteriores à conversa estruturada.
        kinds = [a.operation for a in actions]
        proposals = [(a, a.conversation.proposal) for a in actions if a.conversation and a.conversation.proposal]
        if decision.initiative == 'listen' and kinds not in (['wait'], ['say', 'wait']):
            raise ActionError('Ouvir exige espera fundamentada, com acolhimento verbal opcional antes dela.')
        if decision.initiative != 'listen' and 'wait' in kinds:
            raise ActionError('Uma espera isolada deve declarar a iniciativa de ouvir.')
        if decision.initiative == 'start_conflict' and (kinds[-1] != 'start_conflict' or decision.opinion_ids):
            raise ActionError('Conflito exige causa própria; uma nota social não justifica violência.')
        if 'start_conflict' in kinds and decision.initiative != 'start_conflict':
            raise ActionError('O plano precisa declarar a decisão de iniciar conflito.')
        closing = any(a.conversation and a.conversation.status == 'closed' for a in actions)
        suspending = any(a.conversation and a.conversation.status == 'suspended' for a in actions)
        resuming = any(a.conversation and a.conversation.status == 'active' for a in actions)
        if decision.initiative in {'investigate', 'protect', 'suspend', 'resume'} and not current.get('event_opportunity'):
            raise ActionError('Essa iniciativa exige acontecimento novo percebido.')
        if decision.initiative == 'suspend' and not suspending:
            raise ActionError('Suspender exige comunicar a interrupção, preservando os assuntos.')
        if suspending and decision.initiative not in {'suspend', 'investigate', 'protect', 'start_conflict'}:
            raise ActionError('A interrupção precisa de iniciativa explícita pertinente ao incidente.')
        if decision.initiative == 'resume' and (status != 'suspended' or not resuming):
            raise ActionError('Retomar exige conversa suspensa e retomada comunicada.')
        if status == 'suspended' and resuming and decision.initiative != 'resume':
            raise ActionError('Declare a decisão de retomar o encontro suspenso.')
        if decision.initiative in {'close', 'leave'} and not closing and (cid or 'resume_activity' not in kinds):
            raise ActionError('Encerrar exige despedida registrada ou retomada de atividade permitida.')
        if (closing or 'resume_activity' in kinds) and decision.initiative not in {'close', 'leave'}:
            raise ActionError('O plano precisa declarar a decisão de encerrar.')
        expected = {'accept': 'accept', 'reject': 'reject', 'counteroffer': 'offer'}.get(decision.initiative)
        if expected and (len(proposals) != 1 or proposals[0][1].action not in (
                {'offer', 'revise'} if expected == 'offer' else {expected})):
            raise ActionError('A iniciativa precisa registrar sua resposta concreta à proposta.')
        if any(p.action in {'accept', 'reject', 'offer', 'revise'} for _, p in proposals) and not expected:
            raise ActionError('A resposta sobre proposta precisa declarar aceitar, recusar ou contrapropor.')
        if expected:
            if cid is None or not decision.opinion_ids:
                raise ActionError('Decidir sobre proposta exige opiniões calculadas antes desta decisão.')
            proposal = proposals[0][1]
            reference = proposal.in_reply_to if proposal.action == 'offer' else proposal.proposal_id
            if not reference:
                raise ActionError('A resposta precisa identificar a proposta de base.')
            basis = self.session.conversations.opinion_basis(actor, cid, reference, proposal.version)
            if proposal.action == 'revise' and basis['proposer_id'] != actor:
                raise ActionError('Só o autor pode revisar a própria proposta.')
            if expected != 'offer' and basis['proposer_id'] == actor:
                raise ActionError('O autor não aceita nem recusa sua própria oferta.')
            chosen = [offered[id] for id in decision.opinion_ids]
            kind = 'alternative' if expected == 'offer' else 'proposal'
            matching = [o for o in chosen if o['kind'] == kind and o.get('proposal_id') == basis.get('proposal_id')
                        and o.get('version') == basis.get('version')]
            if not matching or basis.get('withdrawn'):
                raise ActionError('A resposta precisa de avaliação atual da opção e versão correspondentes.')
            if expected == 'offer' and not any(self._offered_terms(proposal, basis) ==
                    [(t['description'], t['kind'], t['actor_id'], t['execution_order']) for t in o['terms']]
                    for o in matching):
                raise ActionError('A contraproposta falada deve corresponder aos termos da alternativa avaliada.')

    @staticmethod
    def _offered_terms(update, basis):
        terms = deepcopy(basis['terms']) if update.action == 'revise' else []
        known = {t['id'] for t in terms}
        if not set(update.remove_term_ids) <= known or any(t.id and t.id not in known for t in update.terms):
            raise ActionError('A revisão cita termo inexistente na proposta.')
        terms = [t for t in terms if t['id'] not in update.remove_term_ids]
        for term in update.terms:
            value = dict(id=term.id, text=term.text, kind=term.kind, actor_id=term.actor_id, order=term.order)
            if term.id is None:
                terms.append(value)
            else:
                terms = [value if t['id'] == term.id else t for t in terms]
        return [(t['text'], t['kind'], t['actor_id'], t['order']) for t in terms]

    def begin(self, actor, decision):
        opportunity = self.intents[actor].get('opportunity_id')
        event_id = new_id()
        if opportunity is not None:
            self._attempted.add((actor, opportunity))
        logger.info('agency.choice_validated', extra={'data': dict(asdict(decision),
            conversation_id=self.intents[actor].get('conversation_id'), opportunity_id=opportunity, event_id=event_id)})
        return event_id

    def apply(self, decision, actions, *, conversation_id=None, event_id=None):
        if conversation_id:
            self.session.conversations.set_objective(decision.actor_id, conversation_id, decision.goal,
                None if decision.initiative in {'close', 'leave', 'start_conflict'} else decision.waiting_for, event_id or new_id())
        if decision.actor_id not in self.intents:
            return  # A conversa foi encerrada ou começou combate.
        current = self.intents[decision.actor_id]
        current.update(asdict(decision))
        cid = current.get('conversation_id')
        if any(a.operation == 'wait' for a in actions):
            current['waits_used'] += 1
        current.pop('event_opportunity', None)
        self._review_events.pop(decision.actor_id, None)
        logger.info('agency.intent_updated', extra={'data': current.copy()})
        if (current.get('one_shot') or decision.initiative in {'close', 'leave'}
                or cid and self.session.conversations.engagement(decision.actor_id, cid)['status'] == 'closed'):
            self.close(decision.actor_id)

    def close(self, actor):
        self.intents.pop(actor, None)
        self._review_events.pop(actor, None)

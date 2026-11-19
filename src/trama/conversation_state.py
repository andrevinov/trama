"""Estado semântico das conversas; política do Trama, sem IA ou efeitos físicos.

Atualizações descrevem uma fala já validada. A aplicação fornece autor, evento e
ouvintes reais; a interpretação do significado continua sendo uma proposta da IA.
"""

from copy import deepcopy
from dataclasses import dataclass, fields, replace
import json


POINT_KINDS = ('statement', 'question', 'request', 'offer', 'condition', 'objection', 'topic')
TERM_KINDS = ('request', 'counterpart', 'condition')
PROPOSAL_ACTIONS = ('offer', 'revise', 'accept', 'reject', 'withdraw')
STATUSES = ('active', 'suspended', 'closed')


class ConversationStateError(ValueError):
    pass


def _text(value, maximum=400):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def _optional(value, maximum=160):
    return value is None or _text(value, maximum)


def _ids(value, maximum=8):
    return (isinstance(value, tuple) and len(value) <= maximum
            and all(_text(v, 120) for v in value) and len(set(value)) == len(value))


@dataclass(frozen=True)
class ConversationPoint:
    kind: str
    text: str

    def __post_init__(self):
        if self.kind not in POINT_KINDS or not _text(self.text):
            raise ConversationStateError('Assunto de conversa inválido.')


@dataclass(frozen=True)
class ProposalTerm:
    id: str | None
    kind: str
    text: str
    actor_id: str | None = None
    order: int | None = None

    def __post_init__(self):
        if (not _optional(self.id, 120) or self.kind not in TERM_KINDS or not _text(self.text)
                or not _optional(self.actor_id, 120)
                or self.order is not None and (type(self.order) is not int or not 1 <= self.order <= 8)):
            raise ConversationStateError('Termo de proposta inválido.')


@dataclass(frozen=True)
class ProposalUpdate:
    action: str
    proposal_id: str | None = None
    version: int | None = None
    in_reply_to: str | None = None
    terms: tuple[ProposalTerm, ...] = ()
    remove_term_ids: tuple[str, ...] = ()

    def __post_init__(self):
        if (self.action not in PROPOSAL_ACTIONS or not _optional(self.proposal_id, 120)
                or not _optional(self.in_reply_to, 120)
                or self.version is not None and (type(self.version) is not int or self.version < 1)
                or not isinstance(self.terms, tuple) or len(self.terms) > 8
                or any(not isinstance(t, ProposalTerm) for t in self.terms)
                or not _ids(self.remove_term_ids)):
            raise ConversationStateError('Alteração de proposta inválida.')
        ids = [t.id for t in self.terms if t.id is not None]
        if len(ids) != len(set(ids)) or set(ids) & set(self.remove_term_ids):
            raise ConversationStateError('Termos repetidos ou removidos e alterados ao mesmo tempo.')
        if self.action == 'offer':
            if self.proposal_id is not None or self.version is not None or not self.terms or ids or self.remove_term_ids:
                raise ConversationStateError('Oferta nova exige termos novos, sem id ou versão anteriores.')
        elif self.proposal_id is None or self.in_reply_to is not None:
            raise ConversationStateError('Informe a proposta existente, sem criar uma contraproposta implícita.')
        elif self.action != 'revise' and (self.terms or self.remove_term_ids):
            raise ConversationStateError('Aceitar, recusar ou retirar não altera termos.')
        elif self.action == 'revise' and not (self.terms or self.remove_term_ids):
            raise ConversationStateError('A revisão precisa alterar algum termo.')


@dataclass(frozen=True)
class ConversationUpdate:
    conversation_id: str | None = None
    target_ids: tuple[str, ...] = ()
    focus: str | None = None
    points: tuple[ConversationPoint, ...] = ()
    resolves: tuple[str, ...] = ()
    proposal: ProposalUpdate | None = None
    goal: str | None = None
    waiting_for: str | None = None
    status: str | None = None
    reason: str | None = None
    romance_boundary: str | None = None
    boundary_text: str | None = None
    romantic_expression: bool = False

    def __post_init__(self):
        if (not _optional(self.conversation_id, 120) or not _ids(self.target_ids)
                or not _optional(self.focus) or not _ids(self.resolves)
                or not isinstance(self.points, tuple) or len(self.points) > 8
                or any(not isinstance(p, ConversationPoint) for p in self.points)
                or self.proposal is not None and not isinstance(self.proposal, ProposalUpdate)
                or not _optional(self.goal, 300) or not _optional(self.waiting_for, 300)
                or self.status is not None and self.status not in STATUSES
                or not _optional(self.reason, 300)
                or self.reason is not None and self.status is None
                or self.status in {'suspended', 'closed'} and self.reason is None
                or self.romance_boundary is not None and self.romance_boundary not in {'open', 'declined'}
                or not _optional(self.boundary_text, 400)
                or (self.romance_boundary is None) != (self.boundary_text is None)
                or type(self.romantic_expression) is not bool
                or (self.romance_boundary is not None or self.romantic_expression) and len(self.target_ids) != 1):
            raise ConversationStateError('Contribuição de conversa inválida.')

    def validate_source(self, text, *, actor_id, player_id):
        # Foco é um rótulo do assunto, não uma citação ou compromisso falado.
        fragments = [p.text for p in self.points]
        if self.reason is not None:
            fragments.append(self.reason)
        if self.boundary_text:
            fragments.append(self.boundary_text)
        if self.proposal:
            fragments += [t.text for t in self.proposal.terms]
        if any(fragment not in text for fragment in fragments):
            raise ConversationStateError('Ponto, motivo, limite ou termo não pertence à fala executada.')
        if actor_id == player_id and (self.goal is not None or self.waiting_for is not None):
            raise ConversationStateError('A interpretação não atribui objetivos privados ao jogador.')


def conversation_update_from_data(value):
    """Lê metadados opcionais de gravações locais; rejeita campos e tipos extras."""
    if value is None:
        return None

    def checked(data, cls):
        if not isinstance(data, dict) or data.keys() - {f.name for f in fields(cls)}:
            raise ConversationStateError('Campos de conversa desconhecidos.')
        return dict(data)

    def sequence(data, name):
        result = data.get(name, [])
        if not isinstance(result, (list, tuple)):
            raise ConversationStateError(f'{name} deve ser uma lista.')
        return result

    try:
        data = checked(value, ConversationUpdate)
        data['points'] = tuple(ConversationPoint(**checked(p, ConversationPoint)) for p in sequence(data, 'points'))
        for name in ('target_ids', 'resolves'):
            data[name] = tuple(sequence(data, name))
        proposal = data.get('proposal')
        if proposal is not None:
            proposal = checked(proposal, ProposalUpdate)
            proposal['terms'] = tuple(ProposalTerm(**checked(t, ProposalTerm)) for t in sequence(proposal, 'terms'))
            proposal['remove_term_ids'] = tuple(sequence(proposal, 'remove_term_ids'))
            data['proposal'] = ProposalUpdate(**proposal)
        return ConversationUpdate(**data)
    except (TypeError, KeyError) as error:
        raise ConversationStateError('Dados de conversa inválidos.') from error


class ConversationState:
    """Registro em processo, com versões imutadas e projeções por ouvinte."""

    def __init__(self):
        self._records = []
        self._events = set()
        self._sequence = 0
        self._point_number = 0
        self._proposal_number = 0
        self._term_number = 0

    @staticmethod
    def _visible(record, actor):
        return sorted([e for e in (*record['contributions'], *record.get('interruptions', ()))
                       if actor in e['heard_by']], key=lambda e: e['sequence'])

    def current_engagement(self, actor):
        for record in reversed(self._records):
            if actor in record['participants'] and self._visible(record, actor):
                frame = self.engagement(actor, record['id'])
                if frame['status'] != 'closed':
                    return frame
        return None

    def interrupt_combat(self, participants, event_id):
        """Interrupção física por participante, sem fabricar uma fala ou resolver pontos."""
        for record in self._records:
            for actor in sorted(set(participants) & set(record['participants'])):
                visible = self._visible(record, actor)
                if not visible or self._status(visible)[0] != 'active':
                    continue
                self._sequence += 1
                record.setdefault('interruptions', []).append(dict(sequence=self._sequence,
                    actor_id=actor, event_id=event_id, heard_by=[actor], addressed_ids=[], focus=None,
                    status='suspended', reason='O combate interrompeu o encontro.', medium='incident'))

    def _select(self, actor, update, heard):
        if update and update.conversation_id:
            record = next((r for r in self._records if r['id'] == update.conversation_id and self._visible(r, actor)), None)
            if record is None:
                raise ConversationStateError('A conversa não é conhecida pelo falante.')
            return record
        targets = set(update.target_ids) if update else set()
        for record in sorted(self._records, key=lambda r: max(
                (e['sequence'] for e in self._visible(r, actor)), default=0), reverse=True):
            events = self._visible(record, actor)
            if not events or self._status(events)[0] != 'active' or actor not in record['participants']:
                continue
            if (targets and targets <= set(record['participants']) or not targets
                    and set(record['participants']) & (heard - {actor})):
                return record
        return None

    @staticmethod
    def _status(events):
        changed = next((e for e in reversed(events) if e['status'] is not None), None)
        return (changed['status'], changed['reason']) if changed else ('active', None)

    def prepare(self, actor, text, heard_by, update, *, event_id, player_id, actor_ids, memory_revision=0):
        """Valida numa cópia antes da emissão; nenhum efeito se houver referência inválida."""
        if event_id in self._events:
            return self, None
        if update is not None:
            if not isinstance(update, ConversationUpdate):
                raise ConversationStateError('Metadados de conversa inválidos.')
            update.validate_source(text, actor_id=actor, player_id=player_id)
            if actor in update.target_ids or not set(update.target_ids) <= set(actor_ids):
                raise ConversationStateError('Destinatário de conversa inexistente ou igual ao falante.')
        heard = set(heard_by) | {actor}
        selected = self._select(actor, update, heard)
        if selected is None and (update is None or not update.target_ids):
            if update is not None:
                raise ConversationStateError('Uma conversa nova exige destinatário identificado.')
            return self, None
        candidate = deepcopy(self)
        if selected is None:
            record = dict(id=f'conversation_{len(candidate._records) + 1}', participants=[actor],
                          contributions=[], points=[], proposals=[], objectives={})
            candidate._records.append(record)
        else:
            record = next(r for r in candidate._records if r['id'] == selected['id'])
        candidate._append(record, actor, text, heard, update or ConversationUpdate(), event_id, player_id, memory_revision)
        candidate._events.add(event_id)
        return candidate, record['id']

    def _append(self, record, actor, text, heard, update, event_id, player_id, memory_revision):
        previous = self._visible(record, actor)
        if update.status == 'active' and update.reason is None:
            if previous and self._status(previous)[0] != 'active':
                raise ConversationStateError('Retomar uma conversa exige motivo literal na fala.')
            # Marcar como ativa uma conversa já ativa não é transição de ciclo.
            update = replace(update, status=None)
        if previous and self._status(previous)[0] != 'active' and update.status != 'active':
            status = self._status(previous)[0]
            if (update.status not in {None, status, *({'closed'} if status == 'suspended' else ())}
                    or update.focus is not None or update.proposal is not None
                    or update.resolves or update.goal is not None or update.waiting_for is not None
                    or update.romantic_expression or update.romance_boundary == 'open'
                    or any(p.kind != 'statement' for p in update.points)):
                raise ConversationStateError('Indique a retomada antes de acrescentar novos assuntos à conversa.')
        self._sequence += 1
        sequence = self._sequence
        addressed = [id for id in update.target_ids if id in heard]
        for id in (actor, *addressed):
            if id not in record['participants']:
                record['participants'].append(id)
        # Referências são resolvidas antes de acrescentar os pontos da própria fala.
        for reference in update.resolves:
            pending = [p for p in record['points'] if actor in p['heard_by']
                       and p['kind'] in {'question', 'request', 'objection', 'topic'}
                       and not any(actor in e['heard_by'] for e in p['resolutions'])]
            point = (next((p for p in reversed(pending) if p['actor_id'] != actor), None)
                     if reference == 'latest' else next((p for p in pending if p['id'] == reference), None))
            if point is None:
                raise ConversationStateError('Pendência desconhecida ou já resolvida para esse personagem.')
            point['resolutions'].append(dict(actor_id=actor, event_id=event_id, heard_by=sorted(heard)))
        if update.proposal:
            self._proposal(record, actor, update.proposal, heard, sequence, event_id,
                           set(record['participants']) | set(update.target_ids), memory_revision)
        for point in update.points:
            self._point_number += 1
            record['points'].append(dict(id=f'point_{self._point_number}', actor_id=actor,
                kind=point.kind, text=point.text, sequence=sequence, event_id=event_id,
                heard_by=sorted(heard), resolutions=[]))
        if actor != player_id and (update.goal is not None or update.waiting_for is not None):
            previous_goal = record['objectives'].get(actor, {}).get('goal')
            record['objectives'][actor] = dict(actor_id=actor, goal=update.goal or previous_goal, waiting_for=update.waiting_for,
                                               event_id=event_id)
        record['contributions'].append(dict(sequence=sequence, actor_id=actor, event_id=event_id,
            text=text, addressed_ids=addressed, heard_by=sorted(heard), focus=update.focus,
            status=update.status, reason=update.reason))

    def _proposal(self, record, actor, update, heard, sequence, event_id, participants, memory_revision):
        proposals = record['proposals']
        known = [p for p in proposals if any(actor in v['heard_by'] for v in p['versions'])]
        known.sort(key=lambda p: max(v['sequence'] for v in p['versions'] if actor in v['heard_by']))
        def find(reference):
            result = (known[-1] if known else None) if reference == 'latest' else next(
                (p for p in known if p['id'] == reference), None)
            if result is None:
                raise ConversationStateError('Proposta desconhecida para esse personagem.')
            return result
        if update.action == 'offer':
            reply = find(update.in_reply_to)['id'] if update.in_reply_to else None
            self._proposal_number += 1
            proposal = dict(id=f'proposal_{self._proposal_number}', actor_id=actor, in_reply_to=reply, versions=[])
            proposals.append(proposal)
            terms = []
        else:
            proposal = find(update.proposal_id)
            versions = [v for v in proposal['versions'] if actor in v['heard_by']]
            base = next((v for v in versions if v['number'] == update.version), None) if update.version else versions[-1]
            if base is None:
                raise ConversationStateError('Versão de proposta não percebida pelo personagem.')
            if update.action in {'revise', 'withdraw'}:
                if proposal['actor_id'] != actor or base is not proposal['versions'][-1]:
                    raise ConversationStateError('Só o autor pode alterar ou retirar a versão atual da proposta.')
            elif proposal['actor_id'] == actor:
                raise ConversationStateError('O autor oferece ou retira; não aceita nem recusa sua própria oferta.')
            if any(r['action'] == 'withdraw' and actor in r['heard_by'] for r in base['responses']):
                raise ConversationStateError('Essa proposta foi retirada.')
            if update.action in {'accept', 'reject'} and any(actor not in t['heard_by'] for t in base['terms']):
                raise ConversationStateError('O personagem não conhece todos os termos dessa versão.')
            if update.action != 'revise':
                base['responses'].append(dict(action=update.action, actor_id=actor, sequence=sequence,
                                              event_id=event_id, heard_by=sorted(heard), memory_revision=memory_revision))
                return
            terms = deepcopy(base['terms'])
        by_id = {t['id']: t for t in terms}
        if not set(update.remove_term_ids) <= by_id.keys():
            raise ConversationStateError('Termo removido não pertence à proposta.')
        terms = [t for t in terms if t['id'] not in update.remove_term_ids]
        for term in update.terms:
            if term.actor_id is not None and term.actor_id not in participants:
                raise ConversationStateError('O responsável pelo termo deve participar da conversa.')
            if term.id is not None and term.id not in by_id:
                raise ConversationStateError('Termo alterado não pertence à proposta.')
            if term.id is None:
                self._term_number += 1
            value = dict(id=term.id or f'term_{self._term_number}', kind=term.kind, text=term.text,
                         actor_id=term.actor_id, order=term.order, heard_by=sorted(heard), event_id=event_id,
                         memory_revision=memory_revision)
            if term.id is None:
                terms.append(value)
            else:
                terms = [value if t['id'] == term.id else t for t in terms]
        if not 1 <= len(terms) <= 8:
            raise ConversationStateError('Uma proposta precisa de 1 a 8 termos.')
        proposal['versions'].append(dict(number=len(proposal['versions']) + 1, terms=terms,
            sequence=sequence, event_id=event_id, heard_by=sorted(heard), responses=[]))

    def engagement(self, actor, conversation_id):
        record = next((r for r in self._records if r['id'] == conversation_id
                       and actor in r['participants'] and self._visible(r, actor)), None)
        if record is None:
            raise ConversationStateError('O acompanhamento exige conversa percebida e participação real.')
        return dict(conversation_id=record['id'], status=self._status(self._visible(record, actor))[0],
                    objective=deepcopy(record['objectives'].get(actor)))

    def engagements_for(self, event_id, speaker):
        """Interlocutores reais de uma fala executada; curiosos não ganham agência."""
        result = []
        for record in self._records:
            event = next((e for e in record['contributions'] if e['event_id'] == event_id
                          and e['actor_id'] == speaker), None)
            if event is None:
                continue
            for actor in record['participants']:
                if actor != speaker and actor in event['heard_by']:
                    result.append(dict(self.engagement(actor, record['id']), actor_id=actor,
                        directed=actor in event['addressed_ids'], responded=any(
                            p['actor_id'] == actor and any(r['event_id'] == event_id for r in p['resolutions'])
                            for p in record['points']),
                        continues=(actor in event['addressed_ids'] or len(record['participants']) == 2) and not any(
                            p['actor_id'] == actor and actor in p['heard_by']
                            and p['kind'] in {'question', 'request', 'objection'}
                            and not any(actor in r['heard_by'] for r in p['resolutions']) for p in record['points'])))
        return result

    def set_objective(self, actor, conversation_id, goal, waiting_for, event_id):
        if not _text(goal, 300) or not _optional(waiting_for, 300) or not _text(event_id, 160):
            raise ConversationStateError('Objetivo privado inválido.')
        self.engagement(actor, conversation_id)  # Identidade/perspectiva antes da escrita.
        record = next(r for r in self._records if r['id'] == conversation_id)
        record['objectives'][actor] = dict(actor_id=actor, goal=goal, waiting_for=waiting_for, event_id=event_id)

    def commitment(self, actor, conversation_id, proposal_id, version, term_id):
        basis = self.opinion_basis(actor, conversation_id, proposal_id, version)
        record = next(r for r in self._records if r['id'] == basis['conversation_id'])
        proposal = next(p for p in record['proposals'] if p['id'] == basis['proposal_id'])
        selected = next(v for v in proposal['versions'] if v['number'] == basis['version'])
        accepted = [r for r in selected['responses'] if r['action'] == 'accept' and actor in r['heard_by']]
        if not accepted:
            raise ConversationStateError('O episódio exige compromisso aceito e conhecido.')
        if term_id.startswith('at:') and term_id[3:] in {str(n) for n in range(1, len(selected['terms']) + 1)}:
            term_id = selected['terms'][int(term_id[3:]) - 1]['id']
        term = next((t for t in selected['terms'] if t['id'] == term_id and actor in t['heard_by']), None)
        if term is None:
            raise ConversationStateError('Termo de compromisso desconhecido.')
        return dict(conversation_id=record['id'], proposal_id=proposal['id'], version=selected['number'],
                    term_id=term['id'], actor_id=term['actor_id'],
                    memory_revision=max(term['memory_revision'], min(r['memory_revision'] for r in accepted)))

    def closure_memories(self, event_id):
        """Seleção estrutural percebida: pendências e termos; sem objetivos ou transcrição."""
        result = []
        for record in self._records:
            event = next((e for e in record['contributions'] if e['event_id'] == event_id and e['status'] == 'closed'), None)
            if event is None:
                continue
            for owner in event['heard_by']:
                participants = {id for e in self._visible(record, owner) for id in (e['actor_id'], *e['addressed_ids'])}
                entities = (record['id'], owner, *sorted(participants - {owner}))[:16]
                for point in record['points']:
                    if owner not in point['heard_by'] or point['kind'] not in {'question', 'request', 'objection', 'topic'}:
                        continue
                    resolved = any(owner in r['heard_by'] for r in point['resolutions'])
                    result.append(dict(owner_id=owner, subject_id=f"{record['id']}:{point['id']}",
                        predicate='conversation_pending', value='resolved_at_close' if resolved else 'unresolved_at_close',
                        text=f"{point['kind']}: {point['text']} — {'resolvido' if resolved else 'pendente'} ao encerrar.",
                        entities=entities))
                for proposal in record['proposals']:
                    for version in proposal['versions']:
                        if owner not in version['heard_by']:
                            continue
                        responses = [r for r in version['responses'] if owner in r['heard_by']]
                        status = responses[-1]['action'] if responses else 'offered'
                        for term in version['terms']:
                            if owner not in term['heard_by']:
                                continue
                            result.append(dict(owner_id=owner,
                                subject_id=f"{proposal['id']}:v{version['number']}:{term['id']}",
                                predicate='conversation_commitment', value=status,
                                text='Registro verbal; não comprova cumprimento. '
                                     f"Proposta de {proposal['actor_id']}, versão {version['number']}: {term['text']} "
                                     f"(responsável: {term['actor_id'] or 'não definido'}; resposta: {status}).", entities=entities))
        return result

    def opinion_basis(self, actor, conversation_id, proposal_id=None, version=None):
        """Referências percebidas completas, independentes dos recortes do contexto."""
        records = [r for r in self._records if self._visible(r, actor)]
        records.sort(key=lambda r: max(e['sequence'] for e in self._visible(r, actor)))
        record = (records[-1] if records else None) if conversation_id == 'latest' else next(
            (r for r in records if r['id'] == conversation_id), None)
        if record is None:
            raise ConversationStateError('A opinião exige conversa percebida pelo NPC.')
        result = dict(conversation_id=record['id'])
        if proposal_id is None:
            return result
        known = [(p, v) for p in record['proposals'] for v in p['versions'] if actor in v['heard_by']]
        if proposal_id != 'latest':
            known = [(p, v) for p, v in known if p['id'] == proposal_id]
        if not known:
            raise ConversationStateError('A opinião exige proposta percebida pelo NPC.')
        proposal = max(known, key=lambda pv: pv[1]['sequence'])[0]
        versions = [v for p, v in known if p['id'] == proposal['id'] and (version is None or v['number'] == version)]
        if not versions:
            raise ConversationStateError('A opinião cita versão não percebida pelo NPC.')
        selected = max(versions, key=lambda v: v['sequence'])
        if any(actor not in t['heard_by'] for t in selected['terms']):
            raise ConversationStateError('A opinião exige conhecer todos os termos dessa versão.')
        return deepcopy(dict(result, proposal_id=proposal['id'], proposer_id=proposal['actor_id'], version=selected['number'],
            withdrawn=any(r['action'] == 'withdraw' and actor in r['heard_by'] for r in selected['responses']),
            terms=[{k: t[k] for k in ('id', 'kind', 'text', 'actor_id', 'order')} for t in selected['terms']]))

    def view(self, actor, *, limit=3, max_chars=10000):
        result, size = [], 0
        for record in reversed(self._records):
            events = self._visible(record, actor)
            if not events:
                continue
            status, reason = self._status(events)
            participants = sorted({id for e in events for id in (e['actor_id'], *e['addressed_ids'])})
            points = []
            for point in record['points']:
                if actor in point['heard_by']:
                    resolutions = [r for r in point['resolutions'] if actor in r['heard_by']]
                    points.append({k: point[k] for k in ('id', 'kind', 'text', 'actor_id', 'event_id')}
                                  | dict(resolved=bool(resolutions)))
            points.reverse()
            points.sort(key=lambda p: p['resolved'])
            proposals = []
            for proposal in record['proposals']:
                versions = []
                for version in proposal['versions']:
                    if actor not in version['heard_by']:
                        continue
                    terms = [{k: t[k] for k in ('id','kind','text','actor_id','order')}
                             for t in version['terms'] if actor in t['heard_by']]
                    responses = [{k: r[k] for k in ('action','actor_id','event_id')}
                                 for r in version['responses'] if actor in r['heard_by']]
                    versions.append(dict(number=version['number'], terms=terms, responses=responses,
                                         terms_complete=len(terms) == len(version['terms'])))
                if versions:
                    reply = proposal['in_reply_to']
                    if reply and not any(p['id'] == reply and any(actor in v['heard_by'] for v in p['versions'])
                                         for p in record['proposals']):
                        reply = None
                    proposals.append(dict(id=proposal['id'], actor_id=proposal['actor_id'],
                                          in_reply_to=reply, versions=versions[-2:]))
            spoken = [e for e in events if e.get('medium') != 'incident']
            frame = dict(id=record['id'], participants=participants, last_speaker=spoken[-1]['actor_id'],
                focus=next((e['focus'] for e in reversed(events) if e['focus'] is not None), None),
                status=status, reason=reason, points=points[:12], proposals=proposals[-3:],
                contributions=[{k: e[k] for k in ('sequence','actor_id','event_id')} for e in spoken[-4:]],
                objective=deepcopy(record['objectives'].get(actor)))
            # Preserva a proposta atual completa; versões antigas continuam no registro.
            while len(json.dumps(frame, ensure_ascii=False)) > max_chars:
                old = next((p for p in frame['proposals'] if len(p['versions']) > 1), None)
                if old:
                    old['versions'].pop(0)
                elif len(frame['proposals']) > 1:
                    frame['proposals'].pop(0)
                elif len(frame['points']) > 1:
                    frame['points'].pop()
                elif frame['contributions']:
                    frame['contributions'].pop(0)
                else:
                    break
            cost = len(json.dumps(frame, ensure_ascii=False))
            if size + cost <= max_chars:
                result.append(frame)
                size += cost
            if len(result) == limit:
                break
        return deepcopy(result)

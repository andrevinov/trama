"""Valida vínculos e limites percebidos; não interpreta a vida interior do jogador."""

from copy import deepcopy
from dataclasses import asdict
import logging

from trama.actions import ActionError
from trama.bonds import BOND_KINDS, ROMANTIC_KINDS, BondEvidence, BondError
from trama.knowledge import Claim, MemorySource
from trama.relationships import RelationshipError

logger = logging.getLogger(__name__)
BOUNDARY_PREFIX = 'romance_boundary:'
DERIVED = {'relationship_episode', 'relationship_bond', 'conversation_commitment', 'conversation_pending'}


class BondSystem:
    def __init__(self, session):
        self.session = session

    def boundary(self, observer, speaker, target):
        memories = [m for m in self.session.knowledge.store.active(observer)
                    if m.claim.subject_id == speaker and m.claim.predicate == BOUNDARY_PREFIX + target
                    and m.claim.value in {'open', 'declined'} and m.source.actor_id == speaker]
        return max(memories, key=lambda m: m.acquired_at).claim.value if memories else 'unknown'

    def availability(self, owner, target):
        eligible = self.session.relationships.romance_eligible(owner, target)
        own = self.boundary(owner, owner, target)
        other = self.boundary(owner, target, owner)
        return dict(eligible=eligible, own_choice=own, known_target_choice=other,
                    can_express=eligible and own != 'declined' and other != 'declined')

    def context(self, owner):
        state = self.session.relationships
        result = state.context(owner)
        if owner != state.player_id and not any(r['target_id'] == state.player_id for r in result):
            row = asdict(state.get(owner, state.player_id))
            row.update(bonds={k: asdict(state.bond(owner, state.player_id, k)) for k in BOND_KINDS},
                       episodes=[], bond_history=[])
            for dimension in ('trust', 'affection'):
                row[dimension]['source_count'] = 0
            result.append(row)
        for row in result:
            row['romance'] = self.availability(owner, row['target_id'])
        return result

    def validate_declaration(self, actor, update):
        if update is None or not (update.romance_boundary or update.romantic_expression):
            return
        if len(update.target_ids) != 1 or actor in update.target_ids:
            raise ActionError('Declaração afetiva exige um destinatário distinto e explícito.')
        target = update.target_ids[0]
        state = self.session.relationships
        if (actor not in state._actors or target not in state._actors):
            raise ActionError('Destinatário afetivo não existe na cena.')
        if update.romance_boundary == 'open' or update.romantic_expression:
            if not state.romance_eligible(actor, target):
                raise ActionError('Romance exige ambos participantes adultos declarados no cenário.')
        if update.romantic_expression:
            status = self.availability(actor, target)
            if status['known_target_choice'] == 'declined' or (
                    status['own_choice'] == 'declined' and update.romance_boundary != 'open'):
                raise ActionError('A expressão amorosa não pode ignorar um limite conhecido.')
            if actor != state.player_id and not any(state.bond(actor, target, k).state == 'active' for k in ROMANTIC_KINDS):
                raise ActionError('O NPC precisa de sentimento próprio validado antes de expressá-lo.')

    def record_declaration(self, actor, update, hearers, event_id):
        if update is None or update.romance_boundary is None:
            return ()
        target = update.target_ids[0]
        learned = []
        for owner in dict.fromkeys((actor, *hearers)):
            if self.boundary(owner, actor, target) == update.romance_boundary:
                continue  # A fala continua no registro; disponibilidade igual não é informação nova.
            learned.append(self.session.knowledge._learn(owner, Claim(actor, BOUNDARY_PREFIX + target, update.romance_boundary),
                update.boundary_text, MemorySource('observation' if owner == actor else 'report', event_id, actor),
                when='Limite declarado em fala efetivamente executada.',
                context='Declaração própria sobre disponibilidade; não comprova sentimentos ou reciprocidade.',
                entities=(actor, target), topics=('relationships', 'boundaries'), replace_existing=True))
        return tuple(learned)

    def _care(self, owner, target, memory):
        if memory.source.kind != 'observation':
            return False
        if {'care', 'costly_help'} & set(memory.topics):
            return True
        return any(e['evidence_id'] == memory.id and e['kind'] in {'care_shown', 'costly_help'}
                   for e in self.session.relationships.history(owner, target))

    def apply(self, updates):
        s = self.session
        if updates and s.encounter.combat:
            raise ActionError('Vínculos só são interpretados no modo narrado, após os acontecimentos.')
        candidate = deepcopy(s.relationships)
        prepared = []
        for update in updates:
            try:
                observer = s.perception.observer(update.owner_id)
                if s.perception.sleeping(observer):
                    raise BondError('NPC dormindo não interpreta vínculos.')
                before = candidate.bond(update.owner_id, update.target_id, update.kind)
                if update.kind in ROMANTIC_KINDS and not candidate.romance_eligible(update.owner_id, update.target_id):
                    raise BondError('Vínculo amoroso exige ambos adultos declarados.')
                active = {m.id: m for m in s.knowledge.store.active(update.owner_id)}
                memories = []
                linked = [m for m in active.values() if (m.source.actor_id == update.target_id
                    or m.claim.subject_id == update.target_id or update.target_id in m.entities)
                    and m.claim.predicate not in DERIVED]
                for id in update.evidence_ids:
                    if id in {'latest_observation', 'latest_report'}:
                        kinds = {'observation'} if id == 'latest_observation' else {'report', 'inference'}
                        memories.append(max((m for m in linked if m.source.kind in kinds),
                            key=lambda m: m.acquired_at, default=None))
                    else:
                        memories.append(active.get(id))
                if any(m is None or m.claim.predicate in DERIVED or not (
                        m.source.actor_id == update.target_id or m.claim.subject_id == update.target_id
                        or update.target_id in m.entities) for m in memories):
                    raise BondError('Vínculo exige evidência própria ativa e ligada ao destinatário, sem resumos derivados.')
                sources = tuple(BondEvidence.from_memory(m) for m in memories)
                if candidate.bond_reused(update, sources):
                    continue
                fresh = [m for m in memories if m.acquired_at > before.revision]
                if update.state == 'ended':
                    if before.state != 'active' or not fresh:
                        raise BondError('Ruptura exige vínculo ativo e acontecimento posterior, sem apagar história.')
                elif before.state == 'active':
                    if not fresh:
                        raise BondError('Manutenção não reaplica história antiga como novo episódio.')
                else:
                    if before.state == 'ended' and not fresh:
                        raise BondError('Reaproximação exige acontecimento novo após a ruptura.')
                    self._validate_formation(candidate, update, memories)
                prepared.append(candidate.record_bond(update, sources, s.knowledge.store.revision))
            except (BondError, RelationshipError) as error:
                raise ActionError(str(error)) from error
        s.relationships = candidate
        for entry in prepared:
            logger.info('relationship.bond_updated', extra={'data': entry})
            after = entry['after']
            s.knowledge._learn(entry['owner_id'],
                Claim(f"bond:{entry['target_id']}:{entry['kind']}", 'relationship_bond', after['state']),
                f"{entry['kind']}: {entry['reason']}"[:700], MemorySource('inference', entry['id'], entry['owner_id']),
                when='Interpretação privada com fontes e antes/depois no histórico.',
                context='Perspectiva do NPC; não atribui sentimento ou escolha ao destinatário.',
                entities=(entry['target_id'],), topics=('relationships', 'bonds'), shareable=False, replace_existing=True)
        return [e['id'] for e in prepared]

    def _validate_formation(self, state, update, memories):
        owner, target = update.owner_id, update.target_id
        care = [m for m in memories if self._care(owner, target, m)]
        reciprocal = ({m.source.actor_id for m in care} >= {owner, target}
                      and len({m.source.event_id for m in care}) >= 2)
        observed = [m for m in memories if m.source.kind == 'observation' and m.source.actor_id == target]
        if update.kind == 'friendship' and not reciprocal:
            raise BondError('Amizade exige história de cuidado observado nas duas direções, em episódios distintos.')
        if update.kind == 'attraction' and not observed:
            raise BondError('Atração é interpretação própria apoiada em encontro observado com o destinatário.')
        if update.kind == 'infatuation':
            attraction = state.bond(owner, target, 'attraction')
            personal = [m for m in observed if self._care(owner, target, m) or 'personal_encounter' in m.topics]
            events = {e.source.event_id for e in attraction.sources} | {m.source.event_id for m in personal}
            if (attraction.state != 'active' or len(events) < 2
                    or not any(m.acquired_at > attraction.revision for m in personal)):
                raise BondError('Paixão exige atração própria e novo encontro significativo observado, sem progressão pela mesma fonte.')
        if update.kind == 'love':
            passion = state.bond(owner, target, 'infatuation')
            if (state.bond(owner, target, 'friendship').state != 'active' or passion.state != 'active'
                    or not reciprocal or not any(m.source.actor_id == target and m.acquired_at > passion.revision for m in care)):
                raise BondError('Amor exige história de amizade/cuidado recíproco e novo cuidado após a paixão, com decisão própria.')

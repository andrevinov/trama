"""Episódios percebidos: valida evidência própria antes de evoluir relações."""

from copy import deepcopy
from dataclasses import asdict
import logging

from trama.actions import ActionError
from trama.knowledge import Claim, MemorySource
from trama.relationships import RelationshipEvidence, RelationshipError

logger = logging.getLogger(__name__)
SUMMARY_PREDICATES = {'conversation_pending', 'conversation_commitment', 'relationship_episode', 'relationship_bond'}


class RelationshipHistory:
    def __init__(self, session):
        self.session = session
        self._seen = set()

    def apply(self, updates):
        s = self.session
        candidate, seen, prepared = deepcopy(s.relationships), set(self._seen), []
        for update in updates:
            if update.owner_id not in s.social.profiles:
                raise ActionError('O episódio exige um NPC existente como dono.')
            try:
                candidate.get(update.owner_id, update.target_id)
            except RelationshipError as error:
                raise ActionError(str(error)) from error
            memories = s.knowledge.store.active(update.owner_id)
            matches = [m for m in memories if m.claim.predicate not in SUMMARY_PREDICATES and (
                m.source.actor_id == update.target_id or m.claim.subject_id == update.target_id
                or update.target_id in m.entities or update.kind == 'correction')]
            if update.evidence_id in {'latest_observation', 'latest_report'}:
                kinds = {'observation'} if update.evidence_id == 'latest_observation' else {'report', 'inference'}
                memory = max((m for m in matches if m.source.kind in kinds), key=lambda m: m.acquired_at, default=None)
            else:
                memory = next((m for m in matches if m.id == update.evidence_id), None)
            if memory is None:
                raise ActionError('Evidência não percebida, não ativa ou sem vínculo com o destinatário.')
            if update.kind == 'suspicion':
                if memory.source.kind not in {'report', 'inference'}:
                    raise ActionError('Suspeita usa relato/inferência; não declare um acontecimento comprovado.')
            elif memory.source.kind != 'observation':
                raise ActionError('Esse episódio exige observação própria; relato não comprova cumprimento ou traição.')
            if update.kind not in {'suspicion', 'correction'} and memory.source.actor_id != update.target_id:
                raise ActionError('A evidência precisa identificar o autor efetivamente observado.')
            if update.kind == 'costly_help' and 'costly_help' not in memory.topics:
                raise ActionError('Ajuda com custo exige custo explícito em evidência observada do cenário.')
            commitment = None
            if update.proposal_id or update.kind == 'promise_kept':
                try:
                    commitment = s.conversations.commitment(update.owner_id, update.conversation_id,
                        update.proposal_id, update.version, update.term_id or '')
                except ValueError as error:
                    raise ActionError(str(error)) from error
                if (commitment['actor_id'] != update.target_id
                        or memory.acquired_at <= commitment['memory_revision']):
                    raise ActionError('Cumprimento exige ação do responsável observada depois do compromisso.')
            if update.kind == 'betrayal_discovered' and not commitment and not {'betrayal', 'harm'} & set(memory.topics):
                raise ActionError('Traição exige quebra de compromisso ou dano/traição explicitamente observado.')
            interests = {i.id: i for i in s.social.profiles[update.owner_id].persona.interests}
            if any(id not in interests or not interests[id].relevant(memory) for id in update.interest_ids):
                raise ActionError('O aspecto resumido exige interesse e âncoras pertinentes à evidência.')
            sources = tuple(RelationshipEvidence(memory.id, memory.claim, id, memory.source)
                            for id in (update.interest_ids or (None,)))
            key = (update.owner_id, update.target_id, memory.claim, memory.source.kind, memory.source.event_id)
            if key in seen:
                continue
            try:
                entry = candidate.record_episode(update.owner_id, update, memory, sources, commitment)
            except RelationshipError as error:
                raise ActionError(str(error)) from error
            seen.add(key)
            if not entry['reused']:
                prepared.append((entry, memory))
        # O lote inteiro foi validado; nenhum episódio rejeitado altera níveis.
        s.relationships, self._seen = candidate, seen
        for entry, memory in prepared:
            logger.info('relationship.episode_applied', extra={'data': {
                **entry, 'sources': [asdict(source) for source in entry['sources']]}})
            s.knowledge._learn(entry['owner_id'], Claim(entry['episode_id'], 'relationship_episode', entry['kind']),
                f"{entry['kind']}: {entry['reason']} Evidência própria: {memory.id}."[:700],
                MemorySource('inference', memory.source.event_id, entry['owner_id'], memory.id),
                when='Interpretação de um episódio percebido durante a partida.',
                context='Avaliação privada com história preservada; relato/suspeita não comprova a verdade global.',
                entities=(entry['target_id'], entry['episode_id']), topics=('relationships', 'episodes'), shareable=False,
                replace_existing=True)
        return [entry['id'] for entry, _ in prepared]

"""Aquisição por sentidos e comunicação; seleção de memórias para a IA."""

import json
import logging

from trama.actions import ActionError
from trama.knowledge import Claim, KnowledgeError, KnowledgeStore, MemorySource
from trama.observability import current_context, new_id
from trama.perception import Noise, Observer, Senses

logger = logging.getLogger(__name__)


class KnowledgeSystem:
    def __init__(self, session, memories=()):
        self.session = session
        self.store = KnowledgeStore(memories)
        owners = {session.encounter.player_id, *(c.id for c in session.creatures), *(o.id for o in session.observers)}
        if any(m.owner_id not in owners for m in memories):
            raise KnowledgeError('Memória inicial pertence a personagem inexistente.')

    def _learn(self, owner, claim, text, source, **context):
        previous = self.store.revision
        memory = self.store.learn(owner, claim, text, source, **context)
        if self.store.revision != previous:
            logger.debug('knowledge.acquired', extra={'data': memory.data()})
            self.session.on_knowledge(memory)
        return memory

    def observe(self, claim, text, position, *, context, entities=(), topics=(), excluded=()):
        """A posição observável é do acontecimento, não a localização onisciente do alvo."""
        source = MemorySource('observation', current_context().get('operation_id') or new_id())
        owners = [o.id for o in self.session.perception.observers()
                  if o.id not in excluded and self.session.perception.sees(o, position)]
        if position in self.session.visibility.visible:
            owners.append(self.session.encounter.player_id)
        return tuple(self._learn(owner, claim, text, source, when='Observado durante a partida.', context=context,
                                 entities=entities, topics=topics) for owner in owners)

    def observe_scene(self):
        for fact in self.session.observable_facts():
            self.observe(**fact)

    def references(self, actor_id, ids):
        try:
            memories = tuple(self.store.get(actor_id, id) for id in ids)
        except KnowledgeError as error:
            raise ActionError(str(error)) from error
        if any(not m.shareable for m in memories):
            raise ActionError('Essa memória não está autorizada para divulgação.')
        return memories

    def communicate(self, actor_id, text, position, volume='normal', *, memory_ids=(), claims=()):
        # Validação vem antes do ruído e de qualquer efeito de comunicação.
        memories = self.references(actor_id, memory_ids)
        if claims and actor_id != self.session.encounter.player_id:
            raise ActionError('NPCs compartilham memórias próprias; não criam fatos por fala.')
        noise = Noise(actor_id, position, volume, 'Fala com informação.', speech=True)
        # Uma pessoa adormecida pode despertar, mas não recebe o conteúdo da
        # frase que a acordou. Capturamos ouvintes conscientes antes do estímulo.
        hearers = [o.id for o in self.session.perception.observers()
                   if not self.session.perception.sleeping(o) and self.session.perception.hears(o, noise)]
        player = self.session.encounter.player_id
        if actor_id != player:
            # Usa o mesmo alcance/atenuação do sentido humano padrão do jogador.
            listener = Observer(player, 'Jogador', self.session.state.position,
                                Senses(perception_bonus=self.session.encounter.player_sheet.skill_bonus('perception')))
            if self.session.perception.hears(listener, noise):
                hearers.append(player)
        event_id = new_id()
        learned = []
        for recipient in hearers:
            for memory in memories:
                source = MemorySource('report', event_id, actor_id, memory.id)
                learned.append(self._learn(recipient, memory.claim, memory.text, source,
                    when=memory.when,
                    context=f'{actor_id} disse: {text}'[:500],
                    entities=memory.entities, topics=memory.topics))
            for claim in claims:
                learned.append(self._learn(recipient, claim, text[:700], MemorySource('report', event_id, actor_id),
                    when='Relato ouvido durante a partida.', context='Afirmação do jogador; veracidade não confirmada.'))
        return {'memory_ids': list(memory_ids), 'claims': [vars(c) for c in claims],
                'shared_memories': [{k: v for k, v in m.data().items()
                                    if k in {'id', 'owner_id', 'claim', 'text', 'source', 'when'}} for m in memories],
                'heard_by': hearers, 'learned_memory_ids': [m.id for m in learned]}

    def context(self, query=''):
        s = self.session
        area = s.scene.area_at(s.state.position) if s.scene else None
        entities = (area.id,) if area else ()
        player = [m.data() for m in self.store.select(s.encounter.player_id, query=query, entities=entities)]
        combat = s.encounter.combat
        observers = [o for o in s.perception.observers() if o.position in s.visibility.visible
                     or s.perception.hears(o, Noise(s.encounter.player_id, s.state.position))
                     or combat is not None and combat.active_id == o.id]
        observers.sort(key=lambda o: (not (combat is not None and combat.active_id == o.id),
                                     max(abs(o.position.x - s.state.position.x), abs(o.position.y - s.state.position.y)), o.id))
        actors, remaining = [], 9000
        for observer in observers[:8]:
            place = s.scene.area_at(observer.position) if s.scene else None
            anchors = (*entities, *((place.id,) if place else ()))
            memories = self.store.select(observer.id, query=query, entities=anchors, max_chars=min(3500, remaining))
            payload = [m.data() for m in memories]
            remaining -= sum(len(json.dumps(m, ensure_ascii=False)) for m in payload)
            actors.append({'actor_id': observer.id, 'memories': payload})
        return player, {'actors': actors, 'limit_per_actor': 6, 'max_content_chars': 9000}

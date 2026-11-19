"""Avalia sentidos por NPC e mudanças observáveis; sem roteiro de dungeon ou IA."""

from dataclasses import replace
from copy import deepcopy
from decimal import Decimal
import logging

from trama.actions import ActionError
from trama.application.routing import path_to_cells
from trama.dice import roll_d20
from trama.distances import CELL_METERS
from trama.movement import MovementError
from trama.perception import CONVERSATION_HEARING_MULTIPLIER, Noise, Observer, Senses
from trama.spatial import Position
from trama.vision import line_of_sight
from trama.observability import new_id

logger = logging.getLogger(__name__)


class PerceptionRangeError(ActionError):
    """Nenhum sentido disponível alcança o alvo da busca."""


def distance(a, b):
    return CELL_METERS * max(abs(a.x - b.x), abs(a.y - b.y))


class PerceptionSystem:
    def __init__(self, session):
        self.session = session
        self.hidden_total = None
        self.awareness = {}
        self.awakened = set()
        self.searches = set()
        self.last_search = {}
        self.revision = 0
        self._observation_key = (session.state.position, session.scene,
                                 tuple((o.id, o.position) for o in self.observers()))
        self._sound_cache = {}
        self._sound_barriers = {}
        self._scene_key = None

    def observers(self):
        s = self.session
        return (*[c for c in s.creatures if s.encounter.states[c.id].hp > 0], *s.observers)

    def observer(self, actor_id):
        observer = next((o for o in self.observers() if o.id == actor_id), None)
        if observer is None:
            raise ActionError('Não há NPC consciente e existente com esses sentidos.')
        return observer

    def bonus(self, observer):
        if observer.senses.perception_bonus is not None:
            return observer.senses.perception_bonus
        return self.session.encounter.sheets[observer.id].skill_bonus('perception')

    def sleeping(self, observer):
        return observer.senses.sleeping and observer.id not in self.awakened

    def sees(self, observer, target):
        senses, s = observer.senses, self.session
        if self.sleeping(observer) or not senses.can_see:
            return False
        d = distance(observer.position, target)
        if senses.sight_range_meters is not None and d > senses.sight_range_meters:
            return False
        dark = s.scene.dark if s.scene else frozenset()
        if senses.darkvision_meters:
            dark = frozenset(p for p in dark if distance(observer.position, p) > senses.darkvision_meters)
        opaque = s.scene.opaque if s.scene else s.grid.blocked
        return target not in dark and line_of_sight(observer.position, target, opaque | dark)

    def sound_distance(self, origin, target):
        s = self.session
        key = (s.scene, s.grid)
        if key != self._scene_key:
            self._sound_cache.clear()
            self._sound_barriers.clear()
            self._scene_key = key
        pair = (origin, target)
        if pair not in self._sound_cache:
            if s.scene:
                passages = frozenset(p.position for p in s.scene.passages)
                grid = replace(s.scene.grid, blocked=s.scene.grid.blocked - passages, difficult=frozenset())
            else:
                grid = replace(s.grid, difficult=frozenset())
            # Objetos não fecham o ar de uma casa; paredes continuam sólidas.
            try:
                path = path_to_cells(grid, origin, frozenset({target}))
                doors = {p.position for p in s.scene.passages if p.kind == 'door' and not p.is_open} if s.scene else set()
                self._sound_cache[pair] = len(path) * CELL_METERS + sum(Decimal('6') for p in path if p in doors)
                self._sound_barriers[pair] = tuple(sorted(p.id for p in s.scene.passages
                    if p.position in path and p.position in doors)) if s.scene else ()
            except MovementError:
                self._sound_cache[pair] = None
                self._sound_barriers[pair] = ()
        return self._sound_cache[pair]

    def sound_barriers(self, origin, target):
        self.sound_distance(origin, target)
        return self._sound_barriers[(origin, target)]

    def hears(self, observer, noise, *, waking=False, adjudicate=True):
        senses = observer.senses
        if not senses.can_hear or observer.id == noise.actor_id:
            return False
        reach = (senses.wake_range_meters if waking else senses.hearing_range_meters) * noise.multiplier
        if (not waking and noise.speech and noise.volume == 'normal'
                and self._mutual_sight(observer, noise)):
            reach *= CONVERSATION_HEARING_MULTIPLIER
        if distance(observer.position, noise.position) > reach:
            return False
        actual = self.sound_distance(noise.position, observer.position)
        if actual is None or actual > reach:
            return False
        if waking or not adjudicate:
            return True
        decision = self.session.adjudication.hearing(observer, noise, self.sound_barriers(noise.position, observer.position))
        hidden_dc = self.hidden_total if noise.actor_id == self.session.encounter.player_id else None
        if decision is None:
            return hidden_dc is None or senses.passive(self.bonus(observer)) >= hidden_dc
        total = dc = None
        heard = decision.outcome == 'automatic'
        if decision.outcome == 'check' or (hidden_dc is not None and decision.outcome != 'impossible'):
            dc = hidden_dc if hidden_dc is not None else decision.dc
            senses = observer.senses
            advantage = senses.advantage or decision.advantage
            disadvantage = senses.disadvantage or decision.disadvantage
            total = 10 + self.bonus(observer) + (5 if advantage and not disadvantage else -5 if disadvantage and not advantage else 0)
            heard = total >= dc
        self.session.adjudication.record_hearing(observer, noise, decision, total, dc, heard)
        return heard

    def _mutual_sight(self, listener, noise):
        """Contato visual atual; lembrança de um interlocutor não amplia audição."""
        s = self.session
        if noise.actor_id == s.encounter.player_id:
            speaker = Observer(noise.actor_id, 'Jogador', s.state.position, Senses(perception_bonus=0))
        else:
            speaker = next((o for o in self.observers() if o.id == noise.actor_id), None)
        return (speaker is not None and speaker.position == noise.position
                and self.sees(listener, speaker.position) and self.sees(speaker, listener.position))

    def _record(self, observer, target_id, level, sense, position, reason):
        previous = self.awareness.get(observer.id, {}).get(target_id)
        if previous and {'heard': 1, 'located': 2, 'seen': 3}[previous['level']] > {'heard': 1, 'located': 2, 'seen': 3}[level]:
            return None  # Ouvir de novo não apaga uma localização já conhecida.
        record = dict(level=level, sense=sense,
                      position=([position.x + 1, position.y + 1] if level in {'seen', 'located'} else None),
                      visible=level == 'seen')
        self.awareness.setdefault(observer.id, {})[target_id] = record
        if previous and previous['level'] == level and (level != 'seen' or previous['visible']):
            return None
        return dict(operation='perception_detected', actor_id=observer.id, target_id=target_id,
                    **record, changed=True, perceptible=False, reason=reason)

    def evaluate(self, noise=None):
        s, events = self.session, []
        incident_id = new_id() if noise is not None and not noise.speech and noise.volume == 'loud' else None
        if noise is not None and noise.speech:
            # Notar a voz não implica compreender as palavras. A comunicação
            # avalia o conteúdo separadamente, antes de publicar este estímulo.
            noise = replace(noise, speech=False)
        player = s.encounter.player_id
        initial_hidden = self.hidden_total
        observers = self.observers()
        key = (s.state.position, s.scene, tuple((o.id, o.position) for o in observers))
        if key != self._observation_key or (noise is not None and noise.actor_id == player):
            self.revision += 1
            self._observation_key = key
        for observer in observers:
            if self.sleeping(observer):
                if noise is None or not self.hears(observer, noise, waking=True):
                    continue
                self.awakened.add(observer.id)
                events.append(dict(operation='awakened', actor_id=observer.id, target_id=noise.actor_id,
                                   changed=True, perceptible=False, reason=noise.reason))
            visible = self.sees(observer, s.state.position)
            old = self.awareness.get(observer.id, {}).get(player)
            if old:
                old['visible'] = visible and old['visible']
            if visible:
                # Sair da cobertura para exposição evidente não é invisibilidade mágica.
                if getattr(observer, 'hostile', False):
                    self.hidden_total = None
                event = self._record(observer, player, 'seen', 'sight', s.state.position, 'Contato visual livre.')
                if event:
                    events.append(event)
            if noise is not None and self.hears(observer, noise):
                if incident_id is not None and hasattr(s, 'agency'):
                    source = (s.state.position if noise.actor_id == player else
                              next((o.position for o in observers if o.id == noise.actor_id), None))
                    located = (source == noise.position and self.sees(observer, source)
                               and (noise.actor_id != player or self.hidden_total is None))
                    s.agency.notice_noise(observer.id, incident_id,
                        noise.position if located else None)
                if noise.actor_id == player and visible:
                    continue
                hidden = initial_hidden if noise.actor_id == player else None
                level = 'located' if hidden is not None else 'heard'
                if hidden is not None and getattr(observer, 'hostile', False):
                    self.hidden_total = None
                event = self._record(observer, noise.actor_id, level, 'hearing', noise.position, noise.reason)
                if event:
                    events.append(event)
        return tuple(events)

    def can_hide(self):
        s = self.session
        enemies = [o for o in self.observers() if getattr(o, 'hostile', False)]
        if any(self.sees(o, s.state.position) for o in enemies):
            return False
        opaque = s.scene.opaque if s.scene else s.grid.blocked
        dark = s.scene.dark if s.scene else frozenset()
        return (s.state.position in dark or any(distance(s.state.position, p) <= CELL_METERS for p in opaque)
                or any(not line_of_sight(o.position, s.state.position, opaque) for o in enemies))

    def search(self, actor_id):
        s = self.session
        observer = self.observer(actor_id)
        if self.sleeping(observer):
            raise ActionError('Um NPC dormindo não pode realizar uma busca consciente.')
        if actor_id in s.encounter.sheets:
            s.encounter.require_turn(actor_id)
        elif s.encounter.combat:
            raise ActionError('Esse NPC não participa dos turnos de combate.')
        signature = (actor_id, observer.position, s.state.position, s.scene, self.hidden_total, self.revision,
                     s.encounter.combat.round if s.encounter.combat else None)
        if signature in self.searches:
            raise ActionError('A mesma busca já foi resolvida; é necessária uma mudança relevante ou novo turno.')
        visible = self.sees(observer, s.state.position)
        audible = self.hears(observer, Noise(s.encounter.player_id, s.state.position,
                            'quiet' if self.hidden_total is not None else 'normal', 'Presença do jogador.'), adjudicate=False)
        hearing = s.adjudication.hearing(observer, Noise(s.encounter.player_id, s.state.position,
            'quiet' if self.hidden_total is not None else 'normal'), self.sound_barriers(s.state.position, observer.position)) if audible else None
        if hearing and hearing.outcome == 'impossible':
            audible = False
        if not visible and not audible:
            raise PerceptionRangeError('A busca não alcança o jogador por nenhum sentido disponível.')
        dc = self.hidden_total
        if dc is None:
            return dict(operation='search', actor_id=actor_id, changed=False, perceptible=False,
                        found=visible or audible, automatic=True, reason='Não há ocultação que exija teste.')
        if s.encounter.combat:
            budget = s.encounter.budgets[actor_id].spend_action()
        else:
            budget = None
        dim = s.scene.dim if s.scene else frozenset()
        impaired = visible and not audible and s.state.position in dim
        roll = roll_d20(s.encounter.roller, self.bonus(observer),
            advantage=observer.senses.advantage or bool(not visible and hearing and hearing.advantage),
            disadvantage=observer.senses.disadvantage or impaired or bool(not visible and hearing and hearing.disadvantage))
        self.searches.add(signature)
        if budget is not None:
            s.encounter.budgets[actor_id] = budget
        found = roll.total >= dc
        if found:
            self.hidden_total = None
            event = self._record(observer, s.encounter.player_id, 'seen' if visible else 'located',
                                 'sight' if visible else 'hearing', s.state.position, 'Busca ativa encontrou o jogador.')
            if event:
                s._events.append(event)
                s.on_perception(event)
        event = dict(operation='search', actor_id=actor_id, changed=found, perceptible=False,
                     dice=list(roll.dice), total=roll.total, dc=dc, found=found, automatic=False,
                     advantage=roll.advantage, disadvantage=roll.disadvantage)
        self.last_search[actor_id] = {**event, 'revision': self.revision, 'player_position': [s.state.position.x + 1, s.state.position.y + 1]}
        logger.info('perception.search_resolved', extra={'data': event})
        return event

    def context(self):
        return dict(hidden=self.hidden_total is not None, revision=self.revision, stealth_total=self.hidden_total, last_search=deepcopy(self.last_search),
                    observers=[dict(id=o.id, name=o.name, column=o.position.x + 1, row=o.position.y + 1,
                                    sleeping=self.sleeping(o), senses={**o.senses.context(self.bonus(o)), 'sleeping': self.sleeping(o)},
                                    awareness=deepcopy(self.awareness.get(o.id, {}))) for o in self.observers()])

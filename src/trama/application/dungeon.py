"""Adjudicação do cenário de fuga, sem SDK ou interface.

As CDs, a rotina do guarda e as consequências sociais são decisões de mestre
registradas em docs/sistema/simulador/fuga-da-dungeon.md; não são novas regras universais.
"""

from copy import deepcopy
from dataclasses import dataclass, field, replace
from decimal import Decimal
import logging

from trama.actions import ActionError
from trama.application.encounter import RuleResult
from trama.application.intents import (
    DIRECTIONS, DoorIntent, MovementIntent, NarrativeIntent, RuleIntent,
    ScenarioIntent, SCENARIO_OPERATIONS,
)
from trama.application.modes import GameMode
from trama.application.routing import path_to_cells
from trama.application.session import GameSession
from trama.application.preparation import SpatialRequirement
from trama.application.travel import TravelResult, TravelExecutor
from trama.characters import ability_check, sheet_from_data
from trama.creatures import creatures_from_data
from trama.movement import MovementError, MovementResult, MovementState, MovementRequest
from trama.scene import Scene
from trama.spatial import Position
from trama.vision import line_of_sight
from trama.perception import Noise, Observer, Senses, observers_from_data

logger = logging.getLogger(__name__)


def distance(a: Position, b: Position) -> int:
    return max(abs(a.x - b.x), abs(a.y - b.y))


def coordinate(p: Position) -> list[int]:
    return [p.x + 1, p.y + 1]


@dataclass
class DungeonState:
    inventory: set[str] = field(default_factory=set)
    discovered: set[str] = field(default_factory=set)
    clothing: str = 'rags'
    sword_concealed: bool = False
    disguise: str = 'untested'
    prisoner_awake: bool = False
    prisoner_free: bool = False
    guard_alert: bool = False
    guard_activity: str = 'on_duty'
    bathroom_remaining: int = 0
    waits: int = 0
    illusion_used: bool = False
    distraction_remaining: int = 0
    escaped: bool = False
    companion_escaped: bool = False


class DungeonSession(GameSession):
    """Pequeno cenário sobre as APIs existentes de movimento e combate.

    O prisioneiro é um NPC de cenário, fora do elenco de Guerreiros do combate.
    Nenhuma ficha fictícia de Guerreiro é atribuída ao mago.
    """

    title = 'Simulador / Fuga da dungeon'

    @classmethod
    def from_data(cls, data: dict, *, roller=None):
        scene = Scene.from_data(data)
        player = sheet_from_data(data['player'], id='player', name='Jogador', default_level=3)
        creatures = creatures_from_data(data['creatures'])
        session = cls(scene.movement_grid, MovementState(Position(*data['start']), player.speed_meters), scene,
                      creatures, player_sheet=player,
                      enemy_sheets=tuple(sheet_from_data(c['sheet'], id=c['id'], name=c['name'])
                                         for c in data['creatures']), roller=roller,
                      observers=observers_from_data(data.get('observers', [])) or (Observer(
                          'prisoner', 'Prisioneiro', Position(*data['dungeon']['prisoner_position']),
                          Senses(perception_bonus=0, sleeping=True)),))
        session.definition = deepcopy(data['dungeon'])
        session.items = {i['id']: deepcopy(i) for i in session.definition['items']}
        session.title = data.get('title', cls.title)
        session._initialize_dungeon()
        return session

    def _initialize_dungeon(self):
        prisoner = self.perception.observer('prisoner')
        self.dungeon = DungeonState(prisoner_awake=not self.perception.sleeping(prisoner))
        self.prisoner_position = prisoner.position
        self.item_positions = {id: Position(*item['position']) for id, item in self.items.items()}
        self._events = []
        self._examined_locks = set()
        self._sword_checked = False
        player = self.encounter.player_id
        self.encounter.states[player] = replace(self.encounter.states[player], javelins_remaining=0)

    def reset(self):
        super().reset()
        self._initialize_dungeon()

    def _event(self, operation, text, *, actor_id='world', perceptible=True, **data):
        event = dict(operation=operation, actor_id=actor_id, text=text, changed=True,
                     perceptible=perceptible, **data)
        self._events.append(event)
        logger.info('dungeon.' + operation, extra={'data': event})

    def _passage(self, id):
        passage = next((p for p in self.scene.passages if p.id == id), None)
        if passage is None:
            raise ActionError('Passagem desconhecida.')
        return passage

    def _near(self, position):
        return (distance(self.state.position, position) <= 1
                and line_of_sight(self.state.position, position, self.scene.opaque))

    def _area(self):
        area = self.scene.area_at(self.state.position)
        return area.id if area else None

    @property
    def guard(self):
        return next(c for c in self.creatures if c.id == 'guard_1')

    def _guard_available(self):
        return self.encounter.states['guard_1'].hp > 0

    def _guard_sees_player(self):
        return self._guard_available() and self.npc_sees_player('guard_1')

    def _check(self, actor, skill, dc):
        state, roll, total = ability_check(self.encounter.sheets[actor], self.encounter.states[actor],
                                          skill, dc, self.encounter.roller)
        self.encounter.states[actor] = state
        self._event('check', f'{skill}: {total} contra CD {dc}.', actor_id=actor,
                    perceptible=actor == 'player',
                    skill=skill, dice=list(roll.dice), total=total, dc=dc, passed=total >= dc)
        return total >= dc, total

    def _pay_action(self):
        if self.mode == GameMode.TURN_BASED:
            self.budget = self.budget.spend_action()

    def _pay_interaction(self):
        if self.mode == GameMode.TURN_BASED:
            self.budget = self.budget.spend_interaction()

    def spatial_requirement(self, intent):
        if not isinstance(intent, ScenarioIntent):
            return super().spatial_requirement(intent)
        target, operation = intent.target_id, intent.operation
        if operation == 'investigate':
            area = next((a for a in self.scene.areas if a.id == target), None)
            if area and self.state.position not in area.cells:
                return SpatialRequirement('inside_area', area.id, area.cells)
        elif operation == 'take' and target in self.items and target not in self.dungeon.inventory:
            return self.reach_requirement(target, self.item_positions[target], include_target=True)
        elif operation in {'listen', 'unlock'}:
            passage = next((p for p in self.scene.passages if p.id == target), None)
            if passage and (operation != 'unlock' or passage.locked):
                return self.reach_requirement(passage.id, passage.position, include_target=True)
        elif operation == 'wake' and target == 'prisoner' and not self.dungeon.prisoner_awake:
            position = self.prisoner_position if self.dungeon.prisoner_free else self._passage('gate_2').position
            return self.reach_requirement(target, position)
        return None

    def validate_preparation(self, intent):
        super().validate_preparation(intent)
        if not isinstance(intent, ScenarioIntent):
            return
        self.encounter.require_turn(self.encounter.player_id)
        operation, target = intent.operation, intent.target_id
        if operation == 'investigate' and not any(a.id == target for a in self.scene.areas):
            raise ActionError('Cômodo desconhecido.')
        if operation == 'take':
            if target not in self.items or target not in self.known_objects():
                raise ActionError('Encontre o objeto antes de pegá-lo.')
            if target in self.dungeon.inventory:
                raise ActionError('Você já carrega esse objeto.')
        if operation in {'listen', 'unlock'}:
            passage = self._passage(target)
            if operation == 'unlock':
                if not passage.locked:
                    return
                if 'cell_key' not in self.dungeon.inventory or target not in {'gate_2', 'gate_3'}:
                    raise ActionError('Você precisa da chave das celas para essa fechadura.')
        if operation == 'wake':
            if target != 'prisoner':
                raise ActionError('Escolha o prisioneiro para acordar.')
            if self.dungeon.prisoner_awake:
                return
        if self.mode == GameMode.TURN_BASED:
            if operation in {'investigate', 'listen', 'wake'} and not self.budget.action_available:
                raise ActionError('A ação deste turno já foi utilizada.')
            if operation in {'take', 'unlock'} and self.budget.free_interaction_used and not self.budget.action_available:
                raise ActionError('A ação deste turno já foi utilizada.')

    def _movement_grid(self):
        # Um guarda incapacitado pode ser atravessado como terreno difícil
        # (PHB 2024, Moving around Other Creatures), mas não é destino livre.
        bodies = frozenset(c.position for c in self.creatures if self.encounter.states[c.id].hp == 0)
        conscious = frozenset(c.position for c in self.creatures if self.encounter.states[c.id].hp > 0)
        grid = replace(self.grid, blocked=self.grid.blocked | conscious | frozenset(o.position for o in self.observers if o.id != 'prisoner'),
                       difficult=self.grid.difficult | bodies)
        if not self.dungeon.prisoner_free:
            grid = replace(grid, blocked=grid.blocked | {self.prisoner_position})
        return grid

    def movement_path(self, intent):
        target = intent.target_id
        position = None
        if target == 'prisoner' and self.prisoner_position in self.visibility.visible:
            if not self.dungeon.prisoner_free:
                goals = self.scene.destination_cells('gate_2')
                return path_to_cells(self._movement_grid(), self.state.position, goals), Decimal('0')
            position = self.prisoner_position
        elif target in self.known_objects():
            position = self.item_positions[target]
        if position is not None:
            goals = frozenset(Position(position.x + dx, position.y + dy)
                              for dx, dy in (*DIRECTIONS.values(), (0, 0))
                              if line_of_sight(Position(position.x + dx, position.y + dy), position,
                                               self.scene.opaque))
            return path_to_cells(self._movement_grid(), self.state.position, goals), Decimal('0')
        return super().movement_path(intent)

    def known_objects(self):
        return {id for id, item in self.items.items()
                if id in self.dungeon.inventory or id in self.dungeon.discovered
                or (item['discovery'] == 'visible' and self.item_positions[id] in self.visibility.visible)}

    def map_view(self):
        visible = self.visibility.visible
        markers = super().map_view()['markers']
        if self.prisoner_position in visible and not self.dungeon.companion_escaped:
            markers.append(dict(kind='ally', label='P', position=coordinate(self.prisoner_position)))
        markers.extend(dict(kind='item', position=coordinate(self.item_positions[id]))
                       for id in self.known_objects() if id not in self.dungeon.inventory
                       and self.item_positions[id] in visible)
        sheet = self.character_context()
        return dict(title=self.title, compact=True, markers=markers,
                    passage_lock_labels={p.id: ('trancada' if p.locked else 'destrancada')
                                         if p.id in self._examined_locks or p.is_open
                                         else 'fechadura não examinada' for p in self.scene.passages},
                    equipment=sheet['clothing'] + ' · Itens: ' + (', '.join(sheet['inventory']) or 'nenhum'),
                    legend='P: prisioneiro · dourado: tochas / itens')

    def character_context(self):
        context = super().character_context()
        if hasattr(self, 'dungeon'):
            context['clothing'] = ('Roupa de empregado da limpeza' if self.dungeon.clothing == 'cleaner_uniform'
                                   else 'Trapos de lã')
            context['inventory'] = [self.items[id]['name'] for id in sorted(self.dungeon.inventory)]
            context['sword_concealed'] = self.dungeon.sword_concealed
        return context

    def interpreter_context(self):
        context = super().interpreter_context()
        state = self.dungeon
        known = self.known_objects()
        context['visible_objects'] = [dict(id=id, name=item['name'], position=coordinate(self.item_positions[id]),
                                           carried=id in state.inventory,
                                           visible=self.item_positions[id] in self.visibility.visible and id not in state.inventory)
                                      for id, item in self.items.items() if id in known]
        if self.prisoner_position in self.visibility.visible and not state.companion_escaped:
            next(c for c in context['visible_creatures'] if c['id'] == 'prisoner')['free'] = state.prisoner_free
        context['world']['map'] = deepcopy(context['map'])
        # A aparência de uma fechadura não revela se está trancada.
        for passage in context['map']['scene']['passages']:
            if passage['id'] not in getattr(self, '_examined_locks', set()) and not passage['is_open']:
                passage['locked'] = None
        context['scenario'] = dict(id='dungeon_escape', operations=list(SCENARIO_OPERATIONS),
            objective='Atravessar a Porta de Saída, na Sala dos Guardas.',
            clothing=context['player_sheet']['clothing'], inventory=sorted(state.inventory),
            sword_concealed=state.sword_concealed, escaped=state.escaped,
            companion_escaped=state.companion_escaped,
            guidance={
                'investigate': 'Investigar/revirar um cômodo ou seus panos/cama: target_id do cômodo referido. Movimento contextual entra nele, se necessário, antes do teste.',
                'take': 'Pegar objeto conhecido: target_id do item. Movimento contextual aproxima até o alcance, sem abrir barreiras.',
                'drop': 'Largar item carregado: target_id do item.',
                'wear': 'Vestir cleaner_uniform, somente depois de encontrá-lo e pegá-lo.',
                'conceal': 'Ocultar longsword sob o uniforme; não torna uma espada invisível.',
                'unlock': 'Destrancar grade ao alcance com cell_key; abrir exige etapa open separada.',
                'listen': 'Ouvir junto de uma porta/cela: target_id da passagem. Revela sinais audíveis, não o futuro.',
                'sneak': 'Movimento furtivo geral até destino conhecido; Hide CD 15 se necessário, seguido do mesmo percurso. NPCs usam seus próprios sentidos e percepção passiva.',
                'wake': 'Acordar prisoner ao alcance, inclusive através da grade.',
                'deceive': 'Tentar passar-se por empregado da limpeza: target_id guard_1, diante dele.',
                'escape': 'Atravessar a saída aberta: target_id outside; nunca teleporta ou abre portas.',
                'wait': 'Aguardar em exploração deixa passar um intervalo da rotina do guarda; não cria turnos.'})
        context['world']['scenario'] = dict(id='dungeon_escape', state={k: sorted(v) if isinstance(v, set) else v for k, v in vars(state).items()},
            items=deepcopy(list(self.items.values())), item_positions={id: coordinate(p) for id, p in self.item_positions.items()},
            prisoner=dict(id='prisoner', position=coordinate(self.prisoner_position),
                          role='Mago ilusionista nível 3; revela-se somente quando libertado. Sem ficha de Guerreiro.',
                          clothing='Trapos de lã', inventory=[],
                          spell='Minor Illusion; som ilusório, CD 13, alcance 9 m, duração 1 minuto; lã dos próprios trapos.'),
            initial_event='A grade da Cela 1 acabou de se abrir magicamente, sem ninguém próximo. O jogador ouviu a fechadura e o metal; não sabe a causa.',
            adjudication='Rotina, itens, disfarce e ilusão são resolvidos pelo cenário. Visão, audição, sono, Hide e Search pertencem ao motor geral por NPC; consulte world.perception e não duplique detecções/testes. Sem parley pendente, não antecipe deslocamento/conflito. Com parley pendente, julgue a fala via influence após speak/challenge; resistência explícita pode iniciar conflito. A abordagem e Influence são regras gerais do Trama. Em combate resolva o turno do guarda normalmente.',
            routine='Após dois intervalos de espera em exploração, o guarda vai ao banheiro por quatro ações do jogador; retorna à mesa depois. Escutar revela sinais dessa rotina.',
            checks={'investigation_uniform': 15, 'listen': 10, 'deception': 15,
                    'sword_notice': 10, 'concealed_sword_notice': 15, 'hide': 15,
                    'illusion_investigation': 13})
        context['world']['scenario']['prisoner']['spellcasting'] = {'intelligence': 16, 'proficiency_bonus': 2, 'spell_save_dc': 13}
        context['world']['conditions'] = ['Tochas fixadas à parede: não bloqueiam movimento nem visão. Iluminação normal, sem visão no escuro para humanos.',
            'Grades permitem visão; paredes e portas fechadas bloqueiam visão e passagem.',
            'Prisioneiro e jogador começam em trapos, sem inventário. O prisioneiro dorme até ser acordado.',
            'Não narre chave, arma escondida, uniforme ou identidade do mago antes da descoberta registrada.']
        return context

    def _operate_door(self, intent):
        passage = self._passage(intent.target_id)
        if passage.is_open != (intent.operation == 'open') and self._near(passage.position):
            self._examined_locks.add(intent.target_id)
        return super()._operate_door(intent)

    def _execute(self, intent, **options):
        if self.dungeon.escaped:
            raise ActionError('A fuga já foi concluída. Reinicie para jogar novamente.')
        self.validate_preparation(intent)
        if isinstance(intent, ScenarioIntent) and intent.operation == 'sneak':
            return super()._execute(intent, **options)
        if isinstance(intent, ScenarioIntent):
            self.encounter.require_turn(self.encounter.player_id)
            return self._scenario_action(intent)
        if isinstance(intent, MovementIntent) and not intent.clarification:
            return self._travel(intent, **options)
        result = super()._execute(intent, **options)
        if isinstance(intent, DoorIntent):
            if not result.changed:
                return result
            self._examined_locks = getattr(self, '_examined_locks', set()) | {intent.target_id}
            if result.changed and intent.operation == 'open' and intent.target_id == 'gate_2':
                self._free_prisoner()
            if result.changed:
                self._notice_guard()
        elif isinstance(intent, RuleIntent) and intent.operation == 'attack':
            self.dungeon.sword_concealed = False
            self.dungeon.disguise = 'failed'
        elif isinstance(intent, NarrativeIntent):
            if intent.operation == 'wait' and self.mode == GameMode.NARRATED:
                self._wait()
        self._advance_bathroom()
        return result

    def _travel(self, intent, *, movement_path=None, include_remainder=True):
        self.validate_preparation(intent)
        self.encounter.require_turn(self.encounter.player_id)
        path, _ = self.movement_path(intent) if movement_path is None else (movement_path, 0)
        if not path:
            return super()._execute(intent, movement_path=path, include_remainder=include_remainder)
        traversed = [self.state.position]
        companion_before = self.prisoner_position
        cost = Decimal('0')
        reactions = []
        protected = Decimal('0')
        result = None
        for index, position in enumerate(path):
            if index == len(path) - 1 and any(c.position == position and self.encounter.states[c.id].hp == 0
                                            for c in self.creatures):
                result = MovementResult(self.state, (), Decimal('0'),
                                        'Você pode atravessar a criatura caída, mas não terminar nessa casa.',
                                        blocked_position=position, stop_code='occupied_destination')
                break
            previous_mode = self.mode
            step_intent = intent if index == 0 else replace(intent, dash=False)
            result = super()._execute(step_intent, movement_path=(position,),
                                      include_remainder=include_remainder and index == len(path) - 1)
            traversed.extend(result.path[1:])
            cost += result.cost_meters
            protected += result.protected_meters
            reactions.extend(getattr(result, 'reactions', ()))
            if len(result.path) > 1:
                self._notice_guard()
                self._follow_prisoner(traversed[-2])
                self._check_exit()
            if previous_mode == GameMode.NARRATED and self.mode == GameMode.TURN_BASED:
                result = replace(result, state=self.state, stop_reason='O guarda identificou a fuga; a iniciativa determina quem age agora.',
                                 stop_code='conflict_started')
            if self.parley_pending:
                result = replace(result, state=self.state,
                    stop_reason='O guarda exige que você pare. Você pode responder antes de decidir pelo combate.',
                    stop_code='parley_pending')
            if result.stop_reason or self.dungeon.escaped:
                break
        self.last_path = tuple(traversed)
        if self.prisoner_position != companion_before:
            self._event('companion_followed', 'O ilusionista acompanha seu percurso.', actor_id='prisoner',
                        origin=coordinate(companion_before), destination=coordinate(self.prisoner_position))
        self._advance_bathroom()
        # A última casa pode não provocar reação, mas as anteriores continuam
        # pertencendo ao percurso e precisam chegar ao relatório/narrador.
        return TravelResult(result.state, tuple(traversed), cost, result.stop_reason,
                            result.blocked_position, protected, stop_code=result.stop_code,
                            reactions=tuple(reactions))

    def _scenario_action(self, intent):
        operation, target = intent.operation, intent.target_id
        state = self.dungeon
        changed = False
        if operation == 'investigate':
            if target != self._area():
                raise ActionError('Entre no cômodo antes de investigá-lo.')
            self._pay_action()
            if target == 'cell_4':
                if 'longsword' not in state.discovered:
                    state.discovered.add('longsword')
                    self._event('item_found', 'Uma espada longa está sob os panos.', item_id='longsword')
                passed, _ = self._check('player', 'investigation', 15)
                if passed and 'cleaner_uniform' not in state.discovered:
                    state.discovered.add('cleaner_uniform')
                    self._event('item_found', 'Você encontra roupa de empregado da limpeza bem escondida sob a cama.', item_id='cleaner_uniform')
                changed = True
            else:
                self._event('searched', 'A busca não revela outros objetos ocultos neste cômodo.')
        elif operation in {'take', 'drop', 'wear', 'conceal'}:
            if target not in self.items:
                raise ActionError('Objeto desconhecido.')
            if operation == 'take':
                if target in state.inventory:
                    raise ActionError('Você já carrega esse objeto.')
                if target not in self.known_objects() or not self._near(self.item_positions[target]):
                    raise ActionError('Encontre o objeto e aproxime-se para pegá-lo.')
                self._pay_interaction()
                if target == 'cell_key' and self._guard_sees_player():
                    passed, _ = self._check('player', 'sleight_of_hand', 13)
                    if not passed:
                        self._start_conflict('O guarda flagra a tentativa de pegar a chave.')
                        return RuleResult(dict(operation=operation, changed=False, summary='A chave continua na mesa.'),
                                          'O guarda flagrou o furto; a iniciativa determina quem age agora.')
                state.inventory.add(target)
                if target == 'longsword':
                    self.encounter.sheets['player'] = replace(self.encounter.player_sheet, weapons=('longsword',))
                    self._sword_checked = False
                self._event('item_taken', f'Você pega {self.items[target]["name"]}.', actor_id='player', item_id=target)
            else:
                if target not in state.inventory:
                    raise ActionError('Você não carrega esse objeto.')
                if operation == 'drop':
                    self._pay_interaction()
                    state.inventory.remove(target)
                    state.discovered.add(target)
                    self.item_positions[target] = self.state.position
                    if target == 'longsword':
                        self.encounter.sheets['player'] = replace(self.encounter.player_sheet, weapons=())
                        state.sword_concealed = False
                    if target == 'cleaner_uniform':
                        state.clothing = 'rags'
                        state.disguise = 'untested'
                    if target in {'longsword', 'cleaner_uniform'}:
                        state.sword_concealed = False
                        self._sword_checked = False
                elif operation == 'wear':
                    if target != 'cleaner_uniform':
                        raise ActionError('Esse objeto não é roupa.')
                    self._pay_action()
                    state.clothing = target
                else:
                    if target != 'longsword' or state.clothing != 'cleaner_uniform':
                        raise ActionError('É preciso vestir o uniforme para ocultar a espada sob ele.')
                    self._pay_action()
                    state.sword_concealed = True
                self._event(operation, f'{operation}: {self.items[target]["name"]}.', actor_id='player', item_id=target)
            changed = True
            self._notice_guard()
        elif operation == 'unlock':
            passage = self._passage(target)
            if not passage.locked:
                return RuleResult(dict(operation=operation, changed=False, status='already_satisfied', summary='A passagem já está destrancada.'))
            if not self._near(passage.position):
                raise ActionError('Aproxime-se da fechadura.')
            if 'cell_key' not in state.inventory or target not in {'gate_2', 'gate_3'}:
                raise ActionError('Você precisa da chave das celas para essa fechadura.')
            self._pay_interaction()
            self.scene = replace(self.scene, passages=tuple(replace(p, locked=False) if p.id == target else p
                                                           for p in self.scene.passages))
            self._examined_locks = getattr(self, '_examined_locks', set()) | {target}
            self._event('unlocked', f'{passage.name} destrancada; ainda está fechada.', actor_id='player', target_id=target)
            changed = True
        elif operation == 'listen':
            passage = self._passage(target)
            if not self._near(passage.position):
                raise ActionError('Aproxime-se da porta ou grade para escutar.')
            self._pay_action()
            passed, _ = self._check('player', 'perception', 10)
            if passed:
                text = ('Você ouve o guarda no banheiro; os passos deixaram a mesa.' if state.guard_activity == 'bathroom'
                        else 'Um único guarda se mexe junto à mesa. Ele resmunga que logo precisará ir ao banheiro.')
                if target == 'gate_2':
                    text = 'Você ouve a respiração do prisioneiro.'
                elif target not in {'guard_door', 'bathroom_door'}:
                    text = 'Você escuta atentamente; nenhum novo sinal relevante se destaca.'
                self._event('heard', text)
        elif operation == 'wake':
            if target != 'prisoner':
                raise ActionError('Escolha o prisioneiro para acordar.')
            if state.prisoner_awake:
                return RuleResult(dict(operation=operation, changed=False, status='already_satisfied', summary='O prisioneiro já está acordado.'))
            if not self._near(self.prisoner_position) and not self._near(self._passage('gate_2').position):
                raise ActionError('Aproxime-se da grade do prisioneiro para acordá-lo.')
            self._pay_action()
            if self._near(self.prisoner_position):
                self._wake_prisoner()  # Contato físico ao alcance não depende de audição.
            else:
                self.emit_noise('player', self.state.position, 'loud', 'Você chama o prisioneiro para acordá-lo.')
            changed = state.prisoner_awake
        elif operation == 'deceive':
            if target != 'guard_1' or not self._guard_sees_player():
                raise ActionError('O guarda precisa ver e ouvir você para avaliar o disfarce.')
            if state.clothing != 'cleaner_uniform':
                raise ActionError('Você precisa vestir o uniforme da limpeza.')
            self._pay_action()
            self._assess_disguise()
            changed = True
        elif operation == 'escape':
            if target != 'outside':
                raise ActionError('A saída deste cenário é outside.')
            return self._travel(MovementIntent((), False, '', 'outside'))
        else:
            raise ActionError('Interação não implementada.')
        self._advance_bathroom()
        return RuleResult(dict(operation=operation, changed=changed, target_id=target,
                               summary='Consulte os fatos e testes registrados nas respostas do cenário.'))

    def _wake_prisoner(self):
        if self.dungeon.prisoner_awake:
            return
        self.dungeon.prisoner_awake = True
        self.perception.awakened.add('prisoner')
        if self._passage('gate_2').is_open:
            self._event('say', 'Obrigado! O prisioneiro desperta e fala baixo ao ver sua grade aberta.', actor_id='prisoner')
            self.emit_noise('prisoner', self.prisoner_position, 'quiet', 'Agradecimento em voz baixa.')
            return
        self._event('say', 'Ei! Por favor, me solte! A chave está na mesa do guarda!', actor_id='prisoner')
        self.dungeon.discovered.add('cell_key')  # Informação dita pelo prisioneiro; não concede o item.
        self.emit_noise('prisoner', self.prisoner_position, 'loud',
                        'O pedido de socorro do prisioneiro ecoa nas celas.')

    def on_perception(self, event):
        # O motor detecta; este cenário decide o que os personagens fazem depois.
        if event['operation'] == 'awakened' and event['actor_id'] == 'prisoner':
            self._wake_prisoner()
            return
        if event['operation'] != 'perception_detected' or event['actor_id'] != 'guard_1':
            return super().on_perception(event)
        if event['target_id'] == 'minor_illusion':
            return  # O som foi ouvido; Study e distração são resolvidos na interação da magia.
        if event['target_id'] == 'player' and event['level'] == 'seen':
            self._notice_guard()
        elif (event['level'] in {'heard', 'located'} and self.mode == GameMode.NARRATED
              and not self.parley_pending and not self.dungeon.distraction_remaining
              and 'guard_1' not in self.peaceful_npcs):
            # Passos na sala podem ser atividade comum; no setor de celas motivam busca.
            if event['target_id'] == 'player' and self._area() not in {'corridor', 'cell_1', 'cell_2', 'cell_3', 'cell_4'}:
                return
            self.dungeon.guard_alert = True
            self.dungeon.guard_activity = 'investigating'
            self._event('alert', 'O guarda ouve um ruído no setor das celas e vem investigar.', actor_id='guard_1')
            doors = ('bathroom_door', 'guard_door') if self.dungeon.bathroom_remaining > 0 else ('guard_door',)
            self.dungeon.bathroom_remaining = 0
            self._move_guard(Position(8, 15), open_doors=doors)

    def _notice_guard(self):
        state = self.dungeon
        if (not self._guard_sees_player() or self.mode == GameMode.TURN_BASED or state.escaped
                or self.parley_pending or 'guard_1' in self.peaceful_npcs):
            return
        if state.distraction_remaining:
            return
        if state.clothing == 'cleaner_uniform' and not state.guard_alert:
            self._assess_disguise()
            return
        if not self.parley_pending and 'guard_1' not in self.peaceful_npcs:
            self._events.append(self.offer_parley('guard_1', 'Você aí! Pare! O que está fazendo fora da cela?'))

    def observe_npc(self, actor_id):
        if actor_id == 'guard_1':
            self.perceive()
            self._notice_guard()
        else:
            super().observe_npc(actor_id)

    def _assess_disguise(self):
        state = self.dungeon
        if state.disguise != 'untested':
            if state.disguise == 'failed':
                self._start_conflict('O guarda já reconheceu o falso empregado.')
            elif 'longsword' in state.inventory and not getattr(self, '_sword_checked', False):
                self._inspect_sword()
            return
        passed, _ = self._check('player', 'deception', 15)
        state.disguise = 'accepted' if passed else 'failed'
        self._event('disguise', 'O guarda aceita a identificação como empregado da limpeza.' if passed
                    else 'O guarda desconfia do uniforme e reconhece a tentativa de fuga.', accepted=passed)
        if not passed:
            self._start_conflict('O disfarce não convenceu o guarda.')
        elif 'longsword' in state.inventory:
            self._inspect_sword()

    def _inspect_sword(self):
        self._sword_checked = True
        passed, _ = self._check('guard_1', 'perception', 15 if self.dungeon.sword_concealed else 10)
        if passed:
            self.dungeon.disguise = 'failed'
            self._start_conflict('O guarda percebe a espada; o disfarce cai.')

    def _start_conflict(self, reason):
        if self.mode == GameMode.TURN_BASED or not self._guard_available():
            return
        self.dungeon.guard_alert = True
        result = self._execute_rule(RuleIntent('start_combat'))
        self._event('start_conflict', reason, actor_id='guard_1', initiative=result.event)

    def _move_guard(self, goal, *, open_doors=()):
        """Rotina de exploração: caminho validado, sem atravessar jogador ou portas."""
        def walk(path):
            before = self.guard.position
            result = TravelExecutor(self).run('guard_1', self._guard_movement_grid(),
                MovementState(before, self.encounter.sheets['guard_1'].speed_meters), MovementRequest(path))
            if self.guard.position != before:
                self._event('move', 'O guarda se desloca.', actor_id='guard_1',
                            origin=coordinate(before), destination=coordinate(self.guard.position),
                            cost_meters=float(result.cost_meters))
            return result.stop_reason is None

        self._notice_guard()
        if self.parley_pending or self.mode == GameMode.TURN_BASED:
            return False
        for id in open_doors:
            p = self._passage(id)
            # O guarda alcança a porta pelo próprio lado antes de abri-la.
            grid = replace(self.grid, blocked=self.grid.blocked | {self.state.position})
            if p.is_open:
                continue
            goals = frozenset(Position(p.position.x + dx, p.position.y + dy)
                              for dx, dy in DIRECTIONS.values()
                              if line_of_sight(Position(p.position.x + dx, p.position.y + dy), p.position, self.scene.opaque))
            try:
                approach = path_to_cells(grid, self.guard.position, goals)
            except MovementError:
                return False
            if approach and not walk(approach):
                return False
            if distance(self.guard.position, p.position) <= 1:
                self.scene = self.scene.with_passage(id, True)
                self.grid = self.scene.movement_grid
                self._event('open', f'O guarda abre {p.name}.', actor_id='guard_1', target_id=id)
                self.perceive()
                self._notice_guard()
                if self.parley_pending or self.mode == GameMode.TURN_BASED:
                    return False
        blocked = self.grid.blocked | {self.state.position}
        blocked |= {self.prisoner_position}
        grid = replace(self.grid, blocked=frozenset(blocked))
        try:
            path = path_to_cells(grid, self.guard.position, frozenset({goal}))
        except MovementError:
            self._event('routine_blocked', 'O guarda não consegue completar o percurso; permanece na posição alcançada.',
                        actor_id='guard_1', destination=coordinate(goal))
            return False
        return walk(path) if path else True

    def _guard_movement_grid(self):
        return replace(self.grid, blocked=self.grid.blocked | {self.state.position, self.prisoner_position})

    def _wait(self):
        state = self.dungeon
        if state.guard_alert or not self._guard_available() or state.guard_activity == 'bathroom':
            return
        state.waits += 1
        self._event('time_passed', 'Você aguarda um intervalo da rotina da dungeon.', actor_id='player')
        if state.waits >= 2:
            if self._move_guard(Position(*self.definition['bathroom_position']), open_doors=('bathroom_door',)):
                state.guard_activity = 'bathroom'
                state.bathroom_remaining = 5  # Desconta o próprio wait; restam quatro ações.
                self.scene = self.scene.with_passage('bathroom_door', False)
                self.grid = self.scene.movement_grid
                self._event('bathroom', 'Passos, uma porta e o ruído de um ferrolho: o guarda entrou no banheiro.', actor_id='guard_1')

    def _advance_bathroom(self):
        state = self.dungeon
        if self.mode == GameMode.TURN_BASED or state.escaped or self.parley_pending:
            return
        if state.distraction_remaining:
            state.distraction_remaining -= 1
            if state.distraction_remaining == 0:
                state.guard_activity = 'on_duty'
                self._move_guard(Position(*self.definition['guard_home']), open_doors=('guard_door',))
                self._event('return', 'O guarda encerra a busca pelo ruído e retorna à sala.', actor_id='guard_1')
                self._notice_guard()
        if state.guard_activity == 'bathroom':
            state.bathroom_remaining -= 1
            if state.bathroom_remaining <= 0:
                if self._move_guard(Position(*self.definition['guard_home']), open_doors=('bathroom_door',)):
                    state.guard_activity = 'on_duty'
                    state.waits = 0
                    self._event('return', 'O guarda retorna do banheiro à sala.', actor_id='guard_1')
                    self._notice_guard()

    def _free_prisoner(self):
        if self.dungeon.prisoner_free:
            return
        if not self.dungeon.prisoner_awake:
            self.dungeon.prisoner_awake = True
            self.perception.awakened.add('prisoner')
        self.dungeon.prisoner_free = True
        self._event('prisoner_freed', 'O prisioneiro se ergue e revela ser um mago ilusionista. Ele retira um fiapo de lã dos trapos e propõe distrair o guarda.', actor_id='prisoner')
        self._illusion()

    def _illusion(self):
        if self.dungeon.illusion_used or not self._guard_available() or self.mode == GameMode.TURN_BASED:
            return
        # Cantrip limitado ao encontro: nenhum equipamento ou grimório surge do nada.
        self.dungeon.illusion_used = True
        source = Position(8, 17)
        # O som fica a 7,5 m da cama, através da grade que acabou de abrir.
        self._event('spell_cast', 'O ilusionista cria o som de uma fuga no fundo do corredor com Ilusão Menor.',
                    actor_id='prisoner', spell='minor_illusion', component='Lã retirada dos próprios trapos',
                    source=coordinate(source), duration_seconds=60, spell_dc=13)
        self.emit_noise('minor_illusion', source, 'loud', 'Som ilusório de uma fuga ruidosa no corredor.')
        if not self.perception.hears(self.guard, Noise('minor_illusion', source, 'loud', 'Som ilusório.')):
            self._event('illusion_unheard', 'O guarda não ouve a ilusão.', actor_id='guard_1', perceptible=False)
            return
        passed, _ = self._check('guard_1', 'investigation', 13)
        if passed:
            self._event('illusion_recognized', 'O guarda examina o som e reconhece a ilusão.', actor_id='guard_1')
            return
        self.dungeon.distraction_remaining = 5
        self.dungeon.guard_alert = False
        self.dungeon.guard_activity = 'distracted'
        doors = ('bathroom_door', 'guard_door') if self.dungeon.bathroom_remaining > 0 else ('guard_door',)
        self._move_guard(source, open_doors=doors)
        self._event('distracted', 'O guarda segue o ruído ilusório, deixando uma oportunidade de fuga. O mago acompanha você.', actor_id='guard_1')

    def _follow_prisoner(self, previous_player_position):
        if not self.dungeon.prisoner_free or self.mode == GameMode.TURN_BASED:
            return
        occupants = {self.state.position} | ({self.guard.position} if self._guard_available() else set())
        grid = replace(self.grid, blocked=self.grid.blocked | occupants)
        goals = frozenset({previous_player_position})
        try:
            path = path_to_cells(grid, self.prisoner_position, goals)
        except MovementError:
            return
        if path:
            before = self.prisoner_position
            self.prisoner_position = path[-1]
            self.observers = tuple(replace(o, position=self.prisoner_position) if o.id == 'prisoner' else o for o in self.observers)
            logger.debug('dungeon.companion_moved', extra={'data': {'actor_id': 'prisoner',
                'origin': coordinate(before), 'destination': coordinate(self.prisoner_position),
                'path': [coordinate(p) for p in path]}})

    def _check_exit(self):
        if self._area() != 'outside':
            return
        if self.mode == GameMode.TURN_BASED and self._guard_available():
            # Chegar à saída é o objetivo; não exige matar o guarda.
            self.encounter.combat = None
        companion_near = (self.dungeon.prisoner_free
                          and distance(self.prisoner_position, self.state.position) <= 1)
        self.dungeon.companion_escaped = False
        if companion_near:
            # Aliados podem atravessar o espaço um do outro, sem terminar juntos.
            outside = next(a for a in self.scene.areas if a.id == 'outside')
            blocked = self.grid.blocked | ({self.guard.position} if self._guard_available() else set())
            try:
                path = path_to_cells(replace(self.grid, blocked=frozenset(blocked)), self.prisoner_position,
                                     outside.cells - {self.state.position})
            except MovementError:
                path = None
            if path is not None:
                if path:
                    self.prisoner_position = path[-1]
                    self.observers = tuple(replace(o, position=self.prisoner_position) if o.id == 'prisoner' else o for o in self.observers)
                self.dungeon.companion_escaped = True
        self.dungeon.escaped = True
        self._event('escaped', 'Você atravessa a saída e escapa da dungeon.' +
                    (' O ilusionista escapa com você.' if self.dungeon.companion_escaped else ''), actor_id='player')

"""Coordena intenções e estado: movimento, ações, visão e criaturas."""

from dataclasses import replace
from decimal import Decimal
import logging
from time import perf_counter

from trama.movement import (
    Grid, MovementError, MovementRequest, MovementResult, MovementState,
    Position, step_cost,
)
from trama.scene import Scene
from trama.application.intents import (
    DIRECTIONS, DoorIntent, PlayerIntent, MovementIntent, RuleIntent, NarrativeIntent, ScenarioIntent,
)
from trama.application.routing import path_to, path_to_cells
from trama.application.preparation import SpatialRequirement
from trama.actions import ActionBudget, ActionError, DoorActionResult, operate_door
from trama.creatures import Creature
from trama.vision import Visibility, field_of_view, line_of_sight
from trama.application.context import build_context
from trama.distances import format_meters
from trama.characters import CharacterError, FighterSheet, ability_check
from trama.dice import Roller
from trama.application.encounter import Encounter, RuleResult
from trama.application.sheets import sheet_context, enemy_summary
from trama.application.sheet_options import sheet_options
from trama.application.travel import TravelExecutor
from trama.application.modes import GameMode
from trama.application.parley import Parley, InfluenceRequest
from trama.application.perception import PerceptionSystem
from trama.perception import Noise, Observer
from trama.observability import log_context, new_id

logger = logging.getLogger(__name__)


class GameSession:
    def __init__(
        self, grid: Grid, initial_state: MovementState, scene: Scene | None = None,
        creatures: tuple[Creature, ...] = (),
        *, player_sheet: FighterSheet | None = None, enemy_sheets: tuple[FighterSheet, ...] | None = None,
        roller: Roller | None = None, observers: tuple[Observer, ...] = (),
    ) -> None:
        if not grid.contains(initial_state.position) or initial_state.position in grid.blocked:
            raise ValueError("O personagem deve começar em uma casa livre do mapa.")
        self.grid = grid
        if scene is not None and scene.movement_grid != grid:
            raise ValueError("O cenário e a sessão devem usar a mesma grade.")
        self.scene = scene
        self.initial_scene = scene
        self.creatures = creatures
        self.initial_creatures = creatures
        self.observers = observers
        self.initial_observers = observers
        if (len({o.id for o in observers}) != len(observers)
                or {o.id for o in observers} & {c.id for c in creatures}
                or len({o.position for o in observers}) != len(observers)
                or any(o.position == initial_state.position or o.position in {c.position for c in creatures} for o in observers)
                or any(not grid.contains(o.position) or o.position in grid.blocked for o in observers)
                or any(o.senses.response == 'challenge' for o in observers)):
            raise ValueError('Observadores precisam de ids distintos e posições livres no mapa.')
        if (len({c.id for c in creatures}) != len(creatures)
                or len({c.position for c in creatures}) != len(creatures)
                or any(not grid.contains(c.position) or c.position in grid.blocked
                       or c.position == initial_state.position for c in creatures)):
            raise ValueError("Criaturas devem ocupar casas livres e distintas.")
        player = player_sheet or FighterSheet("player", "Jogador")
        if player_sheet is not None and initial_state.speed_meters != player.speed_meters:
            raise CharacterError("A velocidade inicial deve corresponder à ficha do personagem.")
        enemies = enemy_sheets if enemy_sheets is not None else tuple(
            FighterSheet(c.id, c.name, level=1, subclass=None) for c in creatures)
        if {s.id for s in enemies} != {c.id for c in creatures}:
            raise CharacterError("Cada criatura precisa de uma ficha correspondente.")
        self._initial_sheets = (player, enemies)
        self._roller = roller
        self.encounter = Encounter(player, enemies, roller)
        self.budget = ActionBudget(action_used=initial_state.dash_used)
        self._vision_key = None
        self._visibility = Visibility(frozenset())
        self.initial_state = initial_state
        self.state = initial_state
        self.last_path: tuple[Position, ...] = ()
        self.npc_movement: dict[str, MovementState] = {}
        self.auto_opportunity = False
        self.pending_opportunity = None
        self.suppressed_opportunity = None
        self.parley: Parley | None = None
        self.peaceful_npcs: set[str] = set()
        self._events = []
        self.perception = PerceptionSystem(self)
        self.reset_version = 0
        logger.info("game.session_created", extra={"data": {"player_id": player.id,
                    "position": initial_state.position, "creature_count": len(creatures)}})
        logger.debug("game.initial_state", extra={"data": {"movement": initial_state,
                     "sheets": self.encounter.sheets.copy(), "resources": self.encounter.states.copy()}})

    @property
    def budget(self) -> ActionBudget:
        return self.encounter.budgets[self.encounter.player_id]

    @budget.setter
    def budget(self, value: ActionBudget) -> None:
        self.encounter.budgets[self.encounter.player_id] = value

    def character_context(self) -> dict:
        return sheet_context(self.encounter.player_sheet,
                             self.encounter.states[self.encounter.player_id], self.budget)

    def map_view(self) -> dict:
        """Projeção para visualizadores; marcadores usam coordenadas em base 1."""
        markers = [{"id": o.id, "kind": "scene_object", "appearance": o.kind,
                    "position": [o.position.x + 1, o.position.y + 1],
                    "attachment": {"surface": o.attachment.surface, "side": o.attachment.side},
                    "blocks_movement": o.blocks_movement, "blocks_vision": o.blocks_vision}
                   for o in self.scene.objects if o.position in self.visibility.visible] if self.scene else []
        return {"title": "Cela e Guardas", "compact": False, "markers": markers,
                "passage_lock_labels": {}, "equipment": "",
                "legend": "Humano · visão normal · áreas claras: visão atual"}

    def drain_world_events(self) -> tuple[dict, ...]:
        """Fatos comuns e adicionais do cenário, consumidos pelo fluxo real."""
        events, self._events = tuple(self._events), []
        return events

    @property
    def parley_pending(self):
        return self.parley is not None and self.parley.status == 'pending'

    def npc_sees_player(self, actor_id):
        try:
            return self.perception.sees(self.perception.observer(actor_id), self.state.position)
        except ActionError:
            return False

    def perceive(self, noise=None):
        events = self.perception.evaluate(noise)
        self._events.extend(events)
        for event in events:
            logger.info('perception.detected' if event['operation'] == 'perception_detected' else 'perception.awakened', extra={'data': event})
            self.on_perception(event)
        return events

    def on_perception(self, event):
        if event['operation'] != 'perception_detected' or event['target_id'] != self.encounter.player_id:
            return
        observer = self.perception.observer(event['actor_id'])
        if (observer.senses.response == 'challenge' and event['level'] == 'seen'
                and self.mode == GameMode.NARRATED and not self.parley_pending
                and observer.id not in self.peaceful_npcs):
            self._events.append(self.offer_parley(observer.id, 'Pare! O que você está fazendo aqui?'))

    def emit_noise(self, actor_id, position, volume='normal', reason='Ruído.'):
        if actor_id == self.encounter.player_id and volume != 'quiet':
            self.perception.hidden_total = None
        return self.perceive(Noise(actor_id, position, volume, reason))

    def offer_parley(self, actor_id, demand):
        """Uma abordagem exige resposta, sem iniciativa ou aproximação adicional."""
        if self.mode != GameMode.NARRATED or not self.npc_sees_player(actor_id):
            raise ActionError('A abordagem exige um NPC consciente que perceba o jogador fora de combate.')
        if not isinstance(demand, str) or not demand.strip():
            raise ActionError('A abordagem exige uma fala concreta do NPC.')
        if self.parley_pending:
            raise ActionError('Já há uma abordagem aguardando resposta.')
        npc = next(c for c in self.creatures if c.id == actor_id)
        self.peaceful_npcs.discard(actor_id)
        self.parley = Parley(actor_id, demand, self.state.position, npc.position)
        event = dict(operation='parley', text=demand, changed=True,
                     perceptible=True, speaker=npc.name, **self.parley.context())
        logger.info('game.parley_started', extra={'data': event})
        return event

    def observe_npc(self, actor_id):
        """Aproximação hostil em exploração para na primeira percepção do jogador.

        Cenários podem julgar disfarce/distração antes de solicitar a abordagem;
        a preservação das posições e a conversa pertencem à sessão geral.
        """
        self.perceive()
        npc = next(c for c in self.creatures if c.id == actor_id)
        if (self.mode == GameMode.NARRATED and npc.hostile and not self.parley_pending
                and actor_id not in self.peaceful_npcs and self.npc_sees_player(actor_id)):
            self._events.append(self.offer_parley(actor_id, 'Pare! O que você está fazendo aqui?'))

    def resolve_influence(self, actor_id, request: InfluenceRequest, reason):
        if not self.parley_pending or self.parley.actor_id != actor_id or self.encounter.combat:
            raise ActionError('Não há conversa pendente com esse NPC.')
        if not isinstance(request, InfluenceRequest):
            raise ActionError('Informe o julgamento da tentativa de Influence.')
        event = dict(operation='influence', actor_id=actor_id, text=reason, changed=True,
                     perceptible=True, willingness=request.willingness, skill=request.skill,
                     attitude=request.attitude)
        passed = request.willingness == 'willing'
        if request.willingness == 'hesitant':
            player = self.encounter.player_id
            dc = max(15, self.encounter.sheets[actor_id].abilities.intelligence)
            state, roll, total = ability_check(self.encounter.player_sheet, self.encounter.states[player],
                request.skill, dc, self.encounter.roller,
                advantage=request.attitude == 'friendly', disadvantage=request.attitude == 'hostile')
            self.encounter.states[player] = state
            passed = total >= dc
            event.update(dc=dc, dice=list(roll.dice), total=total, passed=passed,
                         advantage=roll.advantage, disadvantage=roll.disadvantage)
        event['accepted'] = passed
        self.parley = replace(self.parley, status='peaceful' if passed else 'combat')
        if passed:
            self.peaceful_npcs.add(actor_id)
        else:
            # A recusa desta abordagem torna o interlocutor um adversário,
            # mesmo se ele não era marcado como hostil antes da conversa.
            self.creatures = tuple(replace(c, hostile=True) if c.id == actor_id else c for c in self.creatures)
            event['initiative'] = self._execute_rule(RuleIntent('start_combat')).event
        logger.info('game.influence_resolved', extra={'data': event})
        return event

    def character_options(self) -> list[dict]:
        """Consulta para a ficha, sem rolagens, gastos ou alteração do estado."""
        origin = self.state.position
        opaque = self.scene.opaque if self.scene else self.grid.blocked

        def reachable(position):
            return (max(abs(position.x - origin.x), abs(position.y - origin.y)) <= 1
                    and line_of_sight(origin, position, opaque))

        targets = tuple(c.name for c in self.creatures if c.hostile
                        and self.encounter.states[c.id].hp > 0
                        and c.position in self.visibility.visible and reachable(c.position))
        occupied = {origin, *(c.position for c in self.creatures)}
        doors = tuple(p.name for p in self.scene.passages
                      if p.position in self.visibility.visible and reachable(p.position)
                      and ((p.is_open and p.position not in occupied) or (not p.is_open and not p.locked))) if self.scene else ()
        costs = []
        grid = self._movement_grid()
        for dx, dy in DIRECTIONS.values():
            try:
                costs.append(step_cost(grid, origin, Position(origin.x + dx, origin.y + dy)))
            except MovementError:
                pass
        combat = self.encounter.combat
        return sheet_options(
            self.encounter.player_sheet, self.encounter.states[self.encounter.player_id], self.budget, self.state,
            turn_based=combat is not None, player_turn=combat is None or combat.active_id == self.encounter.player_id,
            can_step=bool(costs), can_move=any(c <= self.state.remaining_meters for c in costs),
            attack_targets=targets, door_targets=doors,
        )

    @property
    def mode(self) -> GameMode:
        return GameMode.TURN_BASED if self.encounter.combat else GameMode.NARRATED

    def visible_enemy_summaries(self) -> list[dict]:
        return [enemy_summary(self.encounter.sheets[c.id], self.encounter.states[c.id])
                for c in self.creatures if c.hostile and c.position in self.visibility.visible]

    def combat_context(self) -> dict | None:
        combat = self.encounter.combat
        if combat is None:
            return None
        visible_ids = {c.id for c in self.creatures if c.position in self.visibility.visible}
        return {"round": combat.round, "active_id": combat.active_id, "player_turn": combat.active_id == self.encounter.player_id,
                "active": (self.encounter.sheets[combat.active_id].name
                           if combat.active_id in visible_ids or combat.active_id == self.encounter.player_id
                           else "Inimigo fora de visão"),
                "order": [{"id": e.id, "name": e.name, "initiative": e.roll.total}
                          for e in combat.order if e.id in visible_ids or e.id == self.encounter.player_id]}

    @property
    def visibility(self) -> Visibility:
        key = (self.state.position, self.grid, self.scene)
        if key != self._vision_key:
            self._visibility = field_of_view(
                self.grid, self.state.position,
                opaque=self.scene.opaque if self.scene else self.grid.blocked,
                dim=self.scene.dim if self.scene else frozenset(),
                dark=self.scene.dark if self.scene else frozenset(),
            )
            self._vision_key = key
        return self._visibility

    def interpreter_context(self) -> dict:
        context = build_context(self.grid, self.state, self.scene, self.creatures, self.visibility, self.budget)
        context['visible_creatures'].extend(dict(id=o.id, name=o.name, column=o.position.x + 1,
            row=o.position.y + 1, hostile=False, sleeping=self.perception.sleeping(o))
            for o in self.observers if o.position in self.visibility.visible)
        context["player_sheet"] = self.character_context()
        context["visible_enemies"] = self.visible_enemy_summaries()
        context["combat"] = self.combat_context()
        context["mode"] = self.mode.value
        context["parley"] = self.parley.context() if self.parley else None
        context["sensing"] = {"hidden": self.perception.hidden_total is not None,
                              "can_hide": self.perception.can_hide()}
        last = self.encounter.last_attacks.get(self.encounter.player_id)
        context["last_attack"] = ({**last, "target_alive": self.encounter.states[last["target_id"]].hp > 0,
                                   "target_visible": any(c.id == last["target_id"] and c.position in self.visibility.visible
                                                         for c in self.creatures)} if last else None)
        context["equipped_weapons"] = list(self.encounter.player_sheet.weapons)
        if self.mode == GameMode.NARRATED:
            context["character"].update(remaining_meters=None, turn=None,
                                        action_used=False, free_interaction_used=False)
        context["world"] = {
            "perception": self.perception.context(),
            "opportunity_attacks": {"player": "automatic" if self.auto_opportunity else "confirm",
                                    "guards": "automatic", "reach_meters": 1.5},
            "map": context["map"],
            "npcs": [{**enemy_summary(self.encounter.sheets[c.id], self.encounter.states[c.id]),
                      "column": c.position.x + 1, "row": c.position.y + 1,
                      "hostile": c.hostile, "visible_to_player": c.position in self.visibility.visible,
                      "sheet": sheet_context(self.encounter.sheets[c.id], self.encounter.states[c.id],
                                             self.encounter.budgets[c.id])}
                     for c in self.creatures],
            "lighting": {"dim": [[p.x + 1, p.y + 1] for p in sorted(self.scene.dim, key=lambda p: (p.y, p.x))],
                         "dark": [[p.x + 1, p.y + 1] for p in sorted(self.scene.dark, key=lambda p: (p.y, p.x))]} if self.scene else {"dim": [], "dark": []},
            "conditions": ["Iluminação indicada em world.lighting; humanos não enxergam no escuro sem sentidos especiais.",
                           "Portas fechadas bloqueiam visão e passagem; som pode atravessá-las com atenuação."],
        }
        return context

    def reach_requirement(self, target_id: str, position: Position, *, include_target=False) -> SpatialRequirement | None:
        """Posições no alcance corpo a corpo/interação com linha de visão."""
        opaque = self.scene.opaque if self.scene else self.grid.blocked
        origin = self.state.position
        if (max(abs(origin.x - position.x), abs(origin.y - position.y)) <= 1
                and line_of_sight(origin, position, opaque)):
            return None
        offsets = (*DIRECTIONS.values(), (0, 0)) if include_target else DIRECTIONS.values()
        cells = frozenset(Position(position.x + dx, position.y + dy) for dx, dy in offsets
                          if line_of_sight(Position(position.x + dx, position.y + dy), position, opaque))
        return SpatialRequirement('in_reach', target_id, cells)

    def spatial_requirement(self, intent) -> SpatialRequirement | None:
        """Consulta sem rolagens, gastos ou decisões de linguagem natural."""
        if isinstance(intent, DoorIntent) and self.scene:
            passage = next((p for p in self.scene.passages if p.id == intent.target_id), None)
            if passage and passage.is_open != (intent.operation == 'open'):
                requirement = self.reach_requirement(passage.id, passage.position)
                if requirement:
                    return SpatialRequirement('in_reach', passage.id, self.scene.destination_cells(passage.id))
        if isinstance(intent, RuleIntent) and intent.operation == 'attack':
            target = next((c for c in self.creatures if c.id == intent.target_id), None)
            if target:
                return self.reach_requirement(target.id, target.position)
        return None

    def validate_preparation(self, intent) -> None:
        """Condições conhecidas que não devem provocar caminhada inútil."""
        if self.parley_pending and not isinstance(intent, NarrativeIntent) and not (
                isinstance(intent, RuleIntent) and intent.operation in {'attack', 'start_combat'}):
            raise ActionError('Responda à abordagem antes de continuar: você pode conversar ou iniciar combate.')
        if isinstance(intent, DoorIntent):
            self.encounter.require_turn(self.encounter.player_id)
            passage = next((p for p in self.scene.passages if p.id == intent.target_id), None) if self.scene else None
            if passage is None:
                raise ActionError('A passagem informada não existe neste mapa.')
            if (passage.is_open != (intent.operation == 'open') and self.mode == GameMode.TURN_BASED
                    and self.budget.free_interaction_used and not self.budget.action_available):
                raise ActionError('A ação deste turno já foi utilizada.')
        elif isinstance(intent, RuleIntent) and intent.operation == 'attack':
            self._validate_attack(intent)

    def _validate_attack(self, intent: RuleIntent) -> Creature:
        self.encounter.require_turn(self.encounter.player_id)
        target = next((c for c in self.creatures if c.id == intent.target_id), None)
        if target is None or target.position not in self.visibility.visible:
            raise CharacterError('Escolha um inimigo visível para atacar.')
        sheet, state = self.encounter.player_sheet, self.encounter.states[self.encounter.player_id]
        if (self.encounter.states[target.id].hp == 0
                or (intent.weapon != 'unarmed' and intent.weapon not in sheet.weapons)
                or (intent.weapon == 'javelin' and state.javelins_remaining == 0)):
            raise CharacterError('Atacante, alvo ou arma indisponível.')
        if intent.use_inspiration and not state.heroic_inspiration:
            raise CharacterError('Inspiração Heroica indisponível.')
        if self.encounter.combat and not self.budget.action_available:
            raise ActionError('A ação deste turno já foi utilizada.')
        return target

    def navigation_grid(self) -> Grid:
        """Mapa de navegação atual, incluindo ocupantes do cenário."""
        return self._movement_grid()

    def _movement_grid(self) -> Grid:
        # Guardas Médios hostis e conscientes: não se atravessa o espaço deles.
        return replace(self.grid, blocked=self.grid.blocked | frozenset(c.position for c in self.creatures)
                       | frozenset(o.position for o in self.observers))

    def execute(self, intent: PlayerIntent, *, movement_path: tuple[Position, ...] | None = None,
                include_remainder: bool = True) -> MovementResult | DoorActionResult | RuleResult:
        with log_context(operation_id=new_id()):
            return self._execute_logged(intent, movement_path=movement_path, include_remainder=include_remainder)

    def _execute_logged(self, intent: PlayerIntent, **options) -> MovementResult | DoorActionResult | RuleResult:
        before = self.state
        mode_before = self.mode
        budget_before = self.budget
        resources_before = self.encounter.states.copy()
        started = perf_counter()
        operation = getattr(intent, "operation", "move")
        logger.info("game.operation_started", extra={"data": {"operation": operation,
                    "actor_id": self.encounter.player_id, "target_id": intent.target_id}})
        logger.debug("game.operation_requested", extra={"data": {"intent": intent}})
        try:
            result = self._execute(intent, **options)
            if self.mode != mode_before:
                logger.info("game.mode_changed", extra={"data": {"before": mode_before, "after": self.mode,
                            "operation": operation, "actor_id": self.encounter.player_id}})
            if isinstance(result, DoorActionResult) and not result.changed:
                self.state = before
            if (isinstance(result, MovementResult) and result.cost_meters == 0
                    and not getattr(result, "reactions", ())
                    and result.state.dash_uses == before.dash_uses):
                self.state = before
                result = replace(result, state=before)
            logger.info("game.operation_completed", extra={"data": {"operation": operation,
                        "duration_ms": round((perf_counter() - started) * 1000, 3), "result": result,
                        "status": getattr(result, "status", "blocked" if getattr(result, "stop_reason", None) else "completed"),
                        "movement_before": before, "movement_after": self.state,
                        "budget_before": budget_before, "budget_after": self.budget,
                        "changed_characters": {id: {"before": resources_before[id], "after": state}
                                               for id, state in self.encounter.states.items()
                                               if resources_before[id] != state}}})
            return result
        except (MovementError, ActionError, CharacterError) as error:
            # Uma tentativa inválida não encerra o movimento imediato de um crítico.
            self.state = before
            logger.warning("game.operation_rejected", extra={"data": {"operation": operation,
                           "reason": str(error), "status": "blocked", "movement": before, "budget": self.budget}}, exc_info=True)
            raise
        except Exception:
            logger.exception("game.operation_failed", extra={"data": {"operation": operation}})
            raise

    def _execute(self, intent: PlayerIntent, *, movement_path=None, include_remainder=True) -> MovementResult | DoorActionResult | RuleResult:
        self.validate_preparation(intent)
        if isinstance(intent, ScenarioIntent) and intent.operation == 'sneak':
            if any(getattr(o, 'hostile', False) and self.perception.sees(o, self.state.position) for o in self.perception.observers()):
                raise ActionError('Um inimigo já vê você na área iluminada; furtividade não concede invisibilidade.')
            if self.perception.hidden_total is None:
                self._execute_rule(RuleIntent('hide'))
            return self._execute(MovementIntent((), False, '', intent.target_id), **dict(
                movement_path=movement_path, include_remainder=include_remainder))
        if isinstance(intent, NarrativeIntent):
            self.encounter.require_turn(self.encounter.player_id)
            if intent.operation in {'speak', 'challenge'}:
                self.emit_noise(self.encounter.player_id, self.state.position, intent.volume, 'Fala do jogador.')
            elif intent.operation == 'look':
                self.perceive()
            return RuleResult({"operation": intent.operation, "changed": False, "text": intent.text, "volume": intent.volume,
                               "summary": "Interação recebida, sem alteração mecânica do estado ou posição."})
        if isinstance(intent, RuleIntent):
            if intent.operation not in {"start_combat", "end_turn"}:
                self.encounter.require_turn(self.encounter.player_id)
            self.state = replace(self.state, free_meters=Decimal("0"))
            return self._execute_rule(intent)
        self.encounter.require_turn(self.encounter.player_id)
        if not isinstance(intent, MovementIntent):
            self.state = replace(self.state, free_meters=Decimal("0"))
        if isinstance(intent, DoorIntent):
            return self._operate_door(intent)
        if not isinstance(intent, MovementIntent):
            raise ActionError("Esta sessão não implementa essa interação de cenário.")
        if intent.clarification:
            raise MovementError(intent.clarification)
        turn_based = self.mode == GameMode.TURN_BASED
        dash_requested = intent.dash
        previous_dash_uses = self.state.dash_uses
        if turn_based and dash_requested and not self.budget.action_available:
            intent = replace(intent, dash=False)
        if intent.dash:
            self.state = replace(self.state, free_meters=Decimal("0"))
        grid = self._movement_grid()
        if movement_path is None:
            path, remainder = self.movement_path(intent)
        else:
            path = movement_path
            remainder = next((s.remainder_meters for s in intent.segments if s.remainder_meters), Decimal("0"))
        if not include_remainder:
            remainder = Decimal("0")
        if intent.target_id is not None and not path:
            return MovementResult(self.state, (self.state.position,), Decimal("0"))
        if not path and remainder:
            return MovementResult(self.state, (self.state.position,), Decimal("0"),
                                  "A distância pedida é menor que uma casa de 1,5 m.")
        if not path and not intent.dash:
            if dash_requested:
                return self._explain_stop(MovementResult(self.state, (self.state.position,), Decimal("0")), True)
            raise MovementError("O pedido não contém movimento.")
        result = TravelExecutor(self).run(self.encounter.player_id, grid, self.state, MovementRequest(tuple(path), intent.dash))
        self.state = result.state
        self.last_path = result.path
        if turn_based and intent.dash and result.state.dash_uses > previous_dash_uses:
            self.budget = self.budget.spend_action()
        if remainder and result.stop_reason is None:
            result = replace(result, stop_reason=(
                f"Restaram {format_meters(remainder)} do pedido: a grade só permite casas inteiras de 1,5 m."
            ))
        return self._explain_stop(result, dash_requested and not intent.dash)

    def movement_path(self, intent: MovementIntent) -> tuple[tuple[Position, ...], Decimal]:
        if intent.clarification:
            raise MovementError(intent.clarification)
        if intent.target_id is not None:
            creature = next((c for c in (*self.creatures, *self.observers) if c.id == intent.target_id), None)
            if creature is not None:
                if creature.position not in self.visibility.visible:
                    raise MovementError("O alvo não está visível para se aproximar.")
                opaque = self.scene.opaque if self.scene else self.grid.blocked
                goals = frozenset(
                    Position(creature.position.x + dx, creature.position.y + dy)
                    for dx, dy in DIRECTIONS.values()
                    if line_of_sight(Position(creature.position.x + dx, creature.position.y + dy), creature.position, opaque)
                )
                return path_to_cells(self._movement_grid(), self.state.position, goals), Decimal("0")
            if self.scene is None:
                raise MovementError("Este mapa não tem destinos nomeados.")
            return path_to(self.scene, self.state.position, intent.target_id, self._movement_grid()), Decimal("0")
        position = self.state.position
        path = []
        remainder = Decimal("0")
        for segment in intent.segments:
            dx, dy = DIRECTIONS[segment.direction]
            for _ in range(segment.squares):
                position = Position(position.x + dx, position.y + dy)
                path.append(position)
            if segment.remainder_meters:
                remainder = segment.remainder_meters
                break
        return tuple(path), remainder

    def _execute_rule(self, intent: RuleIntent) -> RuleResult:
        player = self.encounter.player_id
        if intent.operation == 'hide':
            if not self.perception.can_hide():
                raise ActionError('É preciso ocultação/cobertura e estar fora da visão inimiga; furtividade não concede invisibilidade em uma área iluminada e exposta.')
            if self.perception.hidden_total is not None:
                return RuleResult(dict(operation='hide', changed=False, status='already_satisfied', summary='Você já está escondido.'))
            budget = self.budget.spend_action() if self.mode == GameMode.TURN_BASED else self.budget
            state, roll, total = ability_check(self.encounter.player_sheet, self.encounter.states[player],
                                              'stealth', 15, self.encounter.roller,
                                              disadvantage=self.encounter.player_sheet.armor == 'chain_mail')
            self.encounter.states[player] = state
            self.budget = budget
            self.perception.hidden_total = total if total >= 15 else None
            self.perception.revision += 1
            event = dict(operation='hide', actor_id=player, changed=True, dice=list(roll.dice), total=total,
                         dc=15, passed=total >= 15, perceptible=True,
                         advantage=roll.advantage, disadvantage=roll.disadvantage)
            self._events.append(event)
            logger.info('perception.hide_resolved', extra={'data': event})
            return RuleResult(event)
        if intent.operation == "start_combat":
            interlocutor = (self.parley.actor_id if self.parley is not None
                            and self.parley.status in {'pending', 'combat'} else None)
            enemies = tuple(c.id for c in self.creatures
                            if (c.id == interlocutor or (c.hostile and c.position in self.visibility.visible))
                            and self.encounter.states[c.id].hp > 0)
            result = self.encounter.start(enemies)
            self.peaceful_npcs.difference_update(enemies)
            if self.parley is not None and self.parley.actor_id in enemies:
                self.parley = replace(self.parley, status="combat")
            self.state = replace(self.state, spent_meters=Decimal("0"), dash_used=False,
                                 additional_dash_uses=0, free_meters=Decimal("0"))
            return result
        if intent.operation == "end_turn":
            if self.encounter.combat is None:
                return RuleResult({"operation": "end_turn", "changed": False, "summary": "Modo narrado: não há turno para encerrar."})
            self.encounter.require_turn(player)
            return self.next_turn()
        if intent.operation == "second_wind":
            result = self.encounter.use_second_wind(player)
            if self.mode == GameMode.NARRATED:
                self.budget = ActionBudget()
            return result
        if intent.operation == "action_surge":
            if self.mode == GameMode.NARRATED:
                raise CharacterError("Surto de Ação concede uma ação extra por turno; não há turnos no modo narrado.")
            return self.encounter.use_action_surge(player)
        target = self._validate_attack(intent)
        distance = max(abs(target.position.x - self.state.position.x), abs(target.position.y - self.state.position.y))
        if distance > 1:
            raise CharacterError("Aproxime-se a 1,5 m do alvo. Este incremento habilita ataques corpo a corpo.")
        if not line_of_sight(self.state.position, target.position, self.scene.opaque if self.scene else self.grid.blocked):
            raise CharacterError("Há um obstáculo entre você e o alvo.")
        if self.encounter.combat is None:
            started = self._execute_rule(RuleIntent("start_combat"))
            # Iniciativa precede o primeiro ataque. A intenção não concede um golpe gratuito.
            if self.encounter.combat.active_id != player:
                return RuleResult(started.event, "O conflito começou. A iniciativa foi rolada; os NPCs agem antes do Jogador.")
        else:
            started = None
        result = self.encounter.attack(player, target.id, intent.weapon, use_inspiration=intent.use_inspiration)
        if started:
            result = replace(result, event={**result.event, "conflict_started": started.event})
        if result.event["critical_movement_meters"]:
            self.state = replace(self.state, free_meters=self.state.effective_speed_meters / 2)
        if not any(self.encounter.states[e.id].hp > 0 for e in self.encounter.combat.order if e.id != player):
            ended = self.next_turn()
            result = replace(result, event={**result.event, "conflict_ended": ended.event})
        return result

    def _explain_stop(self, result: MovementResult, dash_unavailable: bool) -> MovementResult:
        reason = result.stop_reason
        if result.blocked_position is not None and self.scene is not None:
            passage = next((p for p in self.scene.passages if p.position == result.blocked_position), None)
            if passage is not None and not passage.is_open:
                reason = f"{passage.name} está fechada e impede a passagem."
            obj = next((o for o in self.scene.objects if o.position == result.blocked_position
                        and o.blocks_movement and o.position in self.visibility.visible), None)
            if obj is not None:
                reason = f"{obj.name} impede a passagem."
            creature = next((c for c in self.creatures if c.position == result.blocked_position
                             and c.position in self.visibility.visible), None)
            if creature is not None:
                reason = f"{creature.name} ocupa a próxima casa e impede a passagem."
        if dash_unavailable:
            note = "Dash indisponível: a ação do turno já foi usada; utilizei somente o movimento restante."
            reason = f"{reason} {note}" if reason else note
        return replace(result, stop_reason=reason)

    def _operate_door(self, intent: DoorIntent) -> DoorActionResult:
        if self.scene is None:
            raise ActionError("Este mapa não tem portas ou grades.")
        passage = next((p for p in self.scene.passages if p.id == intent.target_id), None)
        if passage is None:
            raise ActionError("A passagem informada não existe neste mapa.")
        origin, target = self.state.position, passage.position
        adjacent = max(abs(origin.x - target.x), abs(origin.y - target.y)) <= 1
        reachable = adjacent and line_of_sight(origin, target, self.scene.opaque)
        result = operate_door(
            intent.operation, is_open=passage.is_open, locked=passage.locked,
            in_reach=reachable,
            occupied=target == origin or any(c.position == target for c in self.creatures),
            budget=self.budget if self.mode == GameMode.TURN_BASED else ActionBudget(),
        )
        if result.changed:
            self.scene = self.scene.with_passage(intent.target_id, result.is_open)
            self.grid = self.scene.movement_grid
            if self.mode == GameMode.TURN_BASED:
                self.budget = result.budget
            else:
                result = replace(result, budget=self.budget)
            self.emit_noise(self.encounter.player_id, passage.position,
                            'quiet' if self.perception.hidden_total is not None else 'normal',
                            'Uma passagem foi aberta ou fechada.')
        return result

    def next_turn(self) -> RuleResult | None:
        if self.encounter.combat is None:
            return None
        result = self.encounter.advance()
        self.npc_movement.clear()
        self.pending_opportunity = None
        self.suppressed_opportunity = None
        if self.encounter.combat is None or self.encounter.combat.active_id == self.encounter.player_id:
            self.state = self.state.next_turn()
            if self.encounter.combat is None:
                self.budget = ActionBudget()
        else:
            self.state = replace(self.state, free_meters=Decimal("0"))
        penalty = self.encounter.player_sheet.speed_meters - self.encounter.speed(self.encounter.player_id)
        self.state = replace(self.state, speed_reduction_meters=penalty)
        logger.info("game.turn_started", extra={"data": {"combat": self.combat_context(),
                    "event": result.event, "movement": self.state, "budget": self.budget}})
        return result

    def reset(self) -> None:
        self.reset_version += 1
        player, enemies = self._initial_sheets
        self.encounter = Encounter(player, enemies, self._roller)
        self.state = self.initial_state
        self.scene = self.initial_scene
        self.creatures = self.initial_creatures
        self.observers = self.initial_observers
        self.perception = PerceptionSystem(self)
        if self.scene is not None:
            self.grid = self.scene.movement_grid
        self.budget = ActionBudget(action_used=self.initial_state.dash_used)
        self.last_path = ()
        self.npc_movement.clear()
        self.pending_opportunity = None
        self.suppressed_opportunity = None
        self.parley = None
        self.peaceful_npcs.clear()
        self._events = []
        logger.info("game.session_reset", extra={"data": {"position": self.state.position,
                    "resources": self.encounter.states.copy(), "budget": self.budget}})

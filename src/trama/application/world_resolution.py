"""Executa respostas do Mundo usando as mesmas regras de geometria e combate."""

from dataclasses import replace
import logging

from trama.actions import ActionBudget, ActionError, operate_door
from trama.application.modes import GameMode
from trama.application.perception import PerceptionRangeError
from trama.application.routing import path_to_cells
from trama.application.travel import TravelExecutor
from trama.application.failures import action_failure, action_reference, actor_position
from trama.application.session import GameSession
from trama.application.world import WorldAction, WorldError, WorldReaction
from trama.characters import CharacterError
from trama.movement import MovementError, MovementRequest, MovementState
from trama.distances import CELL_METERS
from trama.spatial import Position
from trama.vision import line_of_sight
from trama.observability import log_context, new_id

logger = logging.getLogger(__name__)


class WorldExecutor:
    def __init__(self, session: GameSession):
        self.session = session
        self.remaining_actions = ()
        self.failure = None

    def reaction(self, reaction: WorldReaction) -> tuple[list[dict], str | None]:
        events = []
        if reaction.check:
            check = reaction.check
            self._npc(check.actor_id)
            # Compatibilidade de transporte: a proposta não substitui sentidos/CD reais.
            try:
                resolved = self.session.perception.search(check.actor_id)
            except PerceptionRangeError:
                resolved = dict(found=False, automatic=True, changed=False, perceptible=False)
            passed = resolved['found']
            event = {**resolved, 'actor_id': check.actor_id, 'operation': 'perception_check',
                     'dc': resolved.get('dc'), 'dice': resolved.get('dice', []),
                     'passed': passed, 'reason': check.reason}
            logger.info("world.check_resolved", extra={"data": event})
            events.append(event)
            if not passed:
                return events, None
        for index, action in enumerate(reaction.actions):
            try:
                previous_mode = self.session.mode
                event = self.execute(action)
                events.append(event)
                events.extend(self.session.drain_world_events())
                if action.operation == 'influence':
                    return events, (None if event['accepted'] else 'O NPC recusou este pedido e aguarda sua resposta; a conversa continua sem iniciativa automática.')
                if action.operation == 'start_conflict' or (previous_mode == GameMode.NARRATED
                        and self.session.mode == GameMode.TURN_BASED):
                    return events, 'O conflito começou; a iniciativa determina quem age agora.'
                if event.get("stop_reason"):
                    self.failure = replace(self.failure, skipped_actions=tuple(
                        action_reference(a, action.actor_id) for a in reaction.actions[index + 1:]))
                    if self.session.pending_opportunity:
                        self.remaining_actions = reaction.actions[index:]
                    logger.info("world.reaction_interrupted", extra={"data": {
                        "actor_id": action.actor_id, "operation": action.operation,
                        "reason": event["stop_reason"],
                        "unperformed_actions": len(reaction.actions) - index - 1,
                    }})
                    return events, "Resposta do Mundo interrompida: " + event["stop_reason"]
            except (WorldError, CharacterError, ActionError, MovementError) as error:
                # Uma resposta parcialmente aplicada deve continuar íntegra no relatório.
                self.failure = replace(self.failure, skipped_actions=tuple(
                    action_reference(a, action.actor_id) for a in reaction.actions[index + 1:]))
                return events, "Resposta do Mundo interrompida: " + str(error)
        reason = reaction.reason if reaction.interrupt else None
        if reason:
            logger.info("world.player_interrupted", extra={"data": {"reason": reason, "position": self.session.state.position}})
        return events, reason

    def _npc(self, actor_id):
        npc = next((c for c in self.session.creatures if c.id == actor_id), None)
        if npc is None:
            npc = next((o for o in self.session.observers if o.id == actor_id), None)
        if npc is None or (actor_id in self.session.encounter.states and self.session.encounter.states[actor_id].hp == 0):
            raise WorldError("A resposta do Mundo exige um NPC existente e com PV.")
        if self.session.perception.sleeping(npc):
            raise WorldError('Um NPC dormindo não pode falar ou agir conscientemente.')
        return npc

    def execute(self, action: WorldAction) -> dict:
        with log_context(operation_id=new_id()):
            self.failure = None
            origin = actor_position(self.session, action.actor_id)
            logger.info("world.action_started", extra={"data": {"actor_id": action.actor_id,
                        "operation": action.operation, "action": action}})
            try:
                mode_before = self.session.mode
                event = self._execute(action)
            except Exception as error:
                self.failure = action_failure(self.session, action, str(error), origin=origin,
                                              code=getattr(error, "code", "invalid_action"),
                                              blocked_position=getattr(error, "position", None))
                logger.exception("world.action_rejected", extra={"data": {"action": action, "failure": self.failure.context()}})
                raise
            if action.operation == 'move' and event.get('stop_code') == 'insufficient_movement':
                # O destino pode estar além do orçamento. O NPC percorreu somente
                # o trecho legal e ainda pode executar outras ações do plano.
                event = {**event, 'status': 'movement_limited',
                         'movement_limit_reason': event['stop_reason'], 'stop_reason': None}
            if event.get("stop_reason"):
                blocked = event.get("blocked_position")
                self.failure = action_failure(self.session, action, event["stop_reason"], origin=origin,
                                              code=event.get("stop_code") or "movement_interrupted",
                                              blocked_position=Position(blocked[0] - 1, blocked[1] - 1) if blocked else None)
            logger.info("world.action_completed", extra={"data": event})
            if self.session.mode != mode_before:
                logger.info("game.mode_changed", extra={"data": {"before": mode_before, "after": self.session.mode,
                            "reason": action.text, "actor_id": action.actor_id}})
            return event

    def _execute(self, action):
        session = self.session
        encounter = session.encounter
        npc = self._npc(action.actor_id) if action.actor_id != "world" else None
        event = {"actor_id": action.actor_id, "operation": action.operation,
                 "text": action.text, "changed": False, "perceptible": npc is None or npc.position in session.visibility.visible}
        if action.operation == "describe":
            return event
        if npc is None:
            raise WorldError("Essa operação exige um NPC; o Mundo não pode controlar o Jogador.")
        if action.operation == 'search':
            if action.target_id != encounter.player_id:
                raise WorldError('Este recorte de Search procura o jogador oculto.')
            return session.perception.search(npc.id)
        if action.operation == 'parley':
            return {**session.offer_parley(npc.id, action.text),
                    'stop_reason': 'O NPC exige uma resposta. Você pode conversar antes do combate.',
                    'stop_code': 'parley_pending'}
        if action.operation == 'influence':
            # Gravações antigas às vezes repetem referências privadas em
            # memory_ids. Validá-las não transforma o raciocínio em fala.
            for id in action.memory_ids:
                try:
                    memory = session.knowledge.store.get(npc.id, id)
                except ValueError as error:
                    raise WorldError(str(error)) from error
                if (action.influence.assessment is None or memory.claim not in
                        {e.claim for e in action.influence.assessment.memory_effects}):
                    raise WorldError('Referência privada de Influence não fundamentada na avaliação.')
            resolved = session.resolve_influence(npc.id, action.influence, action.text)
            if action.memory_ids:
                resolved['private_memory_ids'] = list(action.memory_ids)
            return resolved
        if session.parley_pending and action.operation in {'move', 'open', 'close', 'attack'}:
            raise WorldError('O NPC deve aguardar a resposta à abordagem antes de se aproximar ou atacar.')
        if npc.id not in encounter.sheets and action.operation != 'say':
            raise WorldError('Um NPC sem ficha de combate pode perceber, buscar e falar; não recebe ações de Guerreiro.')
        if action.operation == "say":
            communication = session.knowledge.communicate(npc.id, action.text, npc.position,
                                                           action.volume, memory_ids=action.memory_ids)
            session.emit_noise(npc.id, npc.position, action.volume, 'Fala de um NPC.', speech=True)
            # A fala é um acontecimento audível decidido pelo Mundo, não visão através de paredes.
            return {**event, **communication, "perceptible": encounter.player_id in communication['heard_by'],
                    'changed': bool(communication['learned_memory_ids']),
                    "speaker": npc.name, "volume": action.volume}
        if action.operation == "end_conflict":
            if encounter.combat is None:
                raise WorldError("Não há conflito para encerrar.")
            encounter.combat = None
            encounter.budgets = {id: ActionBudget() for id in encounter.sheets}
            session.state = replace(session.state, spent_meters=0, dash_used=False, additional_dash_uses=0,
                                    free_meters=0, speed_reduction_meters=0)
            session.npc_movement.clear()
            if session.parley is not None:
                session.parley = replace(session.parley, status="peaceful")
                session.peaceful_npcs.add(session.parley.actor_id)
            return {**event, "changed": True, "perceptible": True}
        if action.operation == "start_conflict":
            if encounter.combat is not None:
                return event
            result = encounter.start(tuple(c.id for c in session.creatures if (c.hostile or c.id == action.actor_id) and encounter.states[c.id].hp > 0))
            session.peaceful_npcs.difference_update(e.id for e in encounter.combat.order)
            if session.parley is not None and any(e.id == session.parley.actor_id for e in encounter.combat.order):
                session.parley = replace(session.parley, status="combat")
            session.state = replace(session.state, spent_meters=0, dash_used=False, additional_dash_uses=0, free_meters=0)
            return {**event, **result.event, "operation": "start_conflict", "perceptible": True}
        encounter.require_turn(npc.id)
        if action.operation == "wait":
            return {**event, "changed": False}
        if action.operation == "move":
            # A IA escolhe o destino; a geometria encontra o trajeto e valida cada passo.
            destination = action.destination
            occupied = {session.state.position} | {c.position for c in session.creatures if c.id != npc.id} | {o.position for o in session.observers}
            blocked = session.grid.blocked | occupied
            grid = replace(session.grid, blocked=frozenset(blocked))
            goals = frozenset({destination})
            try:
                path = path_to_cells(grid, npc.position, goals)
            except MovementError:
                if session.scene is None:
                    raise
                # Sem caminho livre, permite aproximar-se da porta fechada;
                # a execução real ainda para nela. Ocupantes nunca são removidos.
                architectural = session.scene.open_passages_grid
                planned = replace(architectural, blocked=frozenset(architectural.blocked | occupied))
                path = path_to_cells(planned, npc.position, goals)
            if not path:
                return event
            state = session.npc_movement.get(npc.id, MovementState(
                npc.position, encounter.sheets[npc.id].speed_meters,
                speed_reduction_meters=encounter.sheets[npc.id].speed_meters - encounter.speed(npc.id)))
            result = TravelExecutor(session).run(npc.id, grid, state, MovementRequest(path))
            session.npc_movement[npc.id] = result.state
            session.creatures = tuple(replace(c, position=result.state.position) if c.id == npc.id else c for c in session.creatures)
            return {**event, "changed": len(result.path) > 1,
                    "from": [npc.position.x + 1, npc.position.y + 1],
                    "to": [result.state.position.x + 1, result.state.position.y + 1],
                    "traveled_meters": float((len(result.path) - 1) * CELL_METERS),
                    "cost_meters": float(result.cost_meters),
                    "stop_reason": result.stop_reason,
                    "stop_code": result.stop_code,
                    "blocked_position": ([result.blocked_position.x + 1, result.blocked_position.y + 1]
                                         if result.blocked_position else None),
                    "reactions": list(getattr(result, "reactions", ())),
                    "perceptible": event["perceptible"] or result.state.position in session.visibility.visible}
        if action.operation in {"open", "close"}:
            passage = next((p for p in session.scene.passages if p.id == action.target_id), None) if session.scene else None
            if passage is None:
                raise WorldError("A passagem não existe.")
            reachable = max(abs(npc.position.x - passage.position.x), abs(npc.position.y - passage.position.y)) <= 1
            result = operate_door(action.operation, is_open=passage.is_open, locked=passage.locked,
                                  in_reach=reachable and line_of_sight(npc.position, passage.position, session.scene.opaque),
                                  occupied=passage.position == session.state.position or any(c.position == passage.position for c in session.creatures),
                                  budget=encounter.budgets[npc.id] if encounter.combat else ActionBudget())
            if result.changed:
                session.scene = session.scene.with_passage(passage.id, result.is_open)
                session.grid = session.scene.movement_grid
                session.knowledge.observe_scene()
                if encounter.combat:
                    encounter.budgets[npc.id] = result.budget
                else:
                    session.perceive()
                    session.observe_npc(npc.id)
                    if session.parley_pending:
                        return {**event, 'changed': True, 'target': passage.name, 'is_open': result.is_open,
                                'status': result.status, 'perceptible': True,
                                'stop_reason': 'O NPC exige uma resposta antes de continuar.', 'stop_code': 'parley_pending'}
            return {**event, "changed": result.changed, "target": passage.name, "is_open": result.is_open, "status": result.status,
                    "perceptible": passage.position in session.visibility.visible}
        if action.operation == "attack":
            if action.target_id != encounter.player_id:
                raise WorldError("Neste cenário, ataques de NPC só têm o Jogador como alvo.")
            if max(abs(npc.position.x - session.state.position.x), abs(npc.position.y - session.state.position.y)) > 1:
                raise WorldError("NPC fora de alcance para atacar.")
            if not line_of_sight(npc.position, session.state.position, session.scene.opaque if session.scene else session.grid.blocked):
                raise WorldError("Obstáculo entre NPC e Jogador.")
            if encounter.combat is None:
                raise WorldError("Inicie o conflito e respeite a iniciativa antes de atacar.")
            result = encounter.attack(npc.id, encounter.player_id, action.weapon)
            session.state = replace(session.state, speed_reduction_meters=encounter.player_sheet.speed_meters - encounter.speed(encounter.player_id))
            return {**event, **result.event, "perceptible": True}
        raise WorldError("Operação do Mundo não implementada.")

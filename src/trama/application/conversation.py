"""Coordena diálogo, execução e fatos para o narrador. Não faz chamadas de rede."""

from dataclasses import asdict, dataclass, field, replace
from collections.abc import Iterable
from copy import deepcopy
import json
import logging

from trama.actions import ActionError, DoorActionResult
from trama.application.dialogue import DialogueMessage, Speech, split_speech
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, NarrativeIntent, RuleIntent
from trama.application.session import GameSession
from trama.distances import CELL_METERS
from trama.movement import MovementError, MovementResult
from trama.characters import CharacterError
from trama.application.encounter import RuleResult
from trama.application.world import WorldPlan, WorldError
from trama.application.world_resolution import WorldExecutor
from trama.application.modes import GameMode
from trama.application.authorization import PlanAuthorizationError, validate_player_plan
from trama.application.interpretation_context import compact_context
from trama.application.context_contracts import AIContext, ContextKind
from trama.application.failures import ExecutionFailure, action_failure, action_reference
from trama.application.preparation import prepare_movement
from trama.observability import new_id

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionReport:
    events: tuple[dict, ...] = ()
    progress: bool = False
    stop_reason: str | None = None
    unperformed_steps: int = 0
    world_events: tuple[dict, ...] = ()
    narrative_interaction: bool = False
    narrative_details: tuple[str, ...] = ()
    questions: tuple[str, ...] = ()
    failures: tuple[ExecutionFailure, ...] = field(default=(), kw_only=True)
    execution_id: str | None = field(default=None, kw_only=True)

    @property
    def status(self) -> str:
        if self.stop_reason:
            return "blocked"
        if self.events and all(e.get("status") == "already_satisfied" for e in self.events) and not self.world_events:
            return "already_satisfied"
        return "completed"

    def context(self) -> dict:
        return {"status": self.status, "events": list(self.events), "progress": self.progress,
                "narrative_interaction": self.narrative_interaction,
                "stop_reason": self.stop_reason, "unperformed_steps": self.unperformed_steps,
                "reactions": list(self.world_events), "narrative_details": list(self.narrative_details),
                "questions": list(self.questions), "failures": [f.context() for f in self.failures],
                "execution_id": self.execution_id}

    def merge(self, other: "ExecutionReport") -> "ExecutionReport":
        reasons = "\n".join(dict.fromkeys(r for r in (self.stop_reason, other.stop_reason) if r)) or None
        return ExecutionReport(self.events + other.events, self.progress or other.progress,
                               reasons, self.unperformed_steps + other.unperformed_steps,
                               self.world_events + other.world_events,
                               self.narrative_interaction or other.narrative_interaction,
                               self.narrative_details + other.narrative_details, self.questions + other.questions,
                               failures=self.failures + other.failures,
                               execution_id=other.execution_id or self.execution_id)


class Conversation:
    def __init__(self, session: GameSession) -> None:
        self.session = session
        self.messages: list[DialogueMessage] = []
        self.pending_npc_turn: WorldPlan | None = None
        self._last_execution = None
        self._preceding_execution = None
        self._reset_version = session.reset_version

    def extend_history(self, messages: Iterable[DialogueMessage]) -> None:
        """Acrescenta falas validadas, sem executar ações ou substituir a memória mecânica.

        Usado tanto por mensagens novas quanto por um histórico registrado. O lote
        inteiro é validado antes da inclusão; papéis e canais são preservados.
        """
        validated = []
        for message in messages:
            if not isinstance(message, DialogueMessage):
                raise ValueError('Use DialogueMessage para acrescentar histórico.')
            validated.append(DialogueMessage(message.role, message.speech))
        self.messages.extend(validated)
        logger.debug('conversation.history_appended', extra={'data': {
            'count': len(validated), 'roles': [m.role for m in validated]}})

    def _sync_reset(self) -> None:
        if self._reset_version != self.session.reset_version:
            self._last_execution = self._preceding_execution = None
            self.pending_npc_turn = None
            self._reset_version = self.session.reset_version

    def _remember(self, report: ExecutionReport, actor_id: str) -> ExecutionReport:
        self._sync_reset()
        report = replace(report, execution_id=new_id())
        self._preceding_execution = self._last_execution
        combat = self.session.combat_context()
        self._last_execution = deepcopy({
            "execution_id": report.execution_id, "actor_id": actor_id,
            "actor_name": self.session.encounter.sheets[actor_id].name,
            "execution": self._execution_context(report),
            "situation": {"mode": self.session.mode.value, "combat": combat,
                          "player_position": [self.session.state.position.x + 1, self.session.state.position.y + 1],
                          "turn_pending": bool(report.stop_reason and combat)},
        })
        logger.info("conversation.execution_recorded", extra={"data": {
            "execution_id": report.execution_id, "actor_id": actor_id,
            "failure_count": len(report.failures), "stop_reason": report.stop_reason,
            "failures": [f.context() for f in report.failures],
            "situation": self._last_execution["situation"]}})
        return report

    def _execution_context(self, report: ExecutionReport) -> dict:
        execution = report.context()
        moves = [e for e in report.events if e["operation"] == "move"]
        traveled = sum(e["traveled_meters"] for e in moves)
        position = [self.session.state.position.x + 1, self.session.state.position.y + 1]
        execution["player_movement"] = {
            "occurred": traveled > 0, "traveled_meters": traveled,
            "from": moves[0]["from"] if moves else position,
            "to": moves[-1]["to"] if moves else position,
        }
        return execution

    def prepare(self, raw: str) -> Speech:
        logger.debug("conversation.player_message", extra={"data": {"text": raw}})
        if not raw.strip() or len(raw) > 2000:
            raise ValueError("Digite uma mensagem com 1 a 2000 caracteres.")
        speech = split_speech(raw)
        if not speech.on and not speech.off:
            raise ValueError("A mensagem está vazia.")
        self.extend_history((DialogueMessage("player", speech),))
        logger.info("conversation.message_accepted", extra={"data": {"text": raw, "speaker": "player",
                    "has_on": bool(speech.on), "has_off": bool(speech.off)}})
        logger.debug("conversation.speech_split", extra={"data": {"speech": speech}})
        return speech

    def interpretation_context(self) -> AIContext:
        return AIContext(ContextKind.INTERPRETATION, compact_context(self._full_context()))

    def _full_context(self) -> dict:
        context = self.session.interpreter_context()
        # Perguntas/comandos em off, inclusive no histórico, não entram na interpretação.
        context["recent_messages"] = [{"role": m.role, "on": m.speech.on}
                                      for m in self.messages[-12:] if m.speech.on]
        return context

    def world_context(self, plan: ActionPlan | None = None) -> AIContext:
        context = self._full_context()
        steps = []
        for intent in plan.steps if plan else ():
            step = asdict(intent)
            step.setdefault("operation", "move")
            if isinstance(intent, MovementIntent):
                try:
                    path, _ = self.session.movement_path(intent)
                    step["proposed_path"] = [[p.x + 1, p.y + 1] for p in path]
                except MovementError as error:
                    step["invalid_reason"] = str(error)
            requirement = self.session.spatial_requirement(intent)
            if requirement:
                step['spatial_requirement'] = requirement.context()
            if hasattr(intent, 'allow_approach'):
                step['preparation'] = []
                if requirement:
                    if isinstance(intent, RuleIntent) and intent.operation == 'attack' and self.session.encounter.combat is None:
                        step['initiative_before_movement'] = True
                    try:
                        approach = prepare_movement(self.session, intent, requirement)
                        if approach:
                            step['preparation'].append({**asdict(approach.intent), 'operation': 'move',
                                'proposed_path': [[p.x + 1, p.y + 1] for p in approach.path]})
                    except MovementError as error:
                        step['invalid_reason'] = str(error)
            steps.append(step)
        context["player_plan"] = json.loads(json.dumps(steps, default=float))
        context["player_request_parts"] = [asdict(p) for p in plan.request_parts] if plan else []
        context["phase"] = "player_action" if plan else "npc_turn"
        return AIContext(ContextKind.WORLD_ACTION if plan else ContextKind.NPC_TURN, context)

    def execute(self, plan: ActionPlan, world: WorldPlan = WorldPlan(), *, player_prompt: str | None = None) -> ExecutionReport:
        self._sync_reset()
        if player_prompt is None and self.messages and self.messages[-1].role == "player":
            player_prompt = self.messages[-1].speech.on
            if not player_prompt:
                raise PlanAuthorizationError("Uma mensagem exclusivamente em off não autoriza ações de jogo.")
        if player_prompt is not None:
            validate_player_plan(player_prompt, plan, self.interpretation_context(), stage="pre_execution")
        logger.info("conversation.plan_started", extra={"data": {"step_count": len(plan.steps)}})
        events = []
        progress = False
        narrative_interaction = False
        reason = None
        attempted = 0
        world_events = []
        failures = []
        executor = WorldExecutor(self.session)
        if any(r.step_index >= len(plan.steps) for r in world.reactions):
            raise WorldError("Resposta do Mundo aponta para uma etapa inexistente.")
        def record(chunk, preparation_for=None):
            nonlocal progress, narrative_interaction, reason
            events.extend(({**e, "preparation_for": preparation_for} if preparation_for else e) for e in chunk.events)
            world_events.extend(chunk.world_events)
            failures.extend(chunk.failures)
            progress |= chunk.progress
            narrative_interaction |= chunk.narrative_interaction
            reason = chunk.stop_reason

        for index, intent in enumerate(plan.steps):
            attempted += 1
            origin = self.session.state.position
            try:
                reactions = [r for r in world.reactions if r.step_index == index]
                if any(r.after_squares not in (None, 0) for r in reactions) and not isinstance(intent, MovementIntent) and not hasattr(intent, "allow_approach"):
                    raise WorldError("Esta etapa não possui percurso para pontos de resposta do Mundo.")
                def react(checkpoint):
                    for reaction in reactions:
                        if reaction.after_squares != checkpoint:
                            continue
                        old_mode = self.session.mode
                        responses, interruption = executor.reaction(reaction)
                        world_events.extend({**event, "step_index": index, "after_squares": checkpoint} for event in responses)
                        if executor.failure:
                            failure = executor.failure
                            if checkpoint == 0:
                                failure = replace(failure, skipped_actions=failure.skipped_actions + (
                                    action_reference(intent, self.session.encounter.player_id),))
                            failures.append(failure)
                        if interruption:
                            return interruption
                        if old_mode != self.session.mode:
                            return "O Mundo alterou a situação de conflito; a ação para para respeitar o novo modo."
                    return None
                reason = react(0)
                if reason:
                    break
                self.session.validate_preparation(intent)
                requirement = self.session.spatial_requirement(intent)
                reference = {"operation": getattr(intent, 'operation', 'move'), "target_id": intent.target_id, "step_index": index}
                if (requirement and getattr(intent, 'allow_approach', True)
                        and isinstance(intent, RuleIntent) and intent.operation == 'attack'
                        and self.session.encounter.combat is None):
                    # Iniciativa antes de qualquer deslocamento tático, sem caminhada
                    # ilimitada de exploração como preparação gratuita de um ataque.
                    record(self._execute_one(RuleIntent('start_combat')), reference)
                    if self.session.encounter.combat.active_id != self.session.encounter.player_id:
                        reason = 'O conflito começou. A iniciativa foi rolada; os NPCs agem antes do Jogador.'
                        failures.append(action_failure(self.session, intent, reason, origin=origin, code='initiative_order'))
                        events.append({'operation': intent.operation, 'target_id': intent.target_id,
                                       'status': 'blocked', 'changed': False, 'preparation_incomplete': True})
                        break
                    requirement = self.session.spatial_requirement(intent)
                approach = prepare_movement(self.session, intent, requirement)
                if approach:
                    logger.info("game.interaction_prepared", extra={"data": {"interaction": reference,
                        "spatial_requirement": requirement.context(), "approach": approach.intent, "path": approach.path}})
                    self._execute_walk(approach.intent, reactions, react,
                                       lambda chunk: record(chunk, reference), path=approach.path)
                    if reason:
                        events.append({"operation": intent.operation, "target_id": intent.target_id,
                                       "changed": False, "status": "blocked", "reason": reason,
                                       "preparation_incomplete": True})
                        if failures:
                            pending = action_reference(intent, self.session.encounter.player_id)
                            failures[-1] = replace(failures[-1], skipped_actions=failures[-1].skipped_actions + (pending,))
                        break
                    origin = self.session.state.position
                    self.session.validate_preparation(intent)
                if isinstance(intent, MovementIntent):
                    self._execute_walk(intent, reactions, react, record)
                else:
                    record(self._execute_one(intent))
                if reason:
                    break
                reason = react(None)
                if reason:
                    break
            except (MovementError, ActionError, CharacterError, WorldError) as error:
                world_events.extend(self.session.drain_world_events())
                reason = str(error)
                failures.append(action_failure(self.session, intent, reason, origin=origin,
                                               code=getattr(error, "code", "invalid_action"),
                                               blocked_position=getattr(error, "position", None)))
                break
        if failures:
            skipped = tuple(action_reference(s, self.session.encounter.player_id) for s in plan.steps[attempted:])
            failures[-1] = replace(failures[-1], skipped_actions=failures[-1].skipped_actions + skipped)
        report = ExecutionReport(tuple(events), progress, reason, len(plan.steps) - attempted,
                                 tuple(world_events), narrative_interaction,
                                 tuple(p.text for p in plan.request_parts if p.kind == "narrative_detail"),
                                 tuple(p.text for p in plan.request_parts if p.kind == "question"), failures=tuple(failures))
        if plan.steps:
            report = self._remember(report, self.session.encounter.player_id)
        logger.info("conversation.plan_completed", extra={"data": {"report": report, "status": report.status}})
        return report

    def _execute_walk(self, intent, reactions, react, record, *, path=None):
        """Mesmo percurso para movimento solicitado e aproximação preparada.

        Cada trecho é registrado imediatamente: uma falha posterior preserva os
        efeitos já aplicados. Checkpoints contam casas realmente percorridas.
        """
        if not any(r.after_squares for r in reactions):
            record(self._execute_one(intent, movement_path=path) if path is not None else self._execute_one(intent))
            return
        if path is None:
            path, _ = self.session.movement_path(intent)
        points = sorted({r.after_squares for r in reactions if r.after_squares and r.after_squares <= len(path)} | {len(path)})
        offset = 0
        traversed = [self.session.state.position]
        try:
            if not path:
                record(self._execute_one(intent))
            for end in points:
                if end == offset:
                    continue
                chunk_intent = intent if offset == 0 else replace(intent, dash=False)
                chunk = self._execute_one(chunk_intent, movement_path=path[offset:end], include_remainder=end == len(path))
                traversed.extend(self.session.last_path[1:])
                record(chunk)
                interruption = None
                if len(self.session.last_path) - 1 == end - offset:
                    interruption = react(end)
                    if interruption:
                        reason = "\n".join(r for r in (chunk.stop_reason, interruption) if r)
                        record(ExecutionReport(stop_reason=reason))
                if chunk.stop_reason or interruption:
                    break
                offset = end
        finally:
            self.session.last_path = tuple(traversed)

    def _execute_one(self, intent, **options) -> ExecutionReport:
        before = self.session.state
        budget_before = self.session.budget
        previous_mode = self.session.mode
        result = self.session.execute(intent, **options)
        scenario_events = self.session.drain_world_events()
        mode_stop = ("O conflito começou; a iniciativa determina quem age agora."
                     if previous_mode == GameMode.NARRATED and self.session.mode == GameMode.TURN_BASED
                     and any(e['operation'] == 'start_conflict' for e in scenario_events) else None)
        if isinstance(result, MovementResult):
            changed = before != result.state or self.session.budget != budget_before
            event = {"operation": "move", "changed": changed,
                           "status": "blocked" if result.stop_reason else ("completed" if changed else "already_satisfied"),
                           "from": [before.position.x + 1, before.position.y + 1],
                           "to": [result.state.position.x + 1, result.state.position.y + 1],
                           "traveled_meters": float((len(result.path) - 1) * CELL_METERS),
                           "cost_meters": float(result.cost_meters),
                           "protected_meters": float(result.protected_meters),
                           "dash": result.state.dash_used and not before.dash_used}
            failures = ()
            if result.stop_reason:
                failures = (action_failure(self.session, intent, result.stop_reason, origin=before.position,
                                           code=result.stop_code or "movement_interrupted",
                                           blocked_position=result.blocked_position),)
            return ExecutionReport((event,), changed, result.stop_reason,
                                   world_events=getattr(result, "reactions", ()) + scenario_events, failures=failures)
        elif isinstance(result, DoorActionResult):
            assert isinstance(intent, DoorIntent)
            passage = next(p for p in self.session.scene.passages if p.id == intent.target_id)
            return ExecutionReport(({"operation": intent.operation, "changed": result.changed,
                                     "target": passage.name, "target_id": passage.id, "is_open": result.is_open, "status": result.status},), result.changed, mode_stop,
                                   world_events=scenario_events)
        elif isinstance(result, RuleResult):
            event = {**result.event, "status": "blocked" if result.stop_reason or mode_stop else result.event.get("status", "completed")}
            return ExecutionReport((event,), result.event["changed"], result.stop_reason or mode_stop,
                                   narrative_interaction=isinstance(intent, NarrativeIntent), world_events=scenario_events)

    def execute_npc_turn(self, world: WorldPlan) -> ExecutionReport:
        self._sync_reset()
        combat = self.session.encounter.combat
        if combat is None or combat.active_id == self.session.encounter.player_id:
            raise WorldError("Não há turno de NPC para resolver.")
        active = combat.active_id
        if any(r.step_index != 0 or r.after_squares != 0 or r.interrupt or
               any(a.actor_id != active for a in r.actions) for r in world.reactions):
            raise WorldError("A decisão deve resolver apenas o NPC ativo, antes da etapa 0, sem interromper o Jogador.")
        events = []
        failures = []
        self.pending_npc_turn = None

        def finish(reason=None):
            return self._remember(ExecutionReport(stop_reason=reason, world_events=tuple(events),
                                                  failures=tuple(failures)), active)

        try:
            for index, reaction in enumerate(world.reactions):
                if self.session.encounter.states[active].hp == 0:
                    break
                executor = WorldExecutor(self.session)
                result, interruption = executor.reaction(reaction)
                events.extend(result)
                if executor.failure:
                    skipped = tuple(action_reference(a, active) for r in world.reactions[index + 1:] for a in r.actions)
                    failures.append(replace(executor.failure, skipped_actions=executor.failure.skipped_actions + skipped))
                if self.session.pending_opportunity:
                    self.pending_npc_turn = WorldPlan((replace(reaction, actions=executor.remaining_actions, check=None),
                                                       *world.reactions[index + 1:]))
                    return finish(interruption)
                if self.session.encounter.states[active].hp == 0:
                    break
                if interruption:
                    return finish(interruption)
            if self.session.encounter.combat:
                events.append({**self.session.next_turn().event, "actor_id": active, "perceptible": True})
        except (MovementError, ActionError, CharacterError, WorldError) as error:
            return finish(str(error))
        return finish()

    def narration_context(
        self, speech: Speech = Speech(), report: ExecutionReport = ExecutionReport(),
        *, initial: bool = False,
    ) -> AIContext:
        context = self.session.interpreter_context()
        self._sync_reset()
        # O narrador descreve a percepção atual, não o mapa arquitetônico inteiro.
        visible = self.session.visibility.visible
        scene = self.session.scene
        area = scene.area_at(self.session.state.position) if scene else None
        perception = {
            "current_place": area.name if area else "passagem",
            "current_description": area.description if area else "",
            "visible_places": ([{"name": a.name, "description": a.description}
                                for a in scene.areas if a.cells & visible] if scene else []),
            "visible_passages": ([p for p in context["map"]["scene"]["passages"] if p["visible"]]
                                 if scene else []),
            "visible_creatures": context["visible_creatures"],
            "visible_enemies": context["visible_enemies"],
            "visible_objects": [o for o in context.get("visible_objects", []) if o.get("visible", True) or o.get("carried")],
            "visible_scene_objects": ([o for o in context["map"]["scene"].get("objects", []) if o["visible"]]
                                      if scene else []),
            "scenario": context.get("scenario"),
        }
        execution = self._execution_context(report)
        previous = self._last_execution
        if previous and report.execution_id == previous["execution_id"]:
            previous = self._preceding_execution
        result = {
            "phase": "initial" if initial else "reply",
            "allow_on": initial or report.progress or report.narrative_interaction or report.status == "already_satisfied" or any(e.get("perceptible") for e in report.world_events),
            "player": {"on": speech.on, "off": speech.off},
            "execution": execution, "previous_execution": deepcopy(previous), "perception": perception,
            "character": context["character"],
            "player_sheet": context["player_sheet"], "combat": context["combat"],
            "mode": context["mode"], "world": context["world"],
            "history": [{"role": m.role, "on": m.speech.on, "off": m.speech.off}
                        for m in self.messages[-12:]],
            "verified_rules": [
                "PHB 2024: movimento em casas de 1,5 m; terreno difícil custa 3 m por casa.",
                "Em modo por turnos, PHB 2024, Dash: usa a ação para adicionar movimento igual à velocidade no turno.",
                "Em modo por turnos, PHB 2024, objetos/Utilize: primeira interação gratuita; seguinte usa a ação.",
                "PHB 2024, visão: Humano sem visão no escuro; paredes/portas fechadas bloqueiam.",
                "O Mundo decide respostas dos guardas; só narre como realizados os efeitos validados em execution.reactions.",
                "PHB 2024, Guerreiro 1–3: Defesa +1 CA com armadura. Retomar o Fôlego: ação bônus, cura 1d10+nível, 2 usos; descanso curto recupera 1 e longo recupera todos.",
                "Guerreiro 2: Surto de Ação concede uma ação extra, exceto Magia; um uso por descanso curto/longo. Novo turno não recupera usos da classe.",
                "Mente Tática: +1d10 a teste de atributo falho; gasta Retomar o Fôlego somente se o teste passar. Não serve para ataques ou salvaguardas.",
                "Campeão 3: críticos com 19–20, vantagem na iniciativa e em Atletismo; após crítico, movimento imediato até metade do deslocamento sem provocar ataques de oportunidade.",
                "Humano: Resourceful concede Inspiração Heroica após descanso longo; Skillful dá uma perícia; Versatile concede Skilled, com três perícias na ficha.",
                "Inspiração Heroica: rerrola um dado imediatamente após rolá-lo e mantém o novo resultado mesmo pior. Com vantagem/desvantagem, rerrola somente um dos dados.",
                "Soldado concede Savage Attacker: uma vez por turno, rola duas vezes os dados de dano da arma e escolhe uma rolagem. A POC escolhe a maior automaticamente.",
                "Maestrias escolhidas: Graze causa modificador de atributo no erro; Sap dá desvantagem no próximo ataque do alvo; Slow reduz sua velocidade em 3 m sem acumular. Sap/Slow terminam no início do próximo turno da fonte.",
                "Descanso curto pode gastar Dados de Vida (d10+CON) para curar; longo recupera PV, todos os Dados de Vida e recursos. Essas APIs e Mente Tática ainda não têm comandos na janela.",
                "Ataques de oportunidade: uma reação para um ataque corpo a corpo antes de uma criatura visível sair do alcance de 1,5 m. Entrar no alcance ou circular dentro dele não provoca. A reação retorna no início do próximo turno do atacante.",
                "Os guardas usam oportunidades disponíveis. O Jogador confirma cada oportunidade antes de atacar, salvo autorização de uso automático. O movimento pausa para essa escolha e depois prossegue do ponto validado.",
                "Movimento imediato protegido após crítico de Campeão não provoca oportunidade. Desengajar, teleporte e movimento forçado ainda não têm comandos. Ataques atuais são corpo a corpo; testes de morte e cobertura completa ainda não estão implementados.",
                "Modo narrado não cobra orçamento por turno; modo por turnos usa iniciativa e recursos do PHB 2024.",
                "Decisão do usuário: executar o possível, parar no impedimento e explicar em off.",
                "Movimento contextual do Jogador: requisitos espaciais podem gerar aproximação antes da ação, salvo proibição de movimento. Iniciativa precede a aproximação tática de ataque; não concede movimento ou golpes gratuitos.",
                "POC: casas inteiras; uma fração restante não é executada nem arredondada para cima.",
            ],
        }
        kind = (ContextKind.NARRATION_INITIAL if initial else ContextKind.NARRATION_OFF
                if speech.off and not speech.on else ContextKind.NARRATION_RESULT)
        return AIContext(kind, result)

    def finish(self, reply: Speech, context: dict) -> Speech:
        on = reply.on if context["allow_on"] else ""
        off = reply.off
        reason = context["execution"]["stop_reason"]
        if reason:
            character = context["character"]
            place = context["perception"]["current_place"]
            where = f"{place} (coluna {character['column']}, linha {character['row']})"
            explanation = (f"Parei em {where}. " if context["execution"]["progress"]
                           else f"Não foi possível realizar a ação em {where}. ") + reason
            if context["execution"]["unperformed_steps"]:
                explanation += " As etapas seguintes não foram executadas."
            if explanation not in off:
                off = "\n".join(p for p in (off, explanation) if p)
        if not on and not off:
            off = "Nenhuma ação foi realizada."
        final = Speech(on, off)
        self.extend_history((DialogueMessage("narrator", final),))
        logger.info("conversation.reply_delivered", extra={"data": {"text": final.text, "speaker": "narrator",
                    "has_on": bool(on), "has_off": bool(off)}})
        logger.debug("conversation.reply", extra={"data": {"speech": final}})
        return final

    def failure(self, explanation: str) -> Speech:
        reply = Speech(off=explanation)
        self.extend_history((DialogueMessage("narrator", reply),))
        logger.info("conversation.local_reply", extra={"data": {"text": reply.text, "speaker": "narrator", "speech": reply}})
        return reply

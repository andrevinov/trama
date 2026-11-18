"""Validação declarativa do plano; a interpretação do português pertence à IA.

Trechos e classificações são dados externos auditáveis, não uma prova semântica
de consentimento. Regras de estado continuam validadas pela sessão a cada etapa.
"""

import logging

from trama.application.dialogue import split_speech
from trama.application.intents import ActionPlan, DoorIntent, InspectionIntent, GestureIntent, InterpretationError, MovementIntent, RuleIntent, ScenarioIntent

logger = logging.getLogger(__name__)


class PlanAuthorizationError(InterpretationError):
    """Plano inconsistente com suas origens declaradas ou referências do cenário."""


def step_operations(step) -> tuple[str, ...]:
    if isinstance(step, MovementIntent):
        return ("clarify",) if step.clarification else (("move", "dash") if step.dash else ("move",))
    if isinstance(step, RuleIntent) and step.use_inspiration:
        return (step.operation, "inspiration")
    return (step.operation,)


def validate_player_plan(prompt: str, plan: ActionPlan, context: dict | None = None,
                         *, stage: str = "validation") -> None:
    """Verifica origens, cobertura, tipos de intenção e ids, sem gramática de verbos."""
    context = context or {}
    try:
        on = split_speech(prompt).on
        if not on:
            raise PlanAuthorizationError("Fala exclusivamente em off não autoriza ações.")
        if not plan.request_parts:
            raise PlanAuthorizationError("O plano não informa os trechos de origem da mensagem atual.")
        covered = []
        for part in plan.request_parts:
            if part.text not in on:
                raise PlanAuthorizationError("O trecho de origem não pertence ao pedido on atual.")
            if any(i >= len(plan.steps) for i in part.step_indices):
                raise PlanAuthorizationError("A origem aponta para uma etapa inexistente.")
            operations = tuple(op for i in part.step_indices for op in step_operations(plan.steps[i]))
            if operations != part.operations:
                raise PlanAuthorizationError("As operações da origem declarada não correspondem às etapas propostas.")
            if part.kind != "execute" and operations and operations != ("clarify",):
                raise PlanAuthorizationError("Perguntas, negações, citações e detalhes narrativos não autorizam ações.")
            if part.kind in {"question", "negated", "quoted", "narrative_detail"} and part.step_indices:
                raise PlanAuthorizationError("Esse trecho deve ser preservado sem executar etapas.")
            if part.kind == "execute" and not operations:
                raise PlanAuthorizationError("O trecho solicitado não foi mapeado para uma etapa.")
            if part.kind in {"unsupported", "conditional", "unclear"} and operations != ("clarify",):
                raise PlanAuthorizationError("Uma intenção não realizável exige esclarecimento antes de prosseguir.")
            covered.extend(part.step_indices)
        if covered != list(range(len(plan.steps))):
            raise PlanAuthorizationError("Toda etapa precisa de uma origem, na ordem, sem repetição ou omissão.")
        scene = context.get("map", {}).get("scene", {})
        passages = {p["id"] for p in scene.get("passages", [])}
        objects = {o["id"] for o in context.get("visible_objects", [])}
        fixtures = {o["id"] for o in scene.get("objects", []) if o.get("visible")}
        destinations = passages | {a["id"] for a in scene.get("areas", [])} | objects
        visible = {c["id"] for c in context.get("visible_creatures", [])}
        communication_targets = {c['id'] for c in context.get('communication_targets', [])} | visible
        for index, step in enumerate(plan.steps):
            if isinstance(step, MovementIntent):
                if step.clarification and index != len(plan.steps) - 1:
                    raise PlanAuthorizationError("O esclarecimento deve encerrar o plano.")
                if step.target_id is not None and step.target_id not in destinations | visible | fixtures:
                    raise PlanAuthorizationError("O destino não existe no contexto visível do Jogador.")
            elif isinstance(step, GestureIntent) and step.target_id not in communication_targets:
                raise PlanAuthorizationError('O destinatário do gesto não é um personagem conhecido.')
            elif isinstance(step, (DoorIntent, InspectionIntent)) and step.target_id not in passages:
                raise PlanAuthorizationError("A passagem não existe no contexto do Jogador.")
            elif isinstance(step, ScenarioIntent):
                capabilities = context.get("scenario", {}).get("operations", [])
                if (step.operation not in capabilities and step.operation != "sneak") or step.target_id not in destinations | visible:
                    raise PlanAuthorizationError("Interação ou alvo não disponível neste cenário.")
            elif isinstance(step, RuleIntent):
                if step.operation == "start_combat":
                    raise PlanAuthorizationError("Conflito é resolvido pelo Mundo e pela iniciativa.")
                if step.operation == "attack" and step.target_id not in visible:
                    raise PlanAuthorizationError("O alvo do ataque não existe no contexto visível do Jogador.")
        logger.info("player.plan_authorized", extra={"data": {"stage": stage, "validation": "declarative",
                    "operations": [op for s in plan.steps for op in step_operations(s)]}})
        logger.debug("player.request_sources", extra={"data": {"parts": plan.request_parts}})
    except (ValueError, TypeError) as error:
        logger.warning("player.plan_authorization_rejected", extra={"data": {"stage": stage,
                       "validation": "declarative", "reason": str(error)}})
        if isinstance(error, PlanAuthorizationError):
            raise
        raise PlanAuthorizationError(str(error)) from error

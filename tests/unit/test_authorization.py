"""O validador confere dados declarativos, sem interpretar português."""

from dataclasses import replace

import pytest

from trama.application.authorization import PlanAuthorizationError, validate_player_plan
from trama.application.intents import ActionPlan, MovementIntent, MovementSegment, RequestPart, RuleIntent
from conftest import sourced_plan

CONTEXT = {"map": {"scene": {"areas": [{"id": "cell"}], "passages": [{"id": "door"}]}},
           "visible_creatures": [{"id": "g1", "name": "Guarda 1"}]}


def test_valid_composed_request_has_no_verb_or_connector_restriction():
    prompt = "Eu uso Surto de Ação para atacar novamente o guarda atacado anteriormente com a espada."
    plan = sourced_plan(ActionPlan((RuleIntent("action_surge"), RuleIntent("attack", "g1"))), prompt)
    validate_player_plan(prompt, plan, CONTEXT)


@pytest.mark.parametrize("prompt", ["Retorno para (13,6).", "Volto à porta.", "Recuo para a cela."])
def test_paraphrases_are_not_parsed_again(prompt):
    plan = sourced_plan(ActionPlan((MovementIntent((MovementSegment("west", 2),), False, ""),)), prompt)
    validate_player_plan(prompt, plan, CONTEXT)


@pytest.mark.parametrize("kind", ["question", "negated", "quoted", "narrative_detail"])
def test_nonexecuting_interpretations_cannot_spend_resources(kind):
    prompt = "Não uso Retomar o Fôlego."
    plan = sourced_plan(ActionPlan((RuleIntent("second_wind"),)), prompt, kind=kind)
    with pytest.raises(PlanAuthorizationError):
        validate_player_plan(prompt, plan, CONTEXT)
    empty = ActionPlan((), (RequestPart(prompt, kind),))
    validate_player_plan(prompt, empty, CONTEXT)


def test_plan_cannot_add_omit_or_repeat_steps_relative_to_declared_request():
    prompt = "Uso Surto de Ação para atacar."
    steps = (RuleIntent("action_surge"), RuleIntent("attack", "g1"))
    correct = sourced_plan(ActionPlan(steps), prompt)
    for changed in ((steps[0],), (steps[1], steps[0]), (*steps, steps[1])):
        with pytest.raises(PlanAuthorizationError):
            validate_player_plan(prompt, replace(correct, steps=changed), CONTEXT)


@pytest.mark.parametrize("indices", [(0, 0), (1, 0), (), (0, 2)])
def test_source_indices_must_cover_steps_once_in_order(indices):
    prompt = "Uso Surto e ataco."
    plan = ActionPlan((RuleIntent("action_surge"), RuleIntent("attack", "g1")),
                      (RequestPart(prompt, "execute", ("action_surge", "attack"), indices),))
    with pytest.raises(PlanAuthorizationError):
        validate_player_plan(prompt, plan, CONTEXT)


def test_history_or_off_source_is_not_current_authorization():
    plan = sourced_plan(ActionPlan((RuleIntent("second_wind"),)), "Use Retomar o Fôlego.")
    for prompt in ("Caminho. [Use Retomar o Fôlego.]", "[Use Retomar o Fôlego.]", "Outro pedido."):
        with pytest.raises(PlanAuthorizationError):
            validate_player_plan(prompt, plan, CONTEXT)


def test_inspiration_and_dash_require_matching_declarative_modifiers():
    prompt = "Corro e ataco com inspiração."
    plan = sourced_plan(ActionPlan((MovementIntent((), True, "", "door"), RuleIntent("attack", "g1", use_inspiration=True))), prompt)
    validate_player_plan(prompt, plan, CONTEXT)
    bad = replace(plan, request_parts=(RequestPart(prompt, "execute", ("move", "attack"), (0, 1)),))
    with pytest.raises(PlanAuthorizationError):
        validate_player_plan(prompt, bad, CONTEXT)


def test_known_references_and_player_scope_are_checked_before_execution():
    for step in (MovementIntent((), False, "", "invented"), RuleIntent("attack", "hidden")):
        with pytest.raises(PlanAuthorizationError):
            validate_player_plan("Pedido atual.", sourced_plan(ActionPlan((step,)), "Pedido atual."), CONTEXT)


def test_missing_sources_and_clarification_followed_by_effects_are_rejected():
    with pytest.raises(PlanAuthorizationError, match="origem"):
        validate_player_plan("Ando.", ActionPlan((MovementIntent((MovementSegment("west", 1),), False, ""),)))
    plan = sourced_plan(ActionPlan((MovementIntent((), False, "Qual direção?"), RuleIntent("second_wind"))), "Pedido.")
    with pytest.raises(PlanAuthorizationError, match="encerrar"):
        validate_player_plan("Pedido.", plan)


def test_narrative_posture_is_preserved_without_a_mechanical_operation():
    prompt = "Retorno para (13,6) e fico de frente para a sala."
    plan = ActionPlan((MovementIntent((MovementSegment("west", 2),), False, ""),), (
        RequestPart("Retorno para (13,6)", "execute", ("move",), (0,)),
        RequestPart("fico de frente para a sala", "narrative_detail"),
    ))
    validate_player_plan(prompt, plan, CONTEXT)

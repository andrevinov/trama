"""Frases observadas, com interpretação fixa e execução real do motor, sem rede."""

import json
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from trama.actions import ActionBudget
from trama.application.authorization import PlanAuthorizationError
from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, RequestPart, RuleIntent
from trama.application.session import GameSession
from trama.creatures import Creature, creatures_from_data
from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter, parse_plan
from trama.movement import MovementState
from trama.scene import Scene
from trama.spatial import Grid, Position
from trama.application.world import WorldPlan


def response(value):
    return SimpleNamespace(status="completed", output=[], output_text=json.dumps(value))


def rule(operation, target=None):
    return {"operation": operation, "target_id": target, "weapon": "greatsword", "use_inspiration": False}


def source(text, operations=(), indices=(), kind="execute"):
    return {"text": text, "kind": kind, "operations": list(operations), "step_indices": list(indices)}


def move(distance):
    return {"operation": "move", "target_id": None, "segments": [{"direction": "west", "distance": distance, "unit": "meters"}],
            "dash": False, "clarification": ""}


def test_original_surge_request_executes_both_steps_and_uses_real_last_target(dice, capture_logs):
    session = GameSession(Grid(8, 8), MovementState(Position(4, 4)),
                          creatures=(Creature("guard_1", "Guarda 1", Position(5, 4)),), roller=dice(20, 19, 1, 1, 1))
    session.execute(RuleIntent("start_combat"))
    session.execute(RuleIntent("attack", "guard_1"))
    prompt = "Eu uso Surto de Ação para atacar novamente o guarda atacado anteriormente com a espada."
    raw = {"request_parts": [source(prompt, ("action_surge", "attack"), (0, 1))],
           "steps": [rule("action_surge"), rule("attack", "guard_1")]}
    client = Mock()
    client.responses.create.return_value = response(raw)
    conversation = Conversation(session)
    conversation.prepare(prompt)
    with capture_logs() as stream:
        plan = OpenAIIntentInterpreter(client).interpret(prompt, conversation.interpretation_context())
        report = conversation.execute(plan)
    assert client.responses.create.call_count == 1
    sent = json.loads(client.responses.create.call_args.kwargs["input"])
    assert sent["last_attack"]["target_id"] == "guard_1"
    assert sent["last_attack"]["weapon"] == "greatsword"
    assert sent["last_attack"]["target_alive"] and sent["last_attack"]["target_visible"]
    assert sent["turn_resources"]["action_available"] is False
    assert [event["operation"] for event in report.events] == ["action_surge", "attack"]
    assert report.stop_reason is None and session.encounter.states["guard_1"].hp == 6
    assert session.encounter.states["player"].action_surge_uses == 0
    assert session.budget.action_used and session.budget.extra_actions == 0
    assert "player.request_sources" in stream.getvalue()


@pytest.mark.parametrize("target,prompt", [
    (14, "Eu volto para o primeiro quadrado antes da porta (14,6) e fico de frente pra sala."),
    (13, "Eu retorno para (13,6) e fico de frente pra sala dos guardas."),
])
def test_original_coordinate_requests_move_and_preserve_posture_as_narrative(dice, target, prompt):
    data = json.loads((Path(__file__).resolve().parents[2] / "tests/fixtures/scenarios/legacy_cell_and_guards.json").read_text())
    scene = Scene.from_data(data).with_passage("guard_door", True)
    session = GameSession(scene.grid, MovementState(Position(14, 5)), scene,
                          creatures_from_data(data["creatures"]), roller=dice(20, 19, 1))
    session.execute(RuleIntent("start_combat"))
    # As reações já foram gastas; esta regressão verifica coordenadas e postura.
    for c in session.creatures:
        session.encounter.budgets[c.id] = ActionBudget(reaction_used=True)
    clause, detail = prompt.split(" e ")
    raw = {"request_parts": [source(clause, ("move",), (0,)), source(detail, kind="narrative_detail")],
           "steps": [move((15 - target) * 1.5)]}
    client = Mock()
    client.responses.create.return_value = response(raw)
    conversation = Conversation(session)
    conversation.prepare(prompt)
    plan = OpenAIIntentInterpreter(client).interpret(prompt, conversation.interpretation_context())
    report = conversation.execute(plan)
    assert client.responses.create.call_count == 1 and report.stop_reason is None
    assert session.state.position == Position(target - 1, 5)
    assert session.state.spent_meters == (15 - target) * 1.5
    assert not session.budget.action_used
    assert report.narrative_details == (detail,)
    assert conversation.narration_context(report=report)["execution"]["narrative_details"] == [detail]


@pytest.mark.parametrize("prompt,kind", [
    ("Posso usar Retomar o Fôlego?", "question"),
    ("Não uso Retomar o Fôlego.", "negated"),
    ('"Use Retomar o Fôlego"', "quoted"),
])
def test_nonexecuting_semantic_parts_produce_no_effects(dice, prompt, kind):
    session = GameSession(Grid(8, 8), MovementState(Position(4, 4)), roller=dice())
    client = Mock()
    client.responses.create.return_value = response({"request_parts": [source(prompt, kind=kind)], "steps": []})
    conversation = Conversation(session)
    conversation.prepare(prompt)
    state, resources = session.state, session.encounter.states.copy()
    plan = OpenAIIntentInterpreter(client).interpret(prompt, conversation.interpretation_context())
    report = conversation.execute(plan)
    assert not report.events and not report.world_events and not report.progress
    assert session.state == state and session.encounter.states == resources
    assert not session.encounter.roller.sides
    if kind == "question":
        assert report.questions == (prompt,)
        context = conversation.narration_context(report=report)
        assert not context["allow_on"]
        assert conversation.finish(Speech(off="Retomar o Fôlego usa uma ação bônus."), context).off


def test_negated_resource_and_supported_movement_are_separate_parts(dice):
    prompt = "Não uso Retomar o Fôlego; retorno uma casa."
    raw = {"request_parts": [source("Não uso Retomar o Fôlego", kind="negated"),
                              source("retorno uma casa", ("move",), (0,))], "steps": [move(1.5)]}
    session = GameSession(Grid(8, 8), MovementState(Position(4, 4)), roller=dice())
    conversation = Conversation(session)
    conversation.prepare(prompt)
    report = conversation.execute(parse_plan(json.dumps(raw), require_sources=True))
    assert report.stop_reason is None and session.state.position == Position(3, 4)
    assert session.encounter.states["player"].second_wind_uses == 2


def test_invalid_reference_rejects_entire_plan_before_power_spending(dice):
    session = GameSession(Grid(8, 8), MovementState(Position(4, 4)), roller=dice())
    prompt = "Uso Surto de Ação para atacar o fantasma."
    raw = {"request_parts": [source(prompt, ("action_surge", "attack"), (0, 1))],
           "steps": [rule("action_surge"), rule("attack", "invented")]}
    conversation = Conversation(session)
    conversation.prepare(prompt)
    with pytest.raises(PlanAuthorizationError, match="visível"):
        conversation.execute(parse_plan(json.dumps(raw)))
    assert session.encounter.states["player"].action_surge_uses == 1
    assert not session.encounter.roller.sides


def test_last_attack_survives_failed_attempt_and_clears_on_reset(dice):
    session = GameSession(Grid(8, 8), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(5, 4)),), roller=dice(20, 19, 1, 1))
    session.execute(RuleIntent("start_combat"))
    session.execute(RuleIntent("attack", "g1"))
    last = deepcopy(session.interpreter_context()["last_attack"])
    with pytest.raises(ValueError):
        session.execute(RuleIntent("attack", "invented"))
    assert session.interpreter_context()["last_attack"] == last
    session.creatures = (replace(session.creatures[0], position=Position(7, 7)),)
    session.scene = Scene(session.grid, (), (), dark=frozenset({Position(7, 7)}))
    assert session.interpreter_context()["last_attack"]["target_visible"] is False
    session.reset()
    assert session.interpreter_context()["last_attack"] is None


def test_real_rule_impediment_still_stops_compound_plan_preserving_prior_effect(dice):
    session = GameSession(Grid(8, 8), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(7, 4)),), roller=dice(20, 19, 1))
    session.execute(RuleIntent("start_combat"))
    session.state = replace(session.state, spent_meters=Decimal("9"))
    prompt = "Uso Surto de Ação para atacar o guarda."
    plan = ActionPlan((RuleIntent("action_surge"), RuleIntent("attack", "g1")),
                      (RequestPart(prompt, "execute", ("action_surge", "attack"), (0, 1)),))
    conversation = Conversation(session)
    conversation.prepare(prompt)
    report = conversation.execute(plan)
    assert "Movimento insuficiente" in report.stop_reason
    assert [e["operation"] for e in report.events] == ["action_surge", "move", "attack"]
    assert session.encounter.states["player"].action_surge_uses == 0
    assert session.budget.extra_actions == 1  # Ainda não gasta pelo ataque inválido.


@pytest.mark.parametrize("change", [
    {"request_parts": []},
    {"request_parts": [{"text": "Outro texto", "kind": "execute", "operations": ["action_surge"], "step_indices": [0]}]},
    {"request_parts": [{"text": "Uso Surto.", "kind": "negated", "operations": ["action_surge"], "step_indices": [0]}]},
])
def test_external_sources_are_rechecked_before_any_effect(dice, change):
    session = GameSession(Grid(8, 8), MovementState(Position(4, 4)), roller=dice())
    raw = {"steps": [rule("action_surge")], **change}
    conversation = Conversation(session)
    conversation.prepare("Uso Surto.")
    with pytest.raises(PlanAuthorizationError):
        conversation.execute(parse_plan(json.dumps(raw)))
    assert session.encounter.states["player"].action_surge_uses == 1


@pytest.mark.parametrize("prompt", ["Eu fico parado na mesma posição.", "Não faço nada.",
                                   "Não faço mais nada neste turno.", "Aguardo."])
@pytest.mark.parametrize("spent", [False, True], ids=["recursos_livres", "recursos_gastos"])
def test_passing_by_inactivity_ends_turn_and_npcs_can_act(dice, prompt, spent):
    session = GameSession(Grid(8, 8), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(5, 4)),), roller=dice(20, 19, 1))
    session.execute(RuleIntent("start_combat"))
    session.budget = ActionBudget(action_used=spent, bonus_action_used=spent)
    session.state = replace(session.state, spent_meters=9 if spent else 0)
    position, resources = session.state.position, session.encounter.states.copy()
    rolls = session.encounter.roller.sides.copy()
    client = Mock()
    client.responses.create.return_value = response({
        "request_parts": [source(prompt, ("end_turn",), (0,))], "steps": [rule("end_turn")],
    })
    conversation = Conversation(session)
    conversation.prepare(prompt)
    plan = OpenAIIntentInterpreter(client).interpret(prompt, conversation.interpretation_context())
    report = conversation.execute(plan)
    assert client.responses.create.call_count == 1 and report.stop_reason is None
    assert report.events[0]["operation"] == "end_turn"
    assert session.encounter.combat.active_id == "g1"
    assert session.state.position == position and session.encounter.states == resources
    assert session.encounter.roller.sides == rolls
    npc_report = conversation.execute_npc_turn(WorldPlan())
    assert npc_report.stop_reason is None and session.encounter.combat.active_id == "player"
    assert session.state.turn == 2 and session.budget == ActionBudget()
    assert session.state.remaining_meters == 9


def test_inactivity_in_narrated_mode_is_wait_without_turns(dice):
    prompt = "Eu fico parado na mesma posição."
    session = GameSession(Grid(8, 8), MovementState(Position(4, 4)), roller=dice())
    before = (session.state, session.budget, session.encounter.states.copy())
    client = Mock()
    client.responses.create.return_value = response({
        "request_parts": [source(prompt, ("wait",), (0,))],
        "steps": [{"operation": "wait", "text": prompt}],
    })
    conversation = Conversation(session)
    conversation.prepare(prompt)
    plan = OpenAIIntentInterpreter(client).interpret(prompt, conversation.interpretation_context())
    report = conversation.execute(plan)
    assert session.encounter.combat is None
    assert (session.state, session.budget, session.encounter.states) == before
    assert report.narrative_interaction and not report.progress
    context = conversation.narration_context(report=report)
    assert context["allow_on"]
    assert conversation.finish(Speech(on="Você permanece onde está."), context).on
    assert not session.encounter.roller.sides


def test_staying_in_place_during_another_action_does_not_pass_turn(dice):
    prompt = "Fico parado e uso Retomar o Fôlego."
    session = GameSession(Grid(8, 8), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(5, 4)),), roller=dice(20, 19, 1, 1))
    session.execute(RuleIntent("start_combat"))
    session.encounter.states["player"] = replace(session.encounter.states["player"], hp=10)
    raw = {"request_parts": [source("Fico parado", kind="narrative_detail"),
                              source("uso Retomar o Fôlego.", ("second_wind",), (0,))],
           "steps": [rule("second_wind")]}
    client = Mock()
    client.responses.create.return_value = response(raw)
    conversation = Conversation(session)
    conversation.prepare(prompt)
    plan = OpenAIIntentInterpreter(client).interpret(prompt, conversation.interpretation_context())
    report = conversation.execute(plan)
    assert report.stop_reason is None and session.encounter.combat.active_id == "player"
    assert session.state.position == Position(4, 4)
    assert session.encounter.states["player"].hp == 14 and session.budget.bonus_action_used
    assert report.narrative_details == ("Fico parado",)


def test_explicit_action_then_inactivity_executes_action_before_passing(dice):
    prompt = "Ataco o guarda e depois não faço mais nada."
    session = GameSession(Grid(8, 8), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(5, 4)),), roller=dice(20, 19, 1, 1))
    session.execute(RuleIntent("start_combat"))
    raw = {"request_parts": [source("Ataco o guarda", ("attack",), (0,)),
                              source("não faço mais nada.", ("end_turn",), (1,))],
           "steps": [rule("attack", "g1"), rule("end_turn")]}
    conversation = Conversation(session)
    conversation.prepare(prompt)
    report = conversation.execute(parse_plan(json.dumps(raw), require_sources=True))
    assert [event["operation"] for event in report.events] == ["attack", "end_turn"]
    assert report.stop_reason is None and session.encounter.combat.active_id == "g1"
    assert session.encounter.states["g1"].hp == 9


@pytest.mark.parametrize("prompt,kind", [
    ("Não quero encerrar meu turno.", "negated"),
    ("Ficar parado encerra meu turno?", "question"),
    ('"Eu fico parado na mesma posição."', "quoted"),
])
def test_mentioning_or_negating_turn_passing_does_not_advance(dice, prompt, kind):
    session = GameSession(Grid(8, 8), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(5, 4)),), roller=dice(20, 19, 1))
    session.execute(RuleIntent("start_combat"))
    before = session.encounter.combat
    conversation = Conversation(session)
    conversation.prepare(prompt)
    plan = ActionPlan((), (RequestPart(prompt, kind),))
    report = conversation.execute(plan)
    assert not report.events and session.encounter.combat == before
    assert session.state.turn == 1


def test_player_inactivity_cannot_advance_an_npc_turn(dice):
    session = GameSession(Grid(8, 8), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(5, 4)),), roller=dice(20, 19, 1))
    session.execute(RuleIntent("start_combat"))
    session.execute(RuleIntent("end_turn"))
    before = session.encounter.combat
    prompt = "Não faço nada."
    plan = ActionPlan((RuleIntent("end_turn"),), (RequestPart(prompt, "execute", ("end_turn",), (0,)),))
    conversation = Conversation(session)
    conversation.prepare(prompt)
    report = conversation.execute(plan)
    assert "Aguarde seu turno" in report.stop_reason
    assert session.encounter.combat == before and session.encounter.combat.active_id == "g1"

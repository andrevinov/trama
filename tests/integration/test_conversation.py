import json
from conftest import sourced_plan
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from trama.application.conversation import Conversation
from trama.application.dialogue import Speech, NarrationError
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, MovementSegment
from trama.application.session import GameSession
from trama.creatures import creatures_from_data
from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter, parse_intent, parse_plan
from trama.infrastructure.openai_narrator import OpenAINarrator
from trama.movement import MovementState
from trama.scene import Scene
from trama.spatial import Position


@pytest.fixture
def conversation():
    data = json.loads((Path(__file__).resolve().parents[2] / "pocs/movimento/cela_guardas.json").read_text())
    scene = Scene.from_data(data)
    session = GameSession(scene.grid, MovementState(Position(*data["start"])), scene,
                          creatures_from_data(data["creatures"]))
    return Conversation(session)


def movement(distance, direction="east", unit="meters"):
    return {"operation": "move", "segments": [{"direction": direction, "distance": distance, "unit": unit}],
            "target_id": None, "dash": False, "clarification": ""}


def test_initial_narration_receives_only_visible_facts(conversation):
    context = conversation.narration_context(initial=True)
    assert context["phase"] == "initial"
    assert context["allow_on"]
    assert context["perception"]["current_place"] == "Cela"
    assert context["perception"]["visible_creatures"] == []
    assert "Sala dos Guardas" not in {a["name"] for a in context["perception"]["visible_places"]}
    assert "guard_1" not in json.dumps(context["perception"])
    assert len(context["world"]["npcs"]) == 3


def test_mixed_prompt_keeps_off_out_of_current_and_historical_actions(conversation):
    speech = conversation.prepare("Entre no Corredor. [Abra a porta. Quanto posso andar?]")
    assert speech.on == "Entre no Corredor."
    context = conversation.interpretation_context()
    assert "Abra a porta" not in json.dumps(context)
    report = conversation.execute(sourced_plan(ActionPlan((MovementIntent((), False, "", "corridor"),)), speech.on))
    request = conversation.narration_context(speech, report)
    assert "Abra a porta" in request["player"]["off"]
    assert request["perception"]["current_place"] == "Corredor"
    assert not conversation.session.scene.passages[1].is_open
    final = conversation.finish(Speech("Você entrou no corredor.", "Restam 4,5 m."), request)
    assert "[Restam 4,5 m.]" in final.text


def test_off_only_does_not_change_game_state_and_cannot_produce_on(conversation):
    before = conversation.session.state
    speech = conversation.prepare("[Abra a porta e me explique os Dados Místicos.]")
    request = conversation.narration_context(speech)
    final = conversation.finish(Speech("Você abriu a porta.", "Não tenho essa regra definida."), request)
    assert final.on == ""
    assert final.text.startswith("[")
    assert conversation.session.state == before
    assert not conversation.session.scene.passages[1].is_open


def test_five_meters_executes_four_and_half_and_reports_remainder(conversation):
    speech = conversation.prepare("Ande 5 m para a direita. [Quanto resta?]")
    plan = parse_plan(json.dumps({"steps": [movement(5)]}))
    report = conversation.execute(sourced_plan(plan, speech.on))
    assert report.progress
    assert report.events[0]["traveled_meters"] == 4.5
    assert "0,5 m" in report.stop_reason
    assert conversation.session.state.position == Position(6, 5)
    assert conversation.session.state.spent_meters == 0
    request = conversation.narration_context(speech, report)
    final = conversation.finish(Speech("Você percorreu 4,5 m e entrou no corredor.", "Restam 4,5 m."), request)
    assert report.stop_reason in final.off
    assert "Corredor (coluna 7, linha 6)" in final.off
    assert final.on


def test_subsquare_request_does_not_waste_dash_or_produce_on(conversation):
    intent = parse_intent(json.dumps({**movement(.5), "dash": True}))
    before = conversation.session.state
    report = conversation.execute(ActionPlan((intent,)))
    assert not report.progress
    assert conversation.session.state == before
    assert not conversation.session.budget.action_used
    final = conversation.finish(Speech("Você correu.", report.stop_reason),
                                conversation.narration_context(report=report))
    assert not final.on
    assert "coluna 4, linha 6" in final.off


def test_fractional_remainder_stops_later_segments_and_operations(conversation):
    first = parse_intent(json.dumps(movement(2)))
    first = MovementIntent((*first.segments, MovementSegment("north", 1)), False, "")
    report = conversation.execute(ActionPlan((first, DoorIntent("open", "guard_door"))))
    assert conversation.session.state.position == Position(4, 5)
    assert report.unperformed_steps == 1
    assert "0,5 m" in report.stop_reason
    assert not conversation.session.scene.passages[1].is_open


def test_move_open_enter_sequence_executes_in_order(conversation):
    report = conversation.execute(ActionPlan((
        MovementIntent((), True, "", "guard_door"), DoorIntent("open", "guard_door"),
        MovementIntent((), False, "", "guard_room"),
    )))
    assert report.stop_reason is None
    assert [e["operation"] for e in report.events] == ["move", "open", "move"]
    assert conversation.session.state.position == Position(14, 5)
    assert conversation.session.state.spent_meters == 0
    assert len(conversation.narration_context(report=report)["perception"]["visible_creatures"]) == 3
    assert report.context()["reactions"] == []


def test_no_rollback_and_no_later_action_after_budget_interruption(conversation, enter_turn_mode):
    enter_turn_mode(conversation.session)
    report = conversation.execute(ActionPlan((
        MovementIntent((), False, "", "guard_door"), DoorIntent("open", "guard_door"),
    )))
    assert report.progress
    assert report.unperformed_steps == 1
    assert "insuficiente" in report.stop_reason
    assert conversation.session.state.position == Position(9, 5)
    assert not conversation.session.scene.passages[1].is_open


def test_closed_door_stops_approach_instead_of_rejecting_entire_move(conversation):
    report = conversation.execute(ActionPlan((MovementIntent((), True, "", "guard_room"),)))
    assert report.progress
    assert conversation.session.state.position == Position(12, 5)
    assert "Porta da Sala dos Guardas está fechada" in report.stop_reason


def test_impossible_first_operation_produces_only_off_and_skips_later_steps(conversation):
    before = conversation.session.state
    report = conversation.execute(ActionPlan((DoorIntent("open", "guard_door", allow_approach=False),
                                              MovementIntent((), False, "", "corridor"))))
    assert not report.progress
    assert report.unperformed_steps == 1
    assert conversation.session.state == before
    final = conversation.finish(Speech("Você abriu a porta.", ""), conversation.narration_context(report=report))
    assert not final.on
    assert "Aproxime-se" in final.off


def test_unsupported_later_action_preserves_earlier_progress(conversation):
    report = conversation.execute(ActionPlan((MovementIntent((), False, "", "corridor"),
                                              MovementIntent((), False, "Combate ainda não implementado."))))
    assert report.progress
    assert conversation.session.state.position == Position(6, 5)
    assert "Combate" in report.stop_reason


def test_narrator_uses_separate_structured_channels_and_no_engine_reference(conversation):
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        status="completed", output=[], output_text=json.dumps({"on": "Você está numa cela.", "off": ""}),
    )
    reply = OpenAINarrator(client).narrate(conversation.narration_context(initial=True))
    assert reply == Speech("Você está numa cela.", "")
    request = client.responses.create.call_args.kwargs
    assert request["text"]["format"]["name"] == "narrator_reply"
    assert request["store"] is False


@pytest.mark.parametrize("text", ["{}", "[]", '{"on":1,"off":""}', '{"on":"","off":""}'])
def test_invalid_narrator_output_is_rejected(conversation, text):
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(status="completed", output=[], output_text=text)
    with pytest.raises(NarrationError):
        OpenAINarrator(client).narrate(conversation.narration_context(initial=True))

from conftest import scripted_responses, sourced_output, sourced_plan
from dataclasses import replace
import json
from pathlib import Path
import runpy
from types import SimpleNamespace
from unittest.mock import Mock

from openai import APIConnectionError
import pytest

from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.intents import RuleIntent
from trama.application.session import GameSession
from trama.characters import ability_check, finish_short_rest
from trama.creatures import Creature
from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter, InterpretationError
from trama.infrastructure.openai_narrator import OpenAINarrator
from trama.movement import MovementState
from trama.observability import log_context
from trama.spatial import Grid, Position


MOVE = {"operation": "move", "target_id": None, "segments": [{"direction": "north", "distance": 1, "unit": "squares"}],
        "dash": False, "clarification": ""}


def events(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def response(payload, *, status="completed", usage=None):
    return SimpleNamespace(status=status, output=[], output_text=json.dumps(payload), usage=usage,
                           id="resp_example", _request_id="req_example")


def token_usage():
    return SimpleNamespace(input_tokens=80, output_tokens=20, total_tokens=100,
                           input_tokens_details=SimpleNamespace(cached_tokens=16, cache_write_tokens=0),
                           output_tokens_details=SimpleNamespace(reasoning_tokens=5))


def test_complete_decision_execution_narration_trace_and_actual_token_usage(capture_logs):
    client = Mock()
    client.api_key = "never-serialize-the-client"
    client.responses.create.side_effect = scripted_responses(*[response({"steps": [MOVE]}, usage=token_usage()),
                                          response({"on": "Você andou 1,5 m para o norte.", "off": ""}, usage=token_usage())])
    with capture_logs() as stream, log_context(interaction_id="interaction-1"):
        session = GameSession(Grid(10, 10), MovementState(Position(4, 4)))
        conversation = Conversation(session)
        speech = conversation.prepare("Ande uma casa para o norte.")
        plan = OpenAIIntentInterpreter(client).interpret(speech.on, conversation.interpretation_context())
        report = conversation.execute(plan)
        context = conversation.narration_context(speech, report)
        conversation.finish(OpenAINarrator(client).narrate(context), context)
    records = events(stream)
    assert all(r["interaction_id"] == "interaction-1" for r in records)
    requests = [r for r in records if r["event"] == "ai.request_payload"]
    assert len(requests) == 2
    assert requests[0]["ai_call_id"] != requests[1]["ai_call_id"]
    assert requests[0]["data"]["request"] == client.responses.create.call_args_list[0].kwargs
    assert json.loads(requests[0]["data"]["request"]["input"])["player_prompt"] == speech.on
    assert "instructions" in requests[0]["data"]["request"]
    assert "never-serialize-the-client" not in stream.getvalue()
    received = [r for r in records if r["event"] == "ai.response_received"]
    assert received[0]["data"]["usage"] == {"input_tokens": 80, "output_tokens": 20, "total_tokens": 100,
                                            "cached_input_tokens": 16, "cache_write_tokens": 0, "reasoning_tokens": 5}
    assert received[0]["data"]["provider_request_id"] == "req_example"
    assert received[0]["data"]["duration_ms"] >= 0
    decision = next(r for r in records if r["event"] == "ai.decision")
    assert decision["ai_call_id"] == requests[0]["ai_call_id"]
    moved = next(r for r in records if r["event"] == "movement.resolved")
    completed = next(r for r in records if r["event"] == "game.operation_completed")
    assert moved["operation_id"] == completed["operation_id"] and moved["operation_id"]
    assert completed["data"]["movement_after"]["position"] == {"x": 4, "y": 3}
    assert session.state.position == Position(4, 3) and session.state.spent_meters == 0
    assert records[-1]["event"] == "conversation.reply"


def test_rejected_plan_records_raw_output_exact_validation_and_step(capture_logs):
    invalid = {"steps": [{**MOVE, "target_id": "guard_door"}]}
    client = Mock()
    client.responses.create.side_effect = scripted_responses(response(invalid, usage=token_usage()))
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)))
    with capture_logs() as stream, log_context(interaction_id="invalid-plan"):
        with pytest.raises(InterpretationError, match="plano inválido"):
            OpenAIIntentInterpreter(client).interpret("Ando tudo que posso em direção à porta.", session.interpreter_context())
    records = events(stream)
    rejected = next(r for r in records if r["event"] == "ai.plan_rejected")
    assert rejected["data"]["step_index"] == 0
    assert any("destino nomeado ou segmentos" in cause["message"] for cause in rejected["error"]["causes"])
    assert "MovementIntent" in rejected["error"]["traceback"]
    raw = next(r for r in records if r["event"] == "ai.rejected_plan_payload")
    assert json.loads(raw["data"]["output_text"]) == sourced_output(invalid, "Ando tudo que posso em direção à porta.")
    assert raw["ai_call_id"] == rejected["ai_call_id"] and rejected["ai_call_id"]
    assert next(r for r in records if r["event"] == "ai.response_received")["data"]["usage"]["total_tokens"] == 100
    assert session.state == session.initial_state


def test_info_keeps_usage_but_not_complete_prompts_or_responses(capture_logs):
    client = Mock()
    client.responses.create.side_effect = scripted_responses(response({"steps": [MOVE]}, usage=token_usage()))
    with capture_logs("INFO") as stream:
        OpenAIIntentInterpreter(client).interpret("Ande uma casa com Mensagem privada de exemplo", {})
    records = events(stream)
    assert "Mensagem privada" not in stream.getvalue()
    assert not any(r["event"] in {"ai.request_payload", "ai.response_payload", "ai.decision"} for r in records)
    assert next(r for r in records if r["event"] == "ai.response_received")["data"]["usage"]["total_tokens"] == 100


def test_log_redaction_does_not_modify_the_actual_request(capture_logs):
    client = Mock()
    client.responses.create.side_effect = scripted_responses(response({"steps": [MOVE]}))
    prompt = "Ande uma casa com texto de teste sk-fake-secret-123456789"
    with capture_logs() as stream:
        OpenAIIntentInterpreter(client).interpret(prompt, {})
    assert json.loads(client.responses.create.call_args.kwargs["input"])["player_prompt"] == prompt
    assert "sk-fake-secret-123456789" not in stream.getvalue()


def test_info_records_complete_player_and_delivered_narration_with_off(capture_logs):
    player = "Eu observo o corredor.\n[Qual a regra?]"
    narrator = Speech("Você vê uma porta coberta de musgo.\nEla está fechada.", "Explicação de regra.")
    with capture_logs("INFO") as stream:
        session = GameSession(Grid(10, 10), MovementState(Position(4, 4)))
        conversation = Conversation(session)
        conversation.prepare(player)
        delivered = conversation.finish(narrator, conversation.narration_context(initial=True))
        conversation.failure("Aviso local de teste.")
    records = events(stream)
    message = next(r for r in records if r["event"] == "conversation.message_accepted")
    reply = next(r for r in records if r["event"] == "conversation.reply_delivered")
    local = next(r for r in records if r["event"] == "conversation.local_reply")
    assert message["data"]["text"] == player and message["data"]["speaker"] == "player"
    assert reply["data"]["text"] == delivered.text and "[Explicação de regra.]" in reply["data"]["text"]
    assert local["data"]["text"] == "[Aviso local de teste.]"
    assert not any(r["event"] == "ai.request_payload" for r in records)


def test_incomplete_response_still_records_usage_and_unavailable_usage_stays_null(capture_logs):
    client = Mock()
    client.responses.create.side_effect = scripted_responses(response({}, status="incomplete", usage=token_usage()))
    with capture_logs() as stream:
        with pytest.raises(InterpretationError, match="incompleta"):
            OpenAIIntentInterpreter(client).interpret("Ande", {})
        client.responses.create.side_effect = scripted_responses(response({"steps": [MOVE]}))
        OpenAIIntentInterpreter(client).interpret("Ande", {})
    received = [r for r in events(stream) if r["event"] == "ai.response_received"]
    assert received[0]["data"]["usage"]["total_tokens"] == 100
    assert all(value is None for value in received[1]["data"]["usage"].values())
    assert any(r["event"] == "ai.request_failed" and r["error"]["type"] == "OpenAIRequestError" for r in events(stream))


def test_network_failure_has_cause_trace_and_never_invents_token_counts(capture_logs):
    client = Mock()
    client.responses.create.side_effect = APIConnectionError(request=Mock())
    with capture_logs() as stream:
        with pytest.raises(InterpretationError):
            OpenAIIntentInterpreter(client).interpret("Ande", {})
    records = events(stream)
    failure = next(r for r in records if r["event"] == "ai.request_failed")
    assert failure["error"]["causes"][0]["type"] == "APIConnectionError"
    assert not any(r["event"] == "ai.response_received" for r in records)


def test_dice_powers_checks_rests_and_resource_changes_are_observable_without_changing_rules(capture_logs, dice):
    roller = dice(15, 16, 10, 4, 19)
    with capture_logs() as stream, log_context(interaction_id="combat-request"):
        session = GameSession(Grid(10, 10), MovementState(Position(4, 4)),
                              creatures=(Creature("g1", "Guarda", Position(5, 4)),), roller=roller)
        session.encounter.states["player"] = replace(session.encounter.states["player"], hp=10)
        session.execute(RuleIntent("start_combat"))
        session.execute(RuleIntent("second_wind"))
        session.execute(RuleIntent("attack", "g1", "unarmed"))
        sheet = session.encounter.player_sheet
        with log_context(operation_id="check-api"):
            state, roll, total = ability_check(sheet, session.encounter.states["player"], "athletics", 15,
                                               dice(1, 2, 10), use_tactical_mind=True)
            rested = finish_short_rest(sheet, state, dice(2), hit_dice=1)
    records = events(stream)
    assert roller.sides == [20, 20, 20, 10, 20]
    assert session.encounter.states["player"].hp == 17 and session.encounter.states["g1"].hp == 8
    assert session.state.free_meters == 4.5
    assert roll.dice == (1, 2) and total == 17 and state.second_wind_uses == 0
    assert rested.second_wind_uses == 1
    power = next(r for r in records if r["event"] == "character.power_used" and r["data"]["power"] == "second_wind")
    assert power["data"]["before"]["hp"] == 10 and power["data"]["after"]["hp"] == 17
    attack = next(r for r in records if r["event"] == "combat.attack_resolved")
    assert attack["data"]["result"]["critical"] and attack["data"]["result"]["damage"] == 4
    check = next(r for r in records if r["event"] == "character.ability_check_resolved")
    assert check["operation_id"] == "check-api" and check["data"]["passed"]
    assert any(r["event"] == "character.rest_finished" for r in records)
    assert len([r for r in records if r["event"] == "dice.rolled"]) == 9


def test_rejected_operation_records_reason_without_commit_or_dice(capture_logs, dice):
    roller = dice()
    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda", Position(8, 4)),), roller=roller)
    with capture_logs() as stream:
        with pytest.raises(ValueError, match="Aproxime"):
            session.execute(RuleIntent("attack", "g1"))
    records = events(stream)
    rejected = next(r for r in records if r["event"] == "game.operation_rejected")
    assert rejected["error"]["type"] == "CharacterError" and "Aproxime" in rejected["data"]["reason"]
    assert not any(r["event"] == "game.operation_completed" for r in records)
    assert session.state == session.initial_state and not roller.sides


def test_cli_debug_creates_jsonl_and_records_startup_failure(capture_logs, monkeypatch, tmp_path):
    module = runpy.run_path(str(Path(__file__).resolve().parents[2] / "pocs/movimento/run.py"))
    path = tmp_path / "debug.jsonl"
    missing = tmp_path / "missing.json"
    monkeypatch.setattr("sys.argv", ["run.py", "--debug", "--log-file", str(path), "--scenario", str(missing)])
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with capture_logs(), pytest.raises(FileNotFoundError):
        module["main"]()
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["event"] for r in records] == ["app.started", "app.failed", "app.stopped"]
    assert records[0]["data"]["debug"]
    assert records[1]["error"]["type"] == "FileNotFoundError"
    assert len({r["session_id"] for r in records}) == 1

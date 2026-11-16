"""Validação real do consumidor lnav, com arquivos e configuração temporários."""

import json
import logging
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from trama.movement import MovementRequest, MovementState, apply_movement
from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.session import GameSession
from trama.observability import log_context
from trama.spatial import Grid, Position

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "tools/lnav"
LNAV = shutil.which("lnav")
pytestmark = pytest.mark.skipif(LNAV is None, reason="lnav não instalado; integração opcional")
PLAYER_TEXT = ("Eu observo as paredes e a porta do corredor. " * 14) + "\n[Qual a regra? FIM-DO-JOGADOR]"
REPLY = Speech(("Você vê pedras cobertas de musgo e uma porta fechada. " * 14) + "FIM-DO-NARRADOR",
               "Explicação em off.\nOutra linha completa.")


@pytest.fixture
def log_file(tmp_path, capture_logs):
    path = tmp_path / "trama.jsonl"
    logger = logging.getLogger("trama.test_lnav")
    with capture_logs(log_file=path), log_context(interaction_id="interaction-example"):
        with log_context(operation_id="operation-example"):
            apply_movement(Grid(10, 10), MovementState(Position(2, 2)), MovementRequest((Position(3, 2),)))
        with log_context(ai_call_id="call-rejected"):
            logger.info("ai.request_started", extra={"data": {"model": "example-model", "task": "action_plan"}})
            logger.debug("ai.request_payload", extra={"data": {"request": {"instructions": "Regras de teste",
                                                                           "input": "Ande.\n[Em off]"}}})
            logger.info("ai.response_received", extra={"data": {"status": "completed", "duration_ms": 12.5,
                        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
                                  "cached_input_tokens": 0, "reasoning_tokens": 0}}})
            logger.debug("ai.response_payload", extra={"data": {"output_text": '{"steps":[]}'}})
            try:
                try:
                    raise ValueError("Destino e segmentos não podem ser usados juntos.")
                except ValueError as error:
                    raise RuntimeError("Plano inválido") from error
            except RuntimeError:
                logger.error("ai.plan_rejected", extra={"data": {"step_index": 0}}, exc_info=True)
        with log_context(ai_call_id="call-network"):
            logger.info("ai.request_started", extra={"data": {"model": "example-model", "task": "narrator_reply"}})
            try:
                raise ConnectionError("Falha de conexão")
            except ConnectionError:
                logger.error("ai.request_failed", extra={"data": {"duration_ms": 20}}, exc_info=True)
        with log_context(ai_call_id="call-no-usage"):
            logger.info("ai.request_started", extra={"data": {"model": "example-model", "task": "narrator_reply"}})
            logger.info("ai.response_received", extra={"data": {"status": "completed", "usage": None}})
        with log_context(ai_call_id="call-pending"):
            logger.info("ai.request_started", extra={"data": {"model": "example-model", "task": "narrator_reply"}})
        logger.info("example." + "long_event_name_" * 5)
        session = GameSession(Grid(10, 10), MovementState(Position(2, 2)))
        conversation = Conversation(session)
        conversation.prepare(PLAYER_TEXT)
        conversation.finish(REPLY, conversation.narration_context(initial=True))
        logger.info("conversation.reply_delivered", extra={"data": {"has_on": True, "has_off": False}})
        logger.info("dice.rolled", extra={"data": {"sides": 20, "result": 19}})
        logger.info("combat.attack_resolved", extra={"data": {"target_id": "guard_1", "weapon": "flail",
                    "result": {"roll": {"dice": [19]}, "hit": True, "critical": True, "damage": 7}}})
    return path


@pytest.fixture
def lnav(tmp_path):
    config_home = tmp_path / "lnav-config"
    # O lnav 0.14 recorre ao perfil real quando a pasta XDG ainda não existe.
    (config_home / "lnav").mkdir(parents=True, exist_ok=True)
    def run(path, command, *, output=":write-json-to -"):
        requests = command if isinstance(command, list) else [command]
        commands = [part for request in requests for part in ("-c", request)]
        if output != requests[-1]:
            commands += ["-c", output]
        result = subprocess.run(
            [LNAV, "-n", "-N", "-I", str(ADDON), *commands, str(path)],
            env={**os.environ, "XDG_CONFIG_HOME": str(config_home)},
            capture_output=True, text=True, timeout=20,
        )
        assert result.returncode == 0, result.stderr
        assert "error:" not in result.stderr.lower(), result.stderr
        return json.loads(result.stdout) if output == ":write-json-to -" else result.stdout
    return run


def test_lnav_recognizes_format_and_preserves_full_event_ids_and_json(log_file, lnav):
    formats = lnav(log_file, ";SELECT DISTINCT log_format FROM all_logs")
    assert formats == [{"log_format": "trama_log"}]
    records = lnav(log_file, ";SELECT * FROM trama_events ORDER BY log_line")
    original = [json.loads(line) for line in log_file.read_text().splitlines()]
    assert [r["event"] for r in records] == [r["event"] for r in original]
    assert all(r["interaction_id"] == "interaction-example" for r in records)
    assert records[0]["operation_id"] == "operation-example"
    moved = next(r for r in records if r["event"] == "movement.resolved")
    assert json.loads(moved["data"])["cost_meters"] == "1.5"
    assert moved["ai_call_id"] is None and moved["error"] is None
    rendered = lnav(log_file, ":write-view-to -", output=":write-view-to -")
    assert "trama.movement" in rendered and "movement.resolved" in rendered
    assert len(rendered.splitlines()) == len(original)


def test_ai_table_counts_each_call_once_and_preserves_unknown_tokens(log_file, lnav):
    calls = {r["ai_call_id"]: r for r in lnav(log_file, ";SELECT * FROM trama_ai_calls")}
    assert len(calls) == 4
    rejected = calls["call-rejected"]
    assert rejected["status"] == "error"
    assert rejected["duration_ms"] == 12.5
    assert rejected["input_tokens"] == 10 and rejected["output_tokens"] == 5 and rejected["total_tokens"] == 15
    assert rejected["cached_input_tokens"] == rejected["reasoning_tokens"] == 0
    assert json.loads(rejected["request"])["input"] == "Ande.\n[Em off]"
    assert rejected["response_text"] == '{"steps":[]}'
    assert rejected["failure_reason"] == "Destino e segmentos não podem ser usados juntos."
    assert calls["call-network"]["status"] == "error" and calls["call-network"]["duration_ms"] == 20
    assert calls["call-network"]["total_tokens"] is None
    assert calls["call-no-usage"]["status"] == "completed" and calls["call-no-usage"]["total_tokens"] is None
    assert calls["call-pending"]["status"] == "pending" and calls["call-pending"]["total_tokens"] is None
    totals = lnav(log_file, ";SELECT sum(total_tokens) AS tokens, count(*) AS calls FROM trama_ai_calls")
    assert totals == [{"tokens": 15, "calls": 4}]


def test_log_screen_shows_fields_that_export_view_alone_does_not_validate(log_file, lnav):
    # write-view-to exporta os valores mesmo com hidden=true. write-screen-to
    # aplica a visibilidade real da interface: regressão das colunas vazias.
    screen = lnav(log_file, ":write-screen-to -", output=":write-screen-to -")
    assert "trama.movement" in screen and "movement.resolved" in screen
    assert "INFO" in screen and "ERROR" in screen and "#interact" in screen
    response_line = next(line for line in screen.splitlines() if "ai.response_received" in line and "12.5" in line)
    assert "10" in response_line and "5" in response_line
    assert "Plano inválido" in screen
    # Conteúdo específico aparece, mas o traceback extenso continua oculto.
    assert "Regras de teste" in screen and "Traceback" not in screen
    assert "in=" not in screen and "out=" not in screen


def test_event_previews_are_specific_and_conversation_text_is_not_lost(log_file, lnav):
    records = lnav(log_file, ";SELECT event, detail, preview, full_text FROM trama_events")
    movement = next(r for r in records if r["event"] == "movement.resolved")
    assert "custo=1.5 m" in movement["detail"] and '"x":2' in movement["detail"]
    assert "tokens" not in movement["detail"]
    attack = next(r for r in records if r["event"] == "combat.attack_resolved")
    assert "guard_1" in attack["detail"] and "dano=7" in attack["detail"]
    die = next(r for r in records if r["event"] == "dice.rolled")
    assert die["detail"] == "d20 = 19"
    player = next(r for r in records if r["event"] == "conversation.message_accepted")
    assert player["full_text"] == PLAYER_TEXT
    assert player["preview"].endswith("…") and "FIM-DO-JOGADOR" not in player["preview"]
    reply = next(r for r in records if r["event"] == "conversation.reply_delivered" and r["full_text"])
    assert reply["full_text"] == REPLY.text


def test_detail_command_opens_complete_text_and_updates_the_buffer(log_file, lnav):
    rows = lnav(log_file, ";SELECT log_line, event FROM trama_events WHERE full_text IS NOT NULL")
    player = next(r["log_line"] for r in rows if r["event"] == "conversation.message_accepted")
    reply = next(r["log_line"] for r in rows if r["event"] == "conversation.reply_delivered")
    full = lnav(log_file, f"|trama-detail {player}", output=":write-view-to -")
    assert PLAYER_TEXT in full
    assert '"text":' not in full  # Texto simples, sem envelope JSON.
    updated = lnav(log_file, [f"|trama-detail {player}", f"|trama-detail {reply}"], output=":write-view-to -")
    assert REPLY.text in updated and "FIM-DO-JOGADOR" not in updated


def test_detail_command_uses_focused_log_line_without_argument(log_file, lnav):
    line = lnav(log_file, ";SELECT log_line FROM trama_events WHERE event = 'conversation.message_accepted'")[0]["log_line"]
    full = lnav(log_file, [f";UPDATE lnav_top_view SET selection = {line}", "|trama-detail"], output=":write-view-to -")
    assert PLAYER_TEXT in full


def test_detail_command_explains_missing_old_text_and_shows_full_json(log_file, lnav):
    line = lnav(log_file, ";SELECT log_line FROM trama_events WHERE event = 'conversation.reply_delivered' AND full_text IS NULL")[0]["log_line"]
    full = lnav(log_file, f"|trama-detail {line}", output=":write-view-to -")
    assert "O texto não foi gravado" in full and '"has_on": true' in full


def test_lnav_config_is_really_isolated(tmp_path, lnav, log_file):
    lnav(log_file, ";SELECT 1")
    assert (tmp_path / "lnav-config/lnav").is_dir()


def test_error_table_preserves_cause_and_traceback(log_file, lnav):
    errors = lnav(log_file, ";SELECT * FROM trama_errors ORDER BY log_line")
    assert len(errors) == 2
    rejected = errors[0]
    assert rejected["level"] == "ERROR" and rejected["event"] == "ai.plan_rejected"
    assert rejected["reason"] == "Destino e segmentos não podem ser usados juntos."
    assert "Traceback" in rejected["traceback"]
    assert json.loads(rejected["causes"])[0]["type"] == "ValueError"


@pytest.mark.parametrize("script", ["trama-events", "trama-ai", "trama-errors"])
def test_table_commands_run_in_lnav(log_file, lnav, script):
    rows = lnav(log_file, "|" + script)
    assert rows and all("log_line" in row for row in rows)


@pytest.mark.parametrize("relative", ["trama.jsonl.1", "Trama/logs/caso-porta.jsonl"])
def test_rotations_and_custom_files_in_project_are_recognized(log_file, lnav, relative):
    path = log_file.parent / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(log_file, path)
    assert lnav(path, ";SELECT DISTINCT log_format FROM all_logs") == [{"log_format": "trama_log"}]


def test_unrelated_rust_logs_keep_their_original_format(tmp_path, lnav):
    path = tmp_path / "rust.jsonl"
    path.write_text(json.dumps({"timestamp": "2026-11-13T12:20:06.135+00:00", "level": "INFO",
                                "target": "example::module", "fields": {"message": "Rust example"}, "spans": []}) + "\n")
    assert lnav(path, ";SELECT DISTINCT log_format FROM all_logs") == [{"log_format": "rust_tracing_log"}]

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
import json
import logging

import pytest

from trama.observability import configure_logging, log_context, current_context
from trama.spatial import Position


def events(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_uniform_envelope_serialization_unicode_and_single_line(capture_logs):
    with capture_logs() as stream:
        logging.getLogger("trama.example").info("example.resolved", extra={"data": {
            "distance_meters": Decimal("1.500"), "position": Position(2, 3),
            "positions": frozenset({Position(2, 3)}), "text": "Ação\n[Off]"}})
    record, = events(stream)
    assert set(record) == {"schema_version", "timestamp", "level", "component", "event",
                           "session_id", "interaction_id", "operation_id", "ai_call_id", "data", "error"}
    assert record["schema_version"] == 1
    assert datetime.fromisoformat(record["timestamp"]).utcoffset().total_seconds() == 0
    assert record["component"] == "trama.example" and record["event"] == "example.resolved"
    assert record["level"] == "INFO" and record["session_id"] == "test-session"
    assert record["interaction_id"] is None and record["error"] is None
    assert record["data"] == {"distance_meters": "1.500", "position": {"x": 2, "y": 3},
                              "positions": [{"x": 2, "y": 3}], "text": "Ação\n[Off]"}


def test_credential_fields_strings_and_exception_chain_are_redacted(capture_logs):
    secret = "sk-example-secret-123456789"
    with capture_logs() as stream:
        logger = logging.getLogger("trama.example")
        logger.debug("example.credentials", extra={"data": {
            "api_key": "arbitrary-secret", "nested": {"Authorization": "Basic arbitrary"},
            "text": f"key={secret} Bearer abcdef123456", "client": object(), "total_tokens": 17}})
        try:
            try:
                raise ValueError(secret)
            except ValueError as error:
                raise RuntimeError("Falha de validação") from error
        except RuntimeError:
            logger.exception("example.failed")
    serialized = stream.getvalue()
    assert secret not in serialized and "arbitrary-secret" not in serialized and "abcdef123456" not in serialized
    first, second = events(stream)
    assert first["data"]["api_key"] == "[REDACTED]"
    assert first["data"]["nested"]["Authorization"] == "[REDACTED]"
    assert first["data"]["client"] == "<object>" and first["data"]["total_tokens"] == 17
    assert second["error"]["type"] == "RuntimeError"
    assert second["error"]["causes"] == [{"type": "ValueError", "message": "[REDACTED]"}]
    assert "Traceback" in second["error"]["traceback"]


def test_context_is_nested_restored_and_isolated_across_threads(capture_logs):
    logger = logging.getLogger("trama.example")
    with capture_logs() as stream:
        with log_context(interaction_id="parent"):
            with log_context(operation_id="child"):
                logger.info("example.inner")
            logger.info("example.outer")
        assert current_context() == {}

        def emit(identifier):
            with log_context(interaction_id=identifier):
                logger.info("example.thread")
            assert current_context() == {}

        with ThreadPoolExecutor(2) as pool:
            list(pool.map(emit, ("one", "two")))
        logger.info("example.after")
    records = events(stream)
    assert records[0]["operation_id"] == "child" and records[0]["interaction_id"] == "parent"
    assert records[1]["operation_id"] is None and records[1]["interaction_id"] == "parent"
    assert {r["interaction_id"] for r in records if r["event"] == "example.thread"} == {"one", "two"}
    assert records[-1]["interaction_id"] is None


def test_info_omits_debug_payloads_without_configuring_other_libraries(capture_logs):
    root = logging.getLogger()
    sdk = logging.getLogger("openai")
    previous = (root.level, root.handlers[:], sdk.level, sdk.handlers[:])
    with capture_logs("INFO") as stream:
        logger = logging.getLogger("trama.example")
        logger.debug("example.payload", extra={"data": {"prompt": "texto privado"}})
        logger.info("example.completed")
    assert "texto privado" not in stream.getvalue()
    assert [r["event"] for r in events(stream)] == ["example.completed"]
    assert previous == (root.level, root.handlers[:], sdk.level, sdk.handlers[:])


def test_handler_honors_info_even_when_a_component_enables_debug(capture_logs):
    logger = logging.getLogger("trama.example.override")
    previous = logger.level
    try:
        logger.setLevel(logging.DEBUG)
        with capture_logs("INFO") as stream:
            logger.debug("example.private_payload", extra={"data": {"prompt": "privado"}})
            logger.info("example.completed")
        assert [r["event"] for r in events(stream)] == ["example.completed"]
    finally:
        logger.setLevel(previous)


def test_rotating_file_keeps_valid_json_and_reconfiguration_does_not_duplicate(capture_logs, tmp_path):
    path = tmp_path / "trama.jsonl"
    with capture_logs(log_file=path, max_bytes=700, backup_count=2) as stream:
        logger = logging.getLogger("trama.example")
        for index in range(8):
            logger.info("example.rotation", extra={"data": {"index": index}})
        # Reabrir o mesmo arquivo fecha os próprios handlers anteriores.
        configure_logging(log_file=path, stream=stream, session_id="test-session", max_bytes=700, backup_count=2)
        logger.info("example.last")
    assert len(events(stream)) == 9
    assert path.exists() and path.with_suffix(".jsonl.1").exists() and path.with_suffix(".jsonl.2").exists()
    assert not path.with_suffix(".jsonl.3").exists()
    for file in tmp_path.iterdir():
        assert all(json.loads(line)["schema_version"] == 1 for line in file.read_text().splitlines())
    assert json.loads(path.read_text().splitlines()[-1])["event"] == "example.last"


@pytest.mark.parametrize("options", [{"level": "VERBOSE"}, {"max_bytes": 0}, {"backup_count": 0}])
def test_bad_configuration_is_rejected(options):
    with pytest.raises(ValueError):
        configure_logging(**options)


def test_arbitrary_values_are_not_accepted_as_correlation_context():
    with pytest.raises(ValueError):
        with log_context(api_key="do-not-store-secrets-in-context"):
            pass

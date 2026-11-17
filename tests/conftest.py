from collections import deque
from copy import copy, deepcopy
from dataclasses import replace
from contextlib import contextmanager
import io
import json
import logging

import pytest

from trama.observability import configure_logging, close_logging


def sourced_plan(plan, prompt, *, operations=None, kind="execute"):
    """Plano estruturado de adaptador simulado; não interpreta texto."""
    from trama.application.dialogue import split_speech
    from trama.application.intents import RequestPart
    from trama.application.authorization import step_operations
    ops = tuple(operations) if operations is not None else tuple(op for s in plan.steps for op in step_operations(s))
    return replace(plan, request_parts=(RequestPart(split_speech(prompt).on, kind, ops, tuple(range(len(plan.steps)))),))


def sourced_output(value, prompt, *, operations=None, kind="execute"):
    """Anotação explícita de saída simulada; casos negativos fornecem suas operações."""
    from trama.application.dialogue import split_speech
    value = deepcopy(value)
    if "request_parts" not in value and "steps" in value:
        ops = []
        for s in value["steps"]:
            op = "clarify" if s.get("clarification") else s.get("operation", "move")
            ops.append(op)
            if s.get("dash"):
                ops.append("dash")
            if s.get("use_inspiration"):
                ops.append("inspiration")
        value["request_parts"] = [{"text": split_speech(prompt).on, "kind": kind,
                                    "operations": ops if operations is None else operations,
                                    "step_indices": list(range(len(value["steps"])))}]
    return value


def scripted_responses(*responses, operations=None, kind="execute"):
    """SDK simulado com resposta e classificação conhecidas, sem analisar a frase."""
    sequence = iter(responses)
    def create(**kwargs):
        response = copy(next(sequence))
        value = json.loads(response.output_text)
        response.output_text = json.dumps(sourced_output(value, json.loads(kwargs["input"]).get("player_prompt", ""),
                                                          operations=operations, kind=kind))
        return response
    return create


@pytest.fixture
def capture_logs():
    @contextmanager
    def capture(level="DEBUG", **options):
        logger = logging.getLogger("trama")
        previous = (logger.handlers[:], logger.level, logger.propagate)
        stream = io.StringIO()
        configure_logging(level=level, stream=stream, session_id="test-session", **options)
        try:
            yield stream
        finally:
            close_logging()
            logger.handlers, logger.level, logger.propagate = previous
    return capture


@pytest.fixture
def dice():
    class ScriptedDice:
        def __init__(self, *values):
            self.values = deque(values)
            self.sides = []

        def roll(self, sides):
            self.sides.append(sides)
            assert self.values, f"Rolagem inesperada de d{sides}"
            value = self.values.popleft()
            assert 1 <= value <= sides
            return value

    return ScriptedDice


@pytest.fixture
def enter_turn_mode(dice):
    """Prepara conflito explícito para regressões que exercitam orçamento por turno."""
    def enter(session):
        from trama.application.encounter import Encounter
        from trama.characters import FighterSheet
        from trama.creatures import Creature
        from trama.spatial import Position

        if not session.creatures:
            position = next(Position(x, y) for y in reversed(range(session.grid.height))
                            for x in reversed(range(session.grid.width))
                            if Position(x, y) not in session.grid.blocked and Position(x, y) != session.state.position)
            session.creatures = (Creature("test_guard", "Guarda de teste", position),)
        enemies = tuple(session.encounter.sheets.get(c.id) or FighterSheet(c.id, c.name, level=1, subclass=None)
                        for c in session.creatures)
        session.encounter = Encounter(session.encounter.player_sheet, enemies, dice(20, 20, *([1] * len(enemies))))
        session.encounter.start(tuple(c.id for c in session.creatures))
        return session
    return enter


def world_actions(events):
    """Ações/checagens do Mundo, sem os registros automáticos de percepção."""
    return [event for event in events if event['operation'] != 'perception_detected']

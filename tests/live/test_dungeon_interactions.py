"""Regressão da interação real; contexto, instruções e adaptadores da aplicação."""

from copy import deepcopy
import json
import os
from pathlib import Path

import pytest
from openai import OpenAI

from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.dungeon import DungeonSession
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, MovementSegment
from trama.infrastructure.openai_intent_interpreter import DEFAULT_MODEL, OpenAIIntentInterpreter
from trama.infrastructure.openai_narrator import OpenAINarrator
from trama.infrastructure.openai_world_director import OpenAIWorldDirector

pytestmark = [pytest.mark.live,
    pytest.mark.skipif(os.environ.get('RUN_OPENAI_LIVE_TESTS') != '1',
                       reason='Defina RUN_OPENAI_LIVE_TESTS=1 para autorizar chamadas pagas.')]


@pytest.mark.parametrize('closed', [False, True], ids=['grade-ja-aberta', 'grade-fechada-aproximacao'])
def test_real_open_leave_and_observe_corridor(closed, tmp_path, capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    scenario = Path(__file__).resolve().parents[2] / 'pocs/simulador/dungeon.json'
    session = DungeonSession.from_data(json.loads(scenario.read_text()))
    conversation = Conversation(session)
    if closed:
        # Congela uma situação produzida pelo motor, sem prompt alternativo de teste.
        setup = conversation.execute(ActionPlan((MovementIntent((), False, '', 'gate_1'),
            DoorIntent('close', 'gate_1'), MovementIntent((MovementSegment('west', 2),), False, ''))))
        assert setup.status == 'completed'
        conversation.finish(Speech('Você fechou a grade da cela e voltou para junto da cama.'),
                            conversation.narration_context(report=setup))
    resources_before = deepcopy(session.encounter.states)
    speech = conversation.prepare('Eu abro a grade da cela devagar e saio para olhar o corredor.')
    interpretation_context = conversation.interpretation_context()
    model = os.environ.get('TRAMA_OPENAI_MODEL', DEFAULT_MODEL)
    with capture_logs() as stream:
        try:
            with OpenAI(timeout=30, max_retries=0) as client:
                plan = OpenAIIntentInterpreter(client, model).interpret(speech.on, interpretation_context)
                world_context = conversation.world_context(plan)
                world = OpenAIWorldDirector(client, model).decide(world_context)
                report = conversation.execute(plan, world)
                narration_context = conversation.narration_context(speech, report)
                reply = conversation.finish(OpenAINarrator(client, model).narrate(narration_context), narration_context)
        finally:
            (tmp_path / 'trace.jsonl').write_text(stream.getvalue())
    (tmp_path / 'interaction.json').write_text(json.dumps({
        'model': model, 'interpretation_context': interpretation_context, 'world_context': world_context,
        'execution': report.context(), 'narration_context': narration_context,
        'reply': {'on': reply.on, 'off': reply.off}}, ensure_ascii=False, indent=2))
    assert report.status == 'completed'
    assert report.unperformed_steps == 0
    assert session.scene.area_at(session.state.position).id == 'corridor'
    assert session._passage('gate_1').is_open
    assert narration_context['execution']['player_movement']['occurred']
    assert narration_context['perception']['current_place'] == 'Corredor'
    assert session.visibility.visible
    assert session.encounter.states == resources_before
    assert not session.dungeon.inventory
    assert session.dungeon.waits == 0
    assert not session.encounter.combat
    assert not session.state.dash_used
    assert reply.on


def test_real_investigation_enters_cell_contextually(tmp_path, capture_logs, dice):
    """Histórico narrado e prompts vêm dos adaptadores reais da aplicação."""
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    scenario = Path(__file__).resolve().parents[2] / 'pocs/simulador/dungeon.json'
    session = DungeonSession.from_data(json.loads(scenario.read_text()), roller=dice(20, 20))
    conversation = Conversation(session)
    setup = conversation.execute(ActionPlan((MovementIntent((), False, '', 'gate_4'), DoorIntent('open', 'gate_4'))))
    assert session.state.position.x == 7 and session.state.position.y == 9
    model = os.environ.get('TRAMA_OPENAI_MODEL', DEFAULT_MODEL)
    with capture_logs() as stream:
        try:
            with OpenAI(timeout=30, max_retries=0) as client:
                narrator = OpenAINarrator(client, model)
                setup_context = conversation.narration_context(report=setup)
                conversation.finish(narrator.narrate(setup_context), setup_context)
                speech = conversation.prepare('Eu checo a cela, procurando por algo útil.')
                interpretation_context = conversation.interpretation_context()
                plan = OpenAIIntentInterpreter(client, model).interpret(speech.on, interpretation_context)
                world_context = conversation.world_context(plan)
                world = OpenAIWorldDirector(client, model).decide(world_context)
                report = conversation.execute(plan, world)
                context = conversation.narration_context(speech, report)
                reply = conversation.finish(narrator.narrate(context), context)
        finally:
            (tmp_path / 'trace.jsonl').write_text(stream.getvalue())
    (tmp_path / 'investigation.json').write_text(json.dumps({
        'model': model, 'interpretation_context': interpretation_context, 'world_context': world_context,
        'execution': report.context(), 'narration_context': context,
        'reply': {'on': reply.on, 'off': reply.off}}, ensure_ascii=False, indent=2))
    assert report.status == 'completed'
    assert session.scene.area_at(session.state.position).id == 'cell_4'
    assert context['execution']['player_movement']['occurred']
    assert session.dungeon.discovered == {'longsword', 'cleaner_uniform'}
    assert not session.dungeon.inventory
    assert not session.encounter.combat
    assert reply.on

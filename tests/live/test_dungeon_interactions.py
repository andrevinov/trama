"""Regressão da interação real; contexto, instruções e adaptadores da aplicação."""

from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from trama.application.conversation import Conversation
from trama.application.scenarios import load_session
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, MovementSegment
from trama.infrastructure.openai_services import open_services

pytestmark = [pytest.mark.live,
    pytest.mark.skipif(os.environ.get('RUN_OPENAI_LIVE_TESTS') != '1',
                       reason='Defina RUN_OPENAI_LIVE_TESTS=1 para autorizar chamadas pagas.')]


@pytest.mark.parametrize('closed', [False, True], ids=['grade-ja-aberta', 'grade-fechada-aproximacao'])
def test_real_open_leave_and_observe_corridor(closed, tmp_path, capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    scenario = Path(__file__).resolve().parents[2] / 'pocs/simulador/dungeon.json'
    session = load_session(scenario)
    conversation = Conversation(session)
    if closed:
        # Congela uma situação produzida pelo motor, sem prompt alternativo de teste.
        setup = conversation.execute(ActionPlan((MovementIntent((), False, '', 'gate_1'),
            DoorIntent('close', 'gate_1'), MovementIntent((MovementSegment('west', 2),), False, ''))))
        assert setup.status == 'completed'
    resources_before = deepcopy(session.encounter.states)
    speech = conversation.prepare('Eu abro a grade da cela devagar e saio para olhar o corredor.')
    interpretation_context = conversation.interpretation_context()
    with capture_logs() as stream:
        try:
            with open_services() as services:
                plan = services.interpreter.interpret(speech.on, interpretation_context)
                world_context = conversation.world_context(plan)
                world = services.world_director.decide(world_context)
                report = conversation.execute(plan, world)
                narration_context = conversation.narration_context(speech, report)
                reply = conversation.finish(services.narrator.narrate(narration_context), narration_context)
        finally:
            (tmp_path / 'trace.jsonl').write_text(stream.getvalue())
    (tmp_path / 'interaction.json').write_text(json.dumps({
        'model': services.config.model, 'configuration': services.metadata, 'interpretation_context': interpretation_context, 'world_context': world_context,
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
    session = load_session(scenario, roller=dice(20, 20))
    conversation = Conversation(session)
    setup = conversation.execute(ActionPlan((MovementIntent((), False, '', 'gate_4'), DoorIntent('open', 'gate_4'))))
    assert session.state.position.x == 7 and session.state.position.y == 9
    with capture_logs() as stream:
        try:
            with open_services() as services:
                narrator = services.narrator
                setup_context = conversation.narration_context(report=setup)
                conversation.finish(narrator.narrate(setup_context), setup_context)
                speech = conversation.prepare('Eu checo a cela, procurando por algo útil.')
                interpretation_context = conversation.interpretation_context()
                plan = services.interpreter.interpret(speech.on, interpretation_context)
                world_context = conversation.world_context(plan)
                world = services.world_director.decide(world_context)
                report = conversation.execute(plan, world)
                context = conversation.narration_context(speech, report)
                reply = conversation.finish(narrator.narrate(context), context)
        finally:
            (tmp_path / 'trace.jsonl').write_text(stream.getvalue())
    (tmp_path / 'investigation.json').write_text(json.dumps({
        'model': services.config.model, 'configuration': services.metadata, 'interpretation_context': interpretation_context, 'world_context': world_context,
        'execution': report.context(), 'narration_context': context,
        'reply': {'on': reply.on, 'off': reply.off}}, ensure_ascii=False, indent=2))
    assert report.status == 'completed'
    assert session.scene.area_at(session.state.position).id == 'cell_4'
    assert context['execution']['player_movement']['occurred']
    assert session.dungeon.discovered == {'longsword', 'cleaner_uniform'}
    assert not session.dungeon.inventory
    assert not session.encounter.combat
    assert reply.on

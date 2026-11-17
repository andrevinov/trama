"""Verifica fixtures e critérios da suíte live sem chamar serviços externos."""

from pathlib import Path
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

from conftest import sourced_output
import runpy

import pytest

from trama.application.intents import ActionPlan, RuleIntent, ScenarioIntent
from trama.application.situations import SituationError
from trama.infrastructure import openai_services

SUPPORT = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'live/test_contextual_movement.py'))
CASES = SUPPORT['CASES']


def scripted_output(case, parameters, *, npc_behavior='wait'):
    """Saídas explícitas de transporte local, sem reinterpretar a frase."""
    task = parameters['text']['format']['name']
    context = json.loads(parameters['input'])
    if task == 'narrator_reply':
        return {'on': 'Você observa os fatos registrados no local.', 'off': ''}
    if task == 'world_response':
        if context['phase'] != 'npc_turn' or npc_behavior == 'wait':
            return {'reactions': []}
        actions = [dict(actor_id='guard_1', operation='move', text='O guarda se aproxima.',
                        target_id=None, destination={'column': 9, 'row': 7}, weapon='longsword'),
                   dict(actor_id='guard_1', operation='attack', text='O guarda ataca.',
                        target_id='player', destination=None, weapon='longsword')]
        if npc_behavior == 'invalid_attack':
            actions = actions[1:]
        elif npc_behavior == 'reaction':
            actions = [actions[0], {**actions[0], 'text': 'O guarda recua.',
                                    'destination': {'column': 11, 'row': 4}}]
        return {'reactions': [dict(step_index=0, after_squares=0, actions=actions,
                                  interrupt=False, reason='', check=None)]}
    expected = case['expected']
    if expected in {'attack', 'short_movement', 'enemy_first'}:
        step = dict(operation='attack', target_id='guard_1', weapon='longsword', use_inspiration=False)
    elif expected == 'take':
        step = dict(operation='take', target_id='longsword')
    else:
        step = dict(operation='investigate', target_id='bathroom' if expected == 'opportunity' else 'cell_4',
                    allow_approach=expected != 'no_movement')
    return sourced_output({'steps': [step]}, case['prompt'])


def install_client(case, monkeypatch, *, npc_behavior='wait'):
    client = Mock()
    client.base_url = 'https://offline.test'
    def create(**parameters):
        return SimpleNamespace(status='completed', output=[], usage=None,
            output_text=json.dumps(scripted_output(case, parameters, npc_behavior=npc_behavior)))
    client.responses.create.side_effect = create
    monkeypatch.setattr(openai_services, 'OpenAI', lambda **kwargs: client)
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-unused-key')
    return client


def run_case(case, monkeypatch, tmp_path, capture_logs, *, npc_behavior='wait'):
    client = install_client(case, monkeypatch, npc_behavior=npc_behavior)
    monkeypatch.setenv('TRAMA_CONTEXTUAL_ARTIFACTS', str(tmp_path))
    SUPPORT['test_live_contextual_movement'](case, capture_logs)
    path = next(tmp_path.rglob('result.json'))
    return client, json.loads(path.read_text()), path


@pytest.mark.parametrize('case', CASES, ids=[case['id'] for case in CASES])
def test_frozen_live_scenario_and_criteria_are_executable_offline(case, monkeypatch, tmp_path, capture_logs):
    client, evidence, path = run_case(case, monkeypatch, tmp_path, capture_logs)
    assert evidence['outcome'] == 'passed' and evidence['errors'] == []
    assert [r['label'] for r in evidence['runs']] == ['opening', 'action']
    stages = [r['stage'] for r in evidence['runs'][1]['requests']]
    assert stages == ['interpret', 'world', *(['npc_turn'] if case['expected'] == 'enemy_first' else []), 'narrate']
    assert client.responses.create.call_count == (5 if case['expected'] == 'enemy_first' else 4)
    assert evidence['call_budget']['used'] == client.responses.create.call_count
    assert not evidence['dice_pending']
    assert path.with_name('trace.jsonl').exists()
    client.close.assert_called_once()


def test_investigation_live_keeps_exact_history_from_failed_session():
    case = next(case for case in CASES if case['id'] == 'investigar-cela-do-log')
    conversation, _ = SUPPORT['build_case'](case)
    speech = conversation.prepare(case['prompt'])
    context = conversation.interpretation_context()
    assert speech.on == 'Eu checo a cela, procurando por algo útil.'
    assert context['character']['column'] == 8
    assert context['character']['row'] == 10
    assert context['character']['current_area'] == 'corridor'
    assert context['recent_messages'][-2]['role'] == 'narrator'
    assert context['recent_messages'][-2]['on'].startswith('Você percorre 6 m pelo corredor até a Cela 4.')
    assert context['recent_messages'][-1]['on'] == speech.on


def test_live_oracle_detects_original_missing_contextual_movement():
    case = next(case for case in CASES if case['id'] == 'investigar-cela-do-log')
    conversation, roller = SUPPORT['build_case'](case)
    before = SUPPORT['snapshot'](conversation.session)
    plan = ActionPlan((ScenarioIntent('investigate', 'cell_4', allow_approach=False),))
    report = conversation.execute(plan)
    errors = SUPPORT['evaluate'](case, before, SUPPORT['snapshot'](conversation.session), report, plan, roller)
    assert errors
    assert any('Não entrou na Cela 4' in error for error in errors)


def test_low_movement_fixture_spends_actual_movement_and_preserves_the_attack_action(capture_logs):
    import json
    case = next(case for case in CASES if case['expected'] == 'short_movement')
    with capture_logs() as stream:
        conversation, roller = SUPPORT['build_case'](case)
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    moves = [e['data'] for e in events if e['event'] == 'movement.resolved']
    assert moves[-1]['cost_meters'] == '1.5'
    assert sum(float(m['cost_meters']) for m in moves[-5:]) == 7.5
    assert conversation.session.state.spent_meters == 7.5
    assert conversation.session.state.remaining_meters == 1.5
    assert not conversation.session.budget.action_used
    assert len(roller.used) == 7


def test_opportunity_fixture_breaks_disguise_by_real_perception_and_initiative(capture_logs):
    import json
    case = next(case for case in CASES if case['expected'] == 'opportunity')
    with capture_logs() as stream:
        conversation, roller = SUPPORT['build_case'](case)
    report = conversation.narration_context()['previous_execution']['execution']
    check = next(e for e in report['reactions'] if e['operation'] == 'check')
    assert check['actor_id'] == 'guard_1' and check['skill'] == 'perception'
    assert check['passed'] and check['dc'] == 10 and check['dice'] == [20]
    assert any(e['operation'] == 'start_conflict' for e in report['reactions'])
    assert [e['operation'] for e in report['events']] == ['drop', 'take']
    assert conversation.session.dungeon.disguise == 'failed'
    assert conversation.session.dungeon.guard_alert
    assert not conversation.session.dungeon.sword_concealed
    assert len(roller.used) == 8
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert any(e['event'] == 'encounter.started' for e in events)


@pytest.mark.parametrize('defect', ['missing_walk', 'missing_gate_open', 'impossible_hp', 'unknown_condition', 'wrong_die', 'failed_investigation'])
def test_invalid_preparation_fails_before_interacting_with_any_model(defect):
    case = deepcopy(next(case for case in CASES if case['expected'] == 'short_movement'))
    if defect == 'missing_walk':
        case['setup'].remove('spend_seven_and_half_meters')
    elif defect == 'missing_gate_open':
        case['setup'][1] = 'approach_closed_storage'
    elif defect == 'impossible_hp':
        case['preconditions']['resources.player.hp'] = 999
    elif defect == 'unknown_condition':
        case['preconditions']['resources.player.unknown'] = True
    elif defect == 'wrong_die':
        case['rolls'][0] = [8, 8]
    else:
        case['rolls'][1] = [20, 1]
    with pytest.raises(SituationError):
        SUPPORT['build_case'](case)


def test_fixed_dice_reject_invalid_values_types_and_unplanned_rolls():
    for rolls in ([[20, 21]], [[20, True]], [[1, 1]], [[8]], [[20, '20']]):
        with pytest.raises(ValueError):
            SUPPORT['FrozenRoller'](rolls)
    roller = SUPPORT['FrozenRoller']([[20, 10]])
    with pytest.raises(SituationError, match='Esperava d20'):
        roller.roll(8)
    assert not roller.used and list(roller.pending) == [(20, 10)]
    assert roller.roll(20) == 10
    with pytest.raises(SituationError, match='não prevista'):
        roller.roll(20)


def test_live_runner_saves_real_adapter_contexts_and_correlated_logs_offline(monkeypatch, tmp_path, capture_logs):
    """Smoke do aparato: apenas o transporte é simulado, sem chamadas pagas."""
    import json
    from types import SimpleNamespace
    case = next(case for case in CASES if case['id'] == 'investigar-cela-do-log')
    answers = iter([
        {'on': 'Você ouve sua cela abrir.', 'off': ''},
        {'request_parts': [{'text': case['prompt'], 'kind': 'execute', 'operations': ['investigate'], 'step_indices': [0]}],
         'steps': [{'operation': 'investigate', 'target_id': 'cell_4', 'allow_approach': True}]},
        {'reactions': []},
        {'on': 'Você entra na cela e investiga os panos e a cama.', 'off': ''},
    ])
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(status='completed', output=[], output_text=json.dumps(next(answers)), usage=None)
    class OfflineClient:
        responses = SimpleNamespace(create=create)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def close(self):
            pass
    run = SUPPORT['test_live_contextual_movement']
    monkeypatch.setattr(openai_services, 'OpenAI', lambda **kwargs: OfflineClient())
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-not-used')
    monkeypatch.setenv('TRAMA_CONTEXTUAL_ARTIFACTS', str(tmp_path))
    run(case, capture_logs)
    results = list(tmp_path.rglob('result.json'))
    assert len(results) == 1 and len(calls) == 4
    evidence = json.loads(results[0].read_text())
    assert evidence['stage'] == 'passed'
    assert evidence['after']['area'] == 'cell_4'
    assert evidence['interpretation_context']['recent_messages'][-1]['on'] == case['prompt']
    records = [json.loads(line) for line in results[0].with_name('trace.jsonl').read_text().splitlines()]
    assert len([r for r in records if r['event'] == 'ai.request_payload']) == 4
    assert {r['session_id'] for r in records} == {evidence['session_id']}
    expected_ids = {run['interaction_id'] for run in evidence['runs']} | {evidence['preparation_interaction_id'], None}
    assert {r['interaction_id'] for r in records} <= expected_ids
    assert len({run['interaction_id'] for run in evidence['runs']}) == 2


def test_live_runner_saves_partial_evidence_when_provider_fails(monkeypatch, tmp_path, capture_logs):
    import json
    from types import SimpleNamespace
    case = next(case for case in CASES if case['id'] == 'investigar-cela-do-log')
    def fail(**kwargs):
        raise RuntimeError('Falha de transporte simulada, sem rede.')
    class OfflineClient:
        responses = SimpleNamespace(create=fail)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def close(self):
            pass
    run = SUPPORT['test_live_contextual_movement']
    monkeypatch.setattr(openai_services, 'OpenAI', lambda **kwargs: OfflineClient())
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-not-used')
    monkeypatch.setenv('TRAMA_CONTEXTUAL_ARTIFACTS', str(tmp_path))
    with pytest.raises(AssertionError, match='Falha de transporte'):
        run(case, capture_logs)
    result = next(tmp_path.rglob('result.json'))
    evidence = json.loads(result.read_text())
    assert evidence['stage'] == 'opening'
    assert evidence['outcome'] == 'flow_failed'
    assert evidence['flow_error']['type'] == 'RuntimeError'
    assert evidence['initial']['area'] == 'corridor'
    assert evidence['after']['position'] == evidence['initial']['position']
    assert evidence['runs'][0]['requests'][0]['is_error']
    assert result.with_name('trace.jsonl').is_file()


def test_guard_winning_initiative_can_move_and_attack_before_returning_control(monkeypatch, tmp_path, capture_logs):
    case = next(c for c in CASES if c['expected'] == 'enemy_first')
    client, evidence, _ = run_case(case, monkeypatch, tmp_path, capture_logs, npc_behavior='attack')
    assert evidence['after']['combat']['active_id'] == 'player'
    assert evidence['after']['position'] == evidence['before']['position']
    assert evidence['after']['resources']['player']['hp'] == 28  # O d20 opcional fixado em 1 erra.
    assert evidence['optional_world_dice_used'] == [[20, 1]]
    assert not evidence['optional_world_dice_pending']
    assert any(e['operation'] == 'attack' and e['actor_id'] == 'guard_1' for e in evidence['execution']['reactions'])
    assert client.responses.create.call_count == 5


def test_recovered_guard_failure_does_not_pass_as_legal_initiative_success(monkeypatch, tmp_path, capture_logs):
    case = next(c for c in CASES if c['expected'] == 'enemy_first')
    client = install_client(case, monkeypatch, npc_behavior='invalid_attack')
    monkeypatch.setenv('TRAMA_CONTEXTUAL_ARTIFACTS', str(tmp_path))
    with pytest.raises(AssertionError, match='resposta do guarda falhou'):
        SUPPORT['test_live_contextual_movement'](case, capture_logs)
    evidence = json.loads(next(tmp_path.rglob('result.json')).read_text())
    assert evidence['outcome'] == 'failed' and evidence['stage'] == 'evaluation'
    assert evidence['after']['combat']['active_id'] == 'player'
    assert any(e.get('fallback') == 'end_turn' for e in evidence['execution']['reactions'])
    assert any(f['actor_id'] == 'guard_1' for f in evidence['execution']['failures'])
    assert client.responses.create.call_count == 5


@pytest.mark.parametrize('limit', [0, 2, 3])
def test_sdk_budget_interrupts_before_next_call_and_never_marks_partial_execution_passed(limit, monkeypatch, tmp_path, capture_logs):
    case = deepcopy(next(c for c in CASES if c['expected'] == 'investigate'))
    case['max_sdk_calls'] = limit
    client = install_client(case, monkeypatch)
    monkeypatch.setenv('TRAMA_CONTEXTUAL_ARTIFACTS', str(tmp_path))
    with pytest.raises(AssertionError, match='orçamento'):
        SUPPORT['test_live_contextual_movement'](case, capture_logs)
    evidence = json.loads(next(tmp_path.rglob('result.json')).read_text())
    assert evidence['outcome'] == 'inconclusive' and evidence['call_budget']['exceeded']
    assert client.responses.create.call_count == evidence['call_budget']['used'] == limit
    if limit == 3:
        assert evidence['after']['area'] == 'cell_4'
        assert evidence['after']['discovered'] == ['cleaner_uniform', 'longsword']
    else:
        assert evidence['after']['area'] == 'corridor' and not evidence['after']['discovered']


@pytest.mark.parametrize('limit', [3, 5])
def test_interpreter_correction_consumes_same_sdk_budget(limit, monkeypatch, tmp_path, capture_logs):
    case = deepcopy(next(c for c in CASES if c['expected'] == 'investigate'))
    case['max_sdk_calls'] = limit
    client = install_client(case, monkeypatch)
    valid = client.responses.create.side_effect
    first = True

    def create(**parameters):
        nonlocal first
        if parameters['text']['format']['name'] == 'action_plan' and first:
            first = False
            bad = {'steps': [dict(operation='second_wind', target_id=None, weapon='greatsword', use_inspiration=False)],
                   'request_parts': [dict(text=case['prompt'], kind='execute', operations=['investigate'], step_indices=[0])]}
            return SimpleNamespace(status='completed', output=[], usage=None, output_text=json.dumps(bad))
        return valid(**parameters)

    client.responses.create.side_effect = create
    monkeypatch.setenv('TRAMA_CONTEXTUAL_ARTIFACTS', str(tmp_path))
    if limit == 3:
        with pytest.raises(AssertionError, match='orçamento'):
            SUPPORT['test_live_contextual_movement'](case, capture_logs)
    else:
        SUPPORT['test_live_contextual_movement'](case, capture_logs)
    evidence = json.loads(next(tmp_path.rglob('result.json')).read_text())
    assert client.responses.create.call_count == evidence['call_budget']['used'] == limit
    assert evidence['outcome'] == ('inconclusive' if limit == 3 else 'passed')
    attempts = [c.kwargs for c in client.responses.create.call_args_list if c.kwargs['text']['format']['name'] == 'action_plan']
    assert len(attempts) == 2
    assert evidence['after']['resources']['player']['second_wind_uses'] == 2


@pytest.mark.parametrize('declare_choice', [False, True])
def test_player_opportunity_is_never_declined_without_declared_input(declare_choice, monkeypatch, tmp_path, capture_logs):
    case = deepcopy(next(c for c in CASES if c['expected'] == 'enemy_first'))
    case['choices'] = [False] if declare_choice else []
    case['max_sdk_calls'] = 7
    client = install_client(case, monkeypatch, npc_behavior='reaction')
    monkeypatch.setenv('TRAMA_CONTEXTUAL_ARTIFACTS', str(tmp_path))
    if declare_choice:
        SUPPORT['test_live_contextual_movement'](case, capture_logs)
    else:
        with pytest.raises(AssertionError, match='escolha declarada'):
            SUPPORT['test_live_contextual_movement'](case, capture_logs)
    evidence = json.loads(next(tmp_path.rglob('result.json')).read_text())
    assert evidence['outcome'] == ('passed' if declare_choice else 'inconclusive')
    assert evidence['after']['pending_opportunity'] is not declare_choice
    assert evidence['choices_used'] == ([False] if declare_choice else [])
    assert any(r['awaiting_reaction'] for r in evidence['runs'])
    assert client.responses.create.call_count == (6 if declare_choice else 5)


def test_precondition_failure_stops_before_opening_or_any_sdk_call(monkeypatch, tmp_path, capture_logs):
    case = deepcopy(next(c for c in CASES if c['expected'] == 'investigate'))
    case['preconditions']['resources.player.hp'] = 999
    client = install_client(case, monkeypatch)
    monkeypatch.setenv('TRAMA_CONTEXTUAL_ARTIFACTS', str(tmp_path))
    with pytest.raises(SituationError, match='pré-condição'):
        SUPPORT['test_live_contextual_movement'](case, capture_logs)
    evidence = json.loads(next(tmp_path.rglob('result.json')).read_text())
    assert evidence['stage'] == 'preparation' and evidence['outcome'] == 'failed'
    assert not evidence['runs'] and evidence['call_budget']['used'] == 0
    client.responses.create.assert_not_called()

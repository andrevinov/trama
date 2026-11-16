"""Verifica fixtures e critérios da suíte live sem chamar serviços externos."""

from pathlib import Path
import runpy

import pytest

from trama.application.intents import ActionPlan, RuleIntent, ScenarioIntent

SUPPORT = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'live/test_contextual_movement.py'))
CASES = SUPPORT['CASES']


@pytest.mark.parametrize('case', CASES, ids=[case['id'] for case in CASES])
def test_frozen_live_scenario_and_criteria_are_executable_offline(case):
    conversation, roller = SUPPORT['build_case'](case)
    before = SUPPORT['snapshot'](conversation.session)
    expected = case['expected']
    if expected == 'take':
        step = ScenarioIntent('take', 'longsword')
    elif expected in {'attack', 'short_movement', 'enemy_first'}:
        step = RuleIntent('attack', 'guard_1', 'longsword')
    elif expected == 'opportunity':
        step = ScenarioIntent('investigate', 'bathroom')
    else:
        step = ScenarioIntent('investigate', 'cell_4', allow_approach=expected != 'no_movement')
    plan = ActionPlan((step,))
    report = conversation.execute(plan)
    after = SUPPORT['snapshot'](conversation.session)
    errors = SUPPORT['evaluate'](case, before, after, report, plan, roller)
    assert not errors, errors


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


def test_live_runner_saves_real_adapter_contexts_and_correlated_logs_offline(monkeypatch, tmp_path, capture_logs):
    """Smoke do aparato: apenas o transporte é simulado, sem chamadas pagas."""
    import json
    from types import SimpleNamespace
    case = next(case for case in CASES if case['id'] == 'investigar-cela-do-log')
    answers = iter([
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
    run = SUPPORT['test_live_contextual_movement']
    monkeypatch.setitem(run.__globals__, 'OpenAI', lambda **kwargs: OfflineClient())
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-not-used')
    monkeypatch.setenv('TRAMA_CONTEXTUAL_ARTIFACTS', str(tmp_path))
    run(case, capture_logs)
    results = list(tmp_path.rglob('result.json'))
    assert len(results) == 1 and len(calls) == 3
    evidence = json.loads(results[0].read_text())
    assert evidence['stage'] == 'passed'
    assert evidence['after']['area'] == 'cell_4'
    assert evidence['interpretation_context']['recent_messages'][-1]['on'] == case['prompt']
    records = [json.loads(line) for line in results[0].with_name('trace.jsonl').read_text().splitlines()]
    assert len([r for r in records if r['event'] == 'ai.request_payload']) == 3
    assert {r['session_id'] for r in records} == {evidence['session_id']}
    assert {r['interaction_id'] for r in records} == {evidence['interaction_id']}


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
    run = SUPPORT['test_live_contextual_movement']
    monkeypatch.setitem(run.__globals__, 'OpenAI', lambda **kwargs: OfflineClient())
    monkeypatch.setenv('OPENAI_API_KEY', 'offline-not-used')
    monkeypatch.setenv('TRAMA_CONTEXTUAL_ARTIFACTS', str(tmp_path))
    with pytest.raises(RuntimeError, match='Falha de transporte'):
        run(case, capture_logs)
    result = next(tmp_path.rglob('result.json'))
    evidence = json.loads(result.read_text())
    assert evidence['stage'] == 'interpretation'
    assert evidence['exception']['type'] == 'RuntimeError'
    assert evidence['before']['area'] == 'corridor'
    assert evidence['after']['position'] == evidence['before']['position']
    assert evidence['interpretation_context']
    assert result.with_name('trace.jsonl').is_file()

"""Controles positivos/negativos independentes; sem rede ou mutação das regras.

As saídas do SDK são explícitas. Cenário, preparação, composição, UI/runner,
adaptadores e efeitos continuam reais. Cópias defeituosas são só observações
entregues aos critérios; nunca são aplicadas à sessão.
"""

from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import runpy
from types import SimpleNamespace
from unittest.mock import Mock

import pygame
import pytest

from conftest import sourced_output, judged_output, without_correlation_ids
from trama.application.intents import RuleIntent
from trama.bootstrap import open_game
from trama.ui.movement_window import MovementWindow, WINDOW_SIZE

ROOT = Path(__file__).resolve().parents[2]
LIVE = runpy.run_path(str(ROOT / 'tests/live/test_contextual_movement.py'))
SURGE_PROMPT = 'Eu uso Surto de Ação e, com a ação extra, ataco o Guarda 1 novamente com a espada grande.'
FALSE_MOVE = 'Você percorre 3 m, entra na Cela 4 e investiga os panos.'


@pytest.fixture
def screen(monkeypatch):
    monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
    pygame.display.init()
    pygame.font.init()
    yield pygame.display.set_mode(WINDOW_SIZE)
    pygame.quit()


def case_for(expected):
    return deepcopy(next(c for c in LIVE['CASES'] if c['expected'] == expected))


def surge_snapshot(session):
    return {'position': [session.state.position.x + 1, session.state.position.y + 1],
            'combat': session.combat_context(),
            'resources': {id: asdict(state) for id, state in session.encounter.states.items()},
            'budgets': {id: asdict(budget) for id, budget in session.encounter.budgets.items()}}


def surge_attack_errors(observed):
    """Expectativas literais do caso, sem usar regras para calcular o esperado."""
    after, report = observed['after'], observed['report']
    errors = []
    if [e['operation'] for e in report.events] != ['action_surge', 'attack']:
        errors.append('Faltou executar Surto de Ação seguido do ataque pedido.')
    attacks = [e for e in report.events if e['operation'] == 'attack']
    if len(attacks) != 1 or attacks[0].get('target_id') != 'guard_1' or attacks[0].get('damage') != 3:
        errors.append('Faltou o ataque único contra o Guarda 1 com 3 de dano.')
    if after['resources']['guard_1']['hp'] != 6:
        errors.append('O guarda deveria terminar com 6 PV.')
    if after['resources']['player']['action_surge_uses'] != 0:
        errors.append('Surto de Ação deveria consumir seu uso.')
    if after['budgets']['player']['extra_actions'] != 0 or not after['budgets']['player']['action_used']:
        errors.append('A ação extra deveria ter sido consumida, com a ação normal já usada.')
    if after['position'] != [15, 6] or after['combat']['active_id'] != 'player':
        errors.append('Posição e vez do jogador deveriam ser preservadas.')
    return errors


def sdk_output(case, parameters, control):
    """Transporte local com plano conhecido; não interpreta português."""
    task = parameters['text']['format']['name']
    payload = json.loads(parameters['input'])
    if task == 'narrator_reply':
        return {'on': FALSE_MOVE if control == 'narrated_only' and payload['phase'] != 'initial'
                else 'Descrição local dos fatos.', 'off': ''}
    if task == 'world_response':
        return {'reactions': []}  # NPC espera legalmente; o fluxo encerra seu turno.
    if case == 'surge':
        steps = [dict(operation='action_surge', target_id=None, weapon='greatsword', use_inspiration=False)]
        if control != 'surge_only':
            steps.append(dict(operation='attack', target_id='guard_1', weapon='greatsword', use_inspiration=False))
        prompt = SURGE_PROMPT
    else:
        prompt = case['prompt']
        expected = case['expected']
        if control == 'narrated_only':
            steps = [dict(operation='look', text='Observo a cela daqui.')]
        elif expected == 'enemy_first':
            steps = [dict(operation='attack', target_id='guard_1', weapon='longsword', use_inspiration=False)]
        else:
            steps = [dict(operation='investigate', target_id='bathroom' if expected == 'opportunity' else 'cell_4',
                          allow_approach=control != 'no_approach')]
    return sourced_output({'steps': steps}, prompt)


def pump(window):
    """Somente agenda/entrega da UI, sem escolher etapas do jogo."""
    for _ in range(12):
        if not window.pending:
            return
        delivery = window.results.get(timeout=3)
        window.results.put(delivery)
        window.poll()
    pytest.fail('A janela não concluiu a agenda no limite local.')


def observe(entry, case, control, tmp_path, capture_logs):
    client = Mock()
    client.base_url = 'https://offline.test'
    def create(**parameters):
        return SimpleNamespace(status='completed', output=[], usage=None,
                               output_text=json.dumps(judged_output(sdk_output(case, parameters, control), parameters)))
    client.responses.create.side_effect = create
    surge = case == 'surge'
    if surge:
        data = json.loads((ROOT / 'tests/fixtures/scenarios/legacy_cell_and_guards.json').read_text())
        data['start'] = [14, 5]
        next(p for p in data['passages'] if p['id'] == 'guard_door')['is_open'] = True
        roller = LIVE['FrozenRoller']([[20, 20], [20, 19], [20, 1], [20, 1], [20, 1]])
        snapshot = surge_snapshot
        prompt = SURGE_PROMPT
    else:
        data = LIVE['case_data'](case)
        roller = LIVE['FrozenRoller'](case['rolls'], case.get('optional_world_rolls', []))
        snapshot = LIVE['snapshot']
        prompt = case['prompt']
    with capture_logs(log_file=tmp_path / f'{entry}-{control}.jsonl'), open_game(data, roller=roller, client=client) as game:
        plans = []
        interpret = game.services.interpreter.interpret
        def record_plan(prompt, context):
            plan = interpret(prompt, context)
            plans.append(deepcopy(plan))
            return plan
        # Espia transparente: preserva o retorno real do adaptador, sem recriar
        # o plano a partir do roteiro nem substituir interpretação/validação.
        game.services.interpreter.interpret = record_plan
        if surge:
            game.flow.session.execute(RuleIntent('start_combat'))
            game.flow.session.execute(RuleIntent('attack', 'guard_1', 'greatsword'))
            initial = snapshot(game.flow.session)
            assert initial['resources']['guard_1']['hp'] == 9
            assert initial['resources']['player']['action_surge_uses'] == 1
            assert initial['budgets']['player']['action_used']
        else:
            LIVE['prepare_case'](case, game.flow.conversation, roller, with_history=False)
        if entry == 'window':
            services = game.services
            window = MovementWindow(game.flow.session, services.interpreter, services.config.model,
                                    services.narrator, services.world_director, flow=game.flow)
            window.start()
            pump(window)
        else:
            assert game.runner.start().status == 'completed'
        if not surge:
            LIVE['restore_history'](case, game.flow.conversation)
        before = snapshot(game.flow.session)
        if entry == 'window':
            window.input.insert(prompt)
            window.submit()
            pump(window)
        else:
            game.runner.submit(prompt)
        assert game.flow.error is None
        assert game.flow.status == 'completed'
        observed = {'before': before, 'after': snapshot(game.flow.session), 'report': deepcopy(game.flow.report),
                    'reply': game.flow.reply, 'roller': roller,
                    'requests': deepcopy([c.kwargs for c in client.responses.create.call_args_list])}
        assert len(plans) == 1
        observed['plan'] = plans[0]
        assert game.flow.session.state.position.x + 1 == observed['after']['position'][0]
        return observed


def errors_for(case, observed):
    if case == 'surge':
        return surge_attack_errors(observed)
    return LIVE['evaluate'](case, observed['before'], observed['after'], observed['report'],
                            observed['plan'], observed['roller'])


def normalized(value):
    return without_correlation_ids(value)


def write_proof(path, control, observations, errors):
    evidence = {'control': control, 'errors': errors, 'observations': {}}
    for entry, observed in observations.items():
        evidence['observations'][entry] = {
            'before': observed['before'], 'after': observed['after'],
            'execution': observed['report'].context(), 'reply': asdict(observed['reply']),
            'plan': asdict(observed['plan']), 'sdk_calls': len(observed['requests'])}
    (path / 'proof.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')


@pytest.mark.parametrize('scenario', ['investigate', 'enemy_first', 'opportunity', 'surge'])
def test_real_ui_and_runner_share_requests_and_satisfy_independent_positive_criteria(scenario, screen, tmp_path, capture_logs):
    case = 'surge' if scenario == 'surge' else case_for(scenario)
    graphical = observe('window', case, 'positive', tmp_path, capture_logs)
    headless = observe('runner', case, 'positive', tmp_path, capture_logs)
    for observed in (graphical, headless):
        assert errors_for(case, observed) == []
        assert not observed['roller'].pending
        narration = json.loads(observed['requests'][-1]['input'])
        if scenario == 'investigate':
            assert narration['execution']['player_movement']['occurred'] is True
            assert narration['execution']['player_movement']['traveled_meters'] == 3
            assert narration['character']['current_area'] == 'cell_4'
        elif scenario == 'enemy_first':
            turns = [json.loads(p['input']) for p in observed['requests']
                     if p['text']['format']['name'] == 'world_response' and json.loads(p['input'])['phase'] == 'npc_turn']
            assert len(turns) == 1 and turns[0]['combat']['active_id'] == 'guard_1'
    assert normalized(graphical['after']) == normalized(headless['after'])
    assert normalized(graphical['report'].context()) == normalized(headless['report'].context())
    def requests(observed):
        return [{**p, 'input': normalized(json.loads(p['input']))} for p in observed['requests']]
    # Compara também instruções/esquemas/parâmetros e ordem das chaves; só ids
    # mecânicos variáveis são removidos do contexto observado, nunca do pedido real.
    assert json.dumps(requests(graphical), ensure_ascii=False) == json.dumps(requests(headless), ensure_ascii=False)
    write_proof(tmp_path, 'positive', {'window': graphical, 'runner': headless}, {'window': [], 'runner': []})


@pytest.mark.parametrize('control', ['no_approach', 'narrated_only', 'surge_only'])
def test_equal_ui_and_runner_results_do_not_hide_missing_player_effects(control, screen, tmp_path, capture_logs):
    case = 'surge' if control == 'surge_only' else case_for('investigate')
    graphical = observe('window', case, control, tmp_path, capture_logs)
    headless = observe('runner', case, control, tmp_path, capture_logs)
    assert normalized(graphical['after']) == normalized(headless['after'])  # A igualdade isolada aprovaria o defeito.
    for observed in (graphical, headless):
        errors = errors_for(case, observed)
        assert errors
        if control == 'surge_only':
            assert any('seguido do ataque' in e for e in errors)
            assert observed['after']['resources']['player']['action_surge_uses'] == 0
            assert observed['after']['budgets']['player']['extra_actions'] == 1
            assert observed['after']['resources']['guard_1']['hp'] == 9
        else:
            assert any('Não entrou na Cela 4' in e for e in errors)
            assert observed['after']['position'] == [8, 10]
            if control == 'narrated_only':
                assert observed['reply'].on == FALSE_MOVE
                narration = json.loads(observed['requests'][-1]['input'])
                assert not narration['execution']['player_movement']['occurred']
                assert narration['execution']['player_movement']['traveled_meters'] == 0
    write_proof(tmp_path, control, {'window': graphical, 'runner': headless},
                {'window': errors_for(case, graphical), 'runner': errors_for(case, headless)})


@pytest.mark.parametrize('entry', ['window', 'runner'])
@pytest.mark.parametrize('omission', ['active_guard', 'missing_end_turn'])
def test_same_live_criteria_reject_observations_without_completed_npc_turn(entry, omission, screen, tmp_path, capture_logs):
    case = case_for('enemy_first')
    actual = observe(entry, case, 'positive', tmp_path, capture_logs)
    assert errors_for(case, actual) == []
    bad = {**actual, 'after': deepcopy(actual['after'])}
    if omission == 'active_guard':
        bad['after']['combat']['active_id'] = 'guard_1'
        bad['after']['combat']['player_turn'] = False
        bad['after']['combat']['active'] = 'Guarda 1'
        expected_error = 'não devolveu'
    else:
        bad['report'] = replace(actual['report'], world_events=tuple(
            e for e in actual['report'].world_events if e['operation'] != 'end_turn'))
        expected_error = 'Falta a conclusão real'
    assert any(expected_error in e for e in errors_for(case, bad))
    assert errors_for(case, actual) == []  # A sessão e sua observação original não foram adulteradas.
    write_proof(tmp_path, omission, {'actual': actual, 'evaluation_only': bad},
                {'actual': [], 'evaluation_only': errors_for(case, bad)})


@pytest.mark.parametrize('entry', ['window', 'runner'])
@pytest.mark.parametrize('omission', ['event', 'damage', 'reaction'])
def test_same_live_criteria_reject_lost_opportunity_even_when_destination_is_correct(entry, omission, screen, tmp_path, capture_logs):
    case = case_for('opportunity')
    actual = observe(entry, case, 'positive', tmp_path, capture_logs)
    assert errors_for(case, actual) == []
    bad = {**actual, 'after': deepcopy(actual['after'])}
    if omission == 'event':
        bad['report'] = replace(actual['report'], world_events=tuple(
            e for e in actual['report'].world_events if e['operation'] != 'opportunity_attack'))
    elif omission == 'damage':
        bad['after']['resources']['player']['hp'] = 28
    else:
        bad['after']['budgets']['guard_1']['reaction_used'] = False
    assert bad['after']['area'] == 'bathroom' and bad['after']['resources']['player']['hp'] == (28 if omission == 'damage' else 23)
    assert any('oportunidade' in e.lower() for e in errors_for(case, bad))
    assert errors_for(case, actual) == []
    write_proof(tmp_path, omission, {'actual': actual, 'evaluation_only': bad},
                {'actual': [], 'evaluation_only': errors_for(case, bad)})

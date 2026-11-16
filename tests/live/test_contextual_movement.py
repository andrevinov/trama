"""Oito regressões live de movimento contextual no simulador real da dungeon."""

from collections import deque
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from trama.application.authorization import step_operations
from trama.application.conversation import Conversation
from trama.application.dialogue import DialogueMessage
from trama.application.scenarios import build_session
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, MovementSegment, ScenarioIntent, RuleIntent
from trama.bootstrap import compose_game, open_game
from trama.application.game_flow import FlowStage
from trama.application.game_runner import RunStatus
from trama.infrastructure.call_budget import CallBudget
from trama.observability import log_context

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/contextual_movement'
CASES = json.loads((FIXTURES / 'cases.json').read_text())
PREPARATIONS = json.loads((FIXTURES / 'preparations.json').read_text())
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]

pytestmark = [pytest.mark.live,
    pytest.mark.skipif(os.environ.get('RUN_OPENAI_LIVE_TESTS') != '1',
                       reason='Defina RUN_OPENAI_LIVE_TESTS=1 para autorizar chamadas pagas.')]


class FrozenRoller:
    """Fixa valor e tipo de cada dado, incluindo a preparação do cenário."""
    def __init__(self, rolls, optional_tail=()):
        if any(not isinstance(r, list) or len(r) != 2 or
               any(type(n) is not int for n in r) or r[0] < 2 or not 1 <= r[1] <= r[0] for r in [*rolls, *optional_tail]):
            raise ValueError('Cada rolagem deve declarar [faces, valor] válidos.')
        self.pending = deque(tuple(r) for r in rolls)
        self.optional_tail = deque(tuple(r) for r in optional_tail)
        self.used = []
        self.optional_used = []

    def roll(self, sides):
        queue = self.pending if self.pending else self.optional_tail
        assert queue, f'Rolagem não prevista: d{sides}.'
        expected_sides, value = queue[0]
        assert sides == expected_sides, f'Esperava d{expected_sides}, recebeu d{sides}.'
        queue.popleft()
        if queue is self.optional_tail:
            self.optional_used.append([sides, value])
        self.used.append([sides, value])
        return value


def snapshot(session):
    area = session.scene.area_at(session.state.position)
    return {
        'position': [session.state.position.x + 1, session.state.position.y + 1],
        'area': area.id if area else None, 'mode': session.mode.value,
        'spent_meters': float(session.state.spent_meters),
        'remaining_meters': float(session.state.remaining_meters), 'dash_used': session.state.dash_used,
        'combat': session.combat_context(),
        'creatures': {c.id: [c.position.x + 1, c.position.y + 1] for c in session.creatures},
        'resources': {id: asdict(state) for id, state in session.encounter.states.items()},
        'budgets': {id: asdict(budget) for id, budget in session.encounter.budgets.items()},
        'inventory': sorted(session.dungeon.inventory), 'discovered': sorted(session.dungeon.discovered),
        'clothing': session.dungeon.clothing, 'weapons': list(session.encounter.player_sheet.weapons),
        'passages': {p.id: {'is_open': p.is_open, 'locked': p.locked} for p in session.scene.passages},
        'last_attack': deepcopy(session.encounter.last_attacks.get('player')),
        'prisoner_awake': session.dungeon.prisoner_awake,
        'prisoner_free': session.dungeon.prisoner_free,
        'escaped': session.dungeon.escaped,
        'disguise': session.dungeon.disguise, 'guard_alert': session.dungeon.guard_alert,
        'sword_concealed': session.dungeon.sword_concealed,
        'pending_opportunity': session.pending_opportunity is not None,
    }


def declared_intent(data):
    """Desserializa a entrada da fixture nos construtores reais, sem regras próprias."""
    values = dict(data)
    kind = values.pop('intent')
    if kind == 'movement':
        values['segments'] = tuple(MovementSegment(**s) for s in values.get('segments', []))
        return MovementIntent(dash=False, clarification='', **values)
    return {'door': DoorIntent, 'scenario': ScenarioIntent, 'rule': RuleIntent}[kind](**values)


def check_preconditions(case, actual):
    """Igualdades declaradas pelo caso; nunca gera expectativas a partir do motor."""
    for path, expected in case['preconditions'].items():
        value = actual
        for key in path.split('.'):
            assert isinstance(value, dict) and key in value, f'{case["id"]}: pré-condição desconhecida {path}.'
            value = value[key]
        assert value == expected, f'{case["id"]}: pré-condição {path}: esperado {expected!r}, obtido {value!r}.'


def case_data(case):
    data = json.loads((ROOT / case['scenario']).read_text())
    for id, variation in case.get('passage_variations', {}).items():
        passage = next(p for p in data['passages'] if p['id'] == id)
        assert not variation.keys() - {'is_open', 'locked'}, 'Variação de passagem desconhecida.'
        passage.update(variation)  # Dados anteriores à construção; validadores reais abaixo.
    return data


def build_case(case, *, services=None):
    """Arranjo local pelo mesmo carregador e pelas mesmas operações públicas."""
    roller = FrozenRoller(case['rolls'], case.get('optional_world_rolls', []))
    session = build_session(case_data(case), roller=roller)
    conversation = Conversation(session) if services is None else compose_game(session, services).conversation
    prepare_case(case, conversation, roller)
    return conversation, roller


def prepare_case(case, conversation, roller, *, with_history=True):
    """Aplica preparação determinística na conversa já criada pelo fluxo."""
    session = conversation.session
    for preparation in case['setup']:
        for index, declared in enumerate(PREPARATIONS[preparation]):
            report = conversation.execute(ActionPlan(tuple(declared_intent(s) for s in declared['steps'])))
            assert report.status == declared['expected_status'], (f'Preparação inválida de {case["id"]}, '
                f'{preparation}[{index}]: {report.stop_reason}')
            assert not report.failures and report.unperformed_steps == 0, 'Preparação deixou ações inválidas ou não executadas.'
            operations = {e['operation'] for e in report.world_events}
            assert set(declared.get('expected_world_operations', [])) <= operations, 'Faltou um efeito esperado na preparação.'
            assert not session.pending_opportunity and not conversation.pending_npc_turn, 'Preparação exige escolha/retomada não declarada.'
    assert len(roller.used) == case['preparation_rolls'], 'A preparação consumiu uma sequência de dados diferente.'
    check_preconditions(case, snapshot(session))
    if with_history:
        restore_history(case, conversation)


def restore_history(case, conversation):
    if case.get('history'):
        history = json.loads((FIXTURES / case['history']).read_text())['messages']
        conversation.extend_history(DialogueMessage.from_data(m) for m in history)


def evaluate(case, before, after, report, plan, roller, requests=None):
    """Critérios de resultado; não exige frases ou microetapas idênticas."""
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    expected = case['expected']
    success = expected in {'investigate', 'take', 'attack', 'opportunity'}
    check(report.status == ('completed' if success else 'blocked'), 'Status de execução divergente.')
    operations = [op for step in plan.steps for op in step_operations(step)]
    primary = {'investigate': 'investigate', 'take': 'take', 'attack': 'attack',
               'short_movement': 'attack', 'enemy_first': 'attack', 'closed_gate': 'investigate',
               'no_movement': 'investigate', 'opportunity': 'investigate'}[expected]
    check(set(operations) <= {'move', 'look', 'clarify', primary}, 'Plano acrescentou ação/poder não solicitado.')
    target = ('bathroom' if expected == 'opportunity' else 'longsword' if expected == 'take'
              else 'guard_1' if primary == 'attack' else 'cell_4')
    primary_steps = [step for step in plan.steps if getattr(step, 'operation', None) == primary]
    check(all(step.target_id == target for step in primary_steps), 'Trocou o alvo solicitado.')

    check(not after['dash_used'], 'Usou Dash sem autorização.')
    check(after['passages'] == before['passages'], 'Abriu/fechou/destrancou passagem sem pedido.')
    check(after['clothing'] == before['clothing'], 'Trocou a roupa sem pedido.')
    check(after['prisoner_awake'] == before['prisoner_awake'] and
          after['prisoner_free'] == before['prisoner_free'] and not after['escaped'],
          'Alterou prisioneiro ou fuga fora do objetivo do caso.')
    for actor, initial in before['resources'].items():
        final = after['resources'][actor]
        check({k: v for k, v in initial.items() if k != 'hp'} ==
              {k: v for k, v in final.items() if k != 'hp'}, f'Gastou recurso de {actor} sem pedido.')
        if not ((expected == 'attack' and actor == 'guard_1') or
                (expected == 'opportunity' and actor == 'player')):
            check(final['hp'] == initial['hp'], f'Alterou PV de {actor} indevidamente.')
    if expected != 'take':
        check(after['inventory'] == before['inventory'] and after['weapons'] == before['weapons'],
              'Coletou/largou/trocou equipamento sem pedido.')
    if expected != 'investigate':
        check(after['discovered'] == before['discovered'], 'Descobriu itens fora do objetivo.')
    check(not roller.pending, 'Deixou de realizar rolagens previstas para o caso.')
    moves = [e for e in report.events if e['operation'] == 'move']
    distance = sum(e['traveled_meters'] for e in moves)
    attacks = [e for e in report.events if e['operation'] == 'attack' and e.get('status') == 'completed']
    if expected == 'investigate':
        check(after['area'] == 'cell_4' and distance == 3, 'Não entrou na Cela 4 percorrendo os 3 m necessários.')
        check(set(after['discovered']) == {'longsword', 'cleaner_uniform'}, 'Não executou a investigação com a rolagem fixada.')
    elif expected == 'take':
        check(distance > 0 and after['inventory'] == ['longsword'] and after['weapons'] == ['longsword'],
              'Não aproximou/coletou a espada longa no inventário real.')
    elif expected == 'attack':
        check(distance == 4.5 and after['spent_meters'] == 4.5, 'Aproximação de ataque não debitou os 4,5 m táticos.')
        check(len(attacks) == 1 and attacks[0].get('target_id') == 'guard_1', 'Não resolveu exatamente o ataque solicitado.')
        check(after['resources']['guard_1']['hp'] == 5, 'Dano não corresponde aos dados fixados.')
        check(after['budgets']['player']['action_used'], 'Não consumiu a ação de ataque.')
        check(after['last_attack'] and after['last_attack']['weapon'] == 'longsword', 'Usou arma diferente da solicitada.')
        starts = [i for i, e in enumerate(report.events) if e['operation'] == 'start_combat']
        movements = [i for i, e in enumerate(report.events) if e['operation'] == 'move']
        check(starts and movements and starts[0] < movements[0], 'Concedeu aproximação antes da iniciativa.')
    elif expected == 'short_movement':
        check(distance == 1.5 and after['spent_meters'] == 9, 'Não limitou a aproximação ao saldo de 1,5 m.')
        check(not attacks and not after['budgets']['player']['action_used'], 'Atacou/gastou ação sem alcançar o guarda.')
        check(any(f.code == 'insufficient_movement' for f in report.failures), 'Falta a causa estruturada de movimento insuficiente.')
    elif expected == 'enemy_first':
        check(after['position'] == before['position'] and distance == 0 and not attacks,
              'Moveu/atacou antes do turno do jogador.')
        check(after['combat'] and after['combat']['active_id'] == 'player', 'O turno do guarda não devolveu o controle ao jogador.')
        check(any(e['operation'] == 'end_turn' and e.get('actor_id') == 'guard_1' for e in report.world_events),
              'Falta a conclusão real do turno do guarda.')
        check(not any(f.actor_id == 'guard_1' for f in report.failures), 'A resposta do guarda falhou em vez de concluir seu turno.')
        if requests is not None:
            turns = [r for r in requests if r.stage == FlowStage.NPC_TURN]
            check(bool(turns) and turns[0].context['combat']['active_id'] == 'guard_1', 'Não resolveu o NPC que venceu a iniciativa.')
    elif expected in {'closed_gate', 'no_movement'}:
        check(after['position'] == before['position'] and distance == 0, 'Moveu apesar da grade/restrição.')
        check(not after['discovered'], 'Investigou sem entrar na cela.')
    elif expected == 'opportunity':
        reactions = [e for e in report.world_events if e['operation'] == 'opportunity_attack']
        check(after['area'] == 'bathroom' and distance == 6, 'Não chegou ao banheiro pelo percurso esperado.')
        check(len(reactions) == 1 and after['resources']['player']['hp'] == before['resources']['player']['hp'] - 5,
              'Não resolveu o ataque de oportunidade com os dados fixados.')
        check(after['budgets']['guard_1']['reaction_used'] and not after['budgets']['guard_1']['action_used'],
              'Oportunidade não consumiu somente a reação do guarda.')
        check(after['budgets']['player']['action_used'], 'Não consumiu a ação para investigar o banheiro.')
    if expected in {'investigate', 'take', 'closed_gate', 'no_movement'}:
        check(after['mode'] == 'narrated', 'Criou combate durante exploração tranquila.')
        check(after['budgets'] == before['budgets'], 'Cobrou orçamento de turno em modo narrado.')
    return errors


def error_data(error):
    return {'type': type(error).__name__, 'message': str(error)} if error is not None else None


def observe_run(evidence, label, result, flow):
    """Somente observação dos dados já produzidos pelo runner compartilhado."""
    traces = []
    for request in result.requests:
        value = error_data(request.result) if isinstance(request.result, Exception) else asdict(request.result)
        traces.append({'request_id': request.request_id, 'stage': request.stage,
                       'prompt': request.prompt, 'context': request.context,
                       'result': value, 'is_error': isinstance(request.result, Exception), 'applied': request.applied})
        # Nomes anteriores preservados para consulta; não constroem pedidos.
        if request.stage == FlowStage.INTERPRET:
            evidence['interpretation_context'] = request.context
            if not isinstance(request.result, Exception):
                evidence['plan'] = value
        elif request.stage == FlowStage.WORLD:
            evidence['world_context'] = request.context
            evidence['world_plan'] = value
        elif request.stage == FlowStage.NARRATE:
            evidence['narration_context'] = request.context
    evidence['runs'].append({'label': label, 'interaction_id': flow.interaction_id,
        'status': result.status, 'flow_status': result.flow_status, 'accepted': result.accepted,
        'requests': traces, 'execution': result.report.context(),
        'reply': asdict(result.reply) if result.reply else None, 'error': error_data(result.error),
        'awaiting_reaction': result.awaiting_reaction, 'pending_request_id': result.pending_request_id,
        'after': snapshot(flow.session)})
    evidence['flow_error'] = error_data(result.error)
    evidence['execution'] = result.report.context()
    evidence['reply'] = asdict(result.reply) if result.reply else None


def require_complete(evidence, result, budget):
    if budget.context()['exceeded']:
        evidence['outcome'] = 'inconclusive'
        raise AssertionError('Execução incompleta: orçamento de chamadas esgotado.')
    if result.status == RunStatus.FAILED:
        evidence['outcome'] = 'flow_failed'
        raise AssertionError(f'Falha no fluxo: {type(result.error).__name__}: {result.error}')
    if result.status != RunStatus.COMPLETED or result.awaiting_reaction:
        evidence['outcome'] = 'inconclusive'
        raise AssertionError(f'Execução incompleta: {result.status}; falta conclusão ou escolha declarada.')


@pytest.mark.parametrize('case', CASES, ids=[case['id'] for case in CASES])
def test_live_contextual_movement(case, capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    output = Path(os.environ.get('TRAMA_CONTEXTUAL_ARTIFACTS', ROOT / 'logs/live/contextual_movement')) / RUN_ID / case['id']
    output.mkdir(parents=True, exist_ok=False)
    evidence = {'case': case, 'stage': 'setup', 'outcome': 'failed', 'session_id': uuid4().hex, 'runs': []}
    game = roller = budget = None
    try:
        budget = CallBudget(case['max_sdk_calls'])
        choices = case['choices']
        assert isinstance(choices, list) and all(type(c) is bool for c in choices), 'Escolhas devem ser booleanos explícitos.'
        roller = FrozenRoller(case['rolls'], case.get('optional_world_rolls', []))
        data = case_data(case)
        with capture_logs(log_file=output / 'trace.jsonl'), log_context(session_id=evidence['session_id']), open_game(data, roller=roller, budget=budget) as game:
            evidence['configuration'] = game.services.metadata
            evidence['model'] = game.services.config.model
            evidence['source_initial'] = snapshot(game.flow.session)
            evidence['stage'] = 'preparation'
            evidence['preparation'] = {name: PREPARATIONS[name] for name in case['setup']}
            if case.get('history'):
                evidence['registered_history'] = json.loads((FIXTURES / case['history']).read_text())
            evidence['preparation_interaction_id'] = uuid4().hex
            with log_context(interaction_id=evidence['preparation_interaction_id']):
                prepare_case(case, game.flow.conversation, roller, with_history=False)
            evidence['preparation_dice_used'] = list(roller.used)
            evidence['initial'] = snapshot(game.flow.session)
            evidence['stage'] = 'opening'
            opening = game.runner.start()
            observe_run(evidence, 'opening', opening, game.flow)
            require_complete(evidence, opening, budget)
            assert opening.reply and opening.reply.on.strip(), 'Abertura sem descrição em on.'
            # A janela recente do caso de regressão preserva o registro original.
            restore_history(case, game.flow.conversation)
            before = evidence['before'] = snapshot(game.flow.session)
            evidence['stage'] = 'action'
            result = game.runner.submit(case['prompt'])
            observe_run(evidence, 'action', result, game.flow)
            action_requests = list(result.requests)
            used_choices = 0
            while result.status == RunStatus.AWAITING_REACTION and used_choices < len(choices):
                choice = choices[used_choices]
                used_choices += 1
                result = game.runner.choose_opportunity(choice)
                observe_run(evidence, 'reaction', result, game.flow)
                action_requests.extend(result.requests)
            evidence['choices_used'] = choices[:used_choices]
            require_complete(evidence, result, budget)
            assert used_choices == len(choices), 'Escolha declarada não foi solicitada pelo fluxo.'
            evidence['after'] = snapshot(game.flow.session)
            interpreted = next((r for r in action_requests if r.stage == FlowStage.INTERPRET
                                and not isinstance(r.result, Exception)), None)
            assert interpreted is not None, 'Faltou a interpretação da ação do jogador.'
            evidence['stage'] = 'evaluation'
            errors = evaluate(case, before, evidence['after'], result.report, interpreted.result, roller, action_requests)
            if not result.reply or (not result.reply.on.strip() and not result.reply.off.strip()):
                errors.append('Narrador devolveu resposta vazia.')
            if not result.report.stop_reason and (result.reply is None or not result.reply.on.strip()):
                errors.append('Ação realizada sem descrição em on.')
            evidence['errors'] = errors
            assert not errors, f'{case["id"]}: ' + '; '.join(errors) + f' — evidências: {output}'
            evidence['outcome'] = evidence['stage'] = 'passed'
    except BaseException as error:
        evidence['exception'] = error_data(error)
        raise
    finally:
        if game is not None:
            evidence['after'] = snapshot(game.flow.session)
        if roller is not None:
            evidence['dice_used'] = roller.used
            evidence['dice_pending'] = list(roller.pending)
            evidence['optional_world_dice_used'] = roller.optional_used
            evidence['optional_world_dice_pending'] = list(roller.optional_tail)
        if budget is not None:
            evidence['call_budget'] = budget.context()
        (output / 'result.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + '\n')

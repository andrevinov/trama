"""Oito regressões live de movimento contextual no simulador real da dungeon."""

from collections import deque
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from openai import OpenAI

from trama.application.authorization import step_operations
from trama.application.conversation import Conversation
from trama.application.dialogue import DialogueMessage, Speech
from trama.application.dungeon import DungeonSession
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, MovementSegment, ScenarioIntent, RuleIntent
from trama.infrastructure.openai_intent_interpreter import DEFAULT_MODEL, OpenAIIntentInterpreter
from trama.infrastructure.openai_narrator import OpenAINarrator
from trama.infrastructure.openai_world_director import OpenAIWorldDirector
from trama.observability import log_context

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/contextual_movement'
CASES = json.loads((FIXTURES / 'cases.json').read_text())
RUN_ID = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]

pytestmark = [pytest.mark.live,
    pytest.mark.skipif(os.environ.get('RUN_OPENAI_LIVE_TESTS') != '1',
                       reason='Defina RUN_OPENAI_LIVE_TESTS=1 para autorizar chamadas pagas.')]


class FrozenRoller:
    """Fixa valor e tipo de cada dado, incluindo a preparação do cenário."""
    def __init__(self, rolls):
        self.pending = deque(tuple(r) for r in rolls)
        self.used = []

    def roll(self, sides):
        assert self.pending, f'Rolagem não prevista: d{sides}.'
        expected_sides, value = self.pending.popleft()
        assert sides == expected_sides, f'Esperava d{expected_sides}, recebeu d{sides}.'
        assert 1 <= value <= sides
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
        'resources': {id: asdict(state) for id, state in session.encounter.states.items()},
        'budgets': {id: asdict(budget) for id, budget in session.encounter.budgets.items()},
        'inventory': sorted(session.dungeon.inventory), 'discovered': sorted(session.dungeon.discovered),
        'clothing': session.dungeon.clothing, 'weapons': list(session.encounter.player_sheet.weapons),
        'passages': {p.id: {'is_open': p.is_open, 'locked': p.locked} for p in session.scene.passages},
        'last_attack': deepcopy(session.encounter.last_attacks.get('player')),
        'prisoner_awake': session.dungeon.prisoner_awake,
        'prisoner_free': session.dungeon.prisoner_free,
        'escaped': session.dungeon.escaped,
    }


def build_case(case):
    """Dados congelados; todas as operações reutilizam a sessão de produção."""
    data = json.loads((ROOT / 'pocs/simulador/dungeon.json').read_text())
    if case['stage'] == 'combat_opportunity':
        # Variação congelada: a porta do banheiro está aberta neste encontro.
        next(p for p in data['passages'] if p['id'] == 'bathroom_door')['is_open'] = True
    roller = FrozenRoller(case['rolls'])
    session = DungeonSession.from_data(data, roller=roller)
    conversation = Conversation(session)

    def execute(*steps):
        report = conversation.execute(ActionPlan(tuple(steps)))
        assert report.status == 'completed', f'Preparação inválida de {case["id"]}: {report.stop_reason}'

    def move(target):
        return MovementIntent((), False, '', target)

    # Percorre as celas como na sessão registrada. A última execução contém os
    # 6 m entre as celas 3 e 4, em vez de fabricar uma descrição resumida para a IA.
    execute(move('gate_2'))
    execute(move('gate_3'))
    if case['stage'] == 'storage_closed':
        execute(move('gate_4'))
    else:
        execute(move('gate_4'), DoorIntent('open', 'gate_4'))

    if case['stage'] == 'known_sword':
        execute(ScenarioIntent('investigate', 'cell_4'), move('corridor'))
    if case['stage'] in {'disguised_standoff', 'combat_low_movement', 'combat_opportunity'}:
        execute(ScenarioIntent('investigate', 'cell_4'), ScenarioIntent('take', 'longsword'),
                ScenarioIntent('take', 'cleaner_uniform'), ScenarioIntent('wear', 'cleaner_uniform'),
                ScenarioIntent('conceal', 'longsword'), move('guard_door'), DoorIntent('open', 'guard_door'))
        assert session.dungeon.disguise == 'accepted'
        assert session.encounter.combat is None
    if case['stage'] == 'combat_opportunity':
        # Vai legalmente até a lateral do guarda, ainda sob o disfarce aceito.
        execute(MovementIntent((MovementSegment('north', 2), MovementSegment('east', 3),
                                MovementSegment('north', 2)), False, ''))
        # Congela o início do conflito: o guarda já reconheceu o fugitivo.
        session.dungeon.guard_alert = True
        session.dungeon.disguise = 'failed'
        execute(RuleIntent('start_combat'))
    elif case['stage'] == 'combat_low_movement':
        execute(RuleIntent('start_combat'))
        # Este teste começa após o jogador gastar 7,5 m no turno vigente.
        session.state = replace(session.state, spent_meters=session.state.speed_meters - Decimal('1.5'))
    if case.get('history'):
        history = json.loads((FIXTURES / case['history']).read_text())['messages']
        conversation.messages = [DialogueMessage(m['role'], Speech(m['on'], m.get('off', ''))) for m in history]
    return conversation, roller


def evaluate(case, before, after, report, plan, roller):
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
        check(after['combat'] and after['combat']['active_id'] == 'guard_1', 'Não respeitou a iniciativa do guarda.')
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


@pytest.mark.parametrize('case', CASES, ids=[case['id'] for case in CASES])
def test_live_contextual_movement(case, capture_logs):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY não configurada')
    model = os.environ.get('TRAMA_OPENAI_MODEL', DEFAULT_MODEL)
    output = Path(os.environ.get('TRAMA_CONTEXTUAL_ARTIFACTS', ROOT / 'logs/live/contextual_movement')) / RUN_ID / case['id']
    output.mkdir(parents=True, exist_ok=False)
    identifiers = {'session_id': uuid4().hex, 'interaction_id': uuid4().hex}
    evidence = {'case': case, 'model': model, 'stage': 'setup', **identifiers}
    conversation = roller = None
    try:
        with capture_logs(log_file=output / 'trace.jsonl'), log_context(**identifiers):
            conversation, roller = build_case(case)
            before = evidence['before'] = snapshot(conversation.session)
            speech = conversation.prepare(case['prompt'])
            evidence['interpretation_context'] = conversation.interpretation_context()
            with OpenAI(timeout=30, max_retries=0) as client:
                evidence['stage'] = 'interpretation'
                plan = OpenAIIntentInterpreter(client, model).interpret(speech.on, evidence['interpretation_context'])
                evidence['plan'] = asdict(plan)
                evidence['world_context'] = conversation.world_context(plan)
                evidence['stage'] = 'world'
                world = OpenAIWorldDirector(client, model).decide(evidence['world_context'])
                evidence['world_plan'] = asdict(world)
                evidence['stage'] = 'execution'
                report = conversation.execute(plan, world)
                evidence['execution'] = report.context()
                evidence['narration_context'] = conversation.narration_context(speech, report)
                evidence['stage'] = 'narration'
                reply = conversation.finish(OpenAINarrator(client, model).narrate(evidence['narration_context']),
                                            evidence['narration_context'])
                evidence['reply'] = asdict(reply)
            evidence['after'] = snapshot(conversation.session)
            errors = evaluate(case, before, evidence['after'], report, plan, roller)
            if not reply.on.strip() and not reply.off.strip():
                errors.append('Narrador devolveu resposta vazia.')
            if not report.stop_reason and not reply.on.strip():
                errors.append('Ação realizada sem descrição em on.')
            evidence['stage'] = 'evaluation'
            evidence['errors'] = errors
            assert not errors, f'{case["id"]}: ' + '; '.join(errors) + f' — evidências: {output}'
            evidence['stage'] = 'passed'
    except BaseException as error:
        evidence['exception'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        if conversation is not None:
            evidence['after'] = snapshot(conversation.session)
        if roller is not None:
            evidence['dice_used'] = roller.used
            evidence['dice_pending'] = list(roller.pending)
        (output / 'result.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + '\n')

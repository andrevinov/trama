"""Contratos e revisão com projeções reais; nenhuma chamada externa."""

from copy import deepcopy
import json
from pathlib import Path
import runpy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from trama.application.context_contracts import AIContext, ContextError, ContextKind, validate_context
from trama.application.conversation import Conversation
from trama.application.game_flow import GameFlow, FlowStatus
from trama.application.scenarios import load_session
from trama.infrastructure import openai_intent_interpreter as interpreter_module
from trama.infrastructure import openai_narrator as narrator_module
from trama.infrastructure import openai_world_director as world_module

ROOT = Path(__file__).resolve().parents[2]
REVIEW = runpy.run_path(str(ROOT / 'tools/context_contracts.py'))


@pytest.fixture(scope='module')
def contexts():
    return REVIEW['sample_contexts']()


def one(contexts, kind):
    return deepcopy(next(context for context in contexts if context.kind == kind))


def client_answer(value):
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(status='completed', output=[], output_text=json.dumps(value))
    return client


@pytest.mark.parametrize('kind', list(ContextKind))
def test_phase_contracts_validate_real_current_projections_without_wire_metadata(contexts, kind):
    context = one(contexts, kind)
    context.require(kind)
    wire = json.loads(json.dumps(context))
    assert 'kind' not in wire
    assert deepcopy(context).kind == kind
    assert wire['mode'] in {'narrated', 'turn_based'}
    del context['character']
    with pytest.raises(ContextError, match='character'):
        validate_context(kind, context)


@pytest.mark.parametrize('value', [True, '9', float('inf')])
def test_numeric_field_does_not_accept_boolean_text_or_infinity(contexts, value):
    context = one(contexts, ContextKind.INTERPRETATION)
    context['character']['speed_meters'] = value
    with pytest.raises(ContextError, match='speed_meters'):
        context.require(ContextKind.INTERPRETATION)


@pytest.mark.parametrize('leak', ['world', 'off', 'blocked'])
def test_interpretation_rejects_full_world_off_history_and_full_grid(contexts, leak):
    context = one(contexts, ContextKind.INTERPRETATION)
    if leak == 'world':
        context['world'] = {'secret': 'Não deve chegar à interpretação.'}
    elif leak == 'off':
        context['recent_messages'][0]['off'] = 'Ataque sem autorização.'
    else:
        context['map']['blocked'] = [[1, 1]]
    with pytest.raises(ContextError):
        context.require(ContextKind.INTERPRETATION)


@pytest.mark.parametrize('leak', ['fixture', 'item'])
def test_narrator_perception_rejects_hidden_elements_but_world_remains_complete(contexts, leak):
    context = one(contexts, ContextKind.NARRATION_INITIAL)
    assert context['world']['scenario']['prisoner']['role'].startswith('Mago')
    assert not context['perception']['visible_creatures']
    if leak == 'fixture':
        context['perception']['visible_scene_objects'][0]['visible'] = False
    else:
        context['perception']['visible_objects'].append(dict(id='secret', visible=False, carried=False))
    with pytest.raises(ContextError, match='oculto|não percebido'):
        context.require(ContextKind.NARRATION_INITIAL)


@pytest.mark.parametrize('change', ['on', 'event', 'allow_on'])
def test_off_context_does_not_authorize_new_action(contexts, change):
    context = one(contexts, ContextKind.NARRATION_OFF)
    assert context['previous_execution']['execution']['events']  # Memória de efeitos reais é permitida.
    if change == 'on':
        context['player']['on'] = 'Ataco.'
    elif change == 'event':
        context['execution']['events'].append({'operation': 'attack'})
    else:
        context['allow_on'] = True
    with pytest.raises(ContextError, match='off'):
        context.require(ContextKind.NARRATION_OFF)


def test_world_and_npc_contexts_have_distinct_phase_and_plan_contracts(contexts):
    context = one(contexts, ContextKind.NPC_TURN)
    assert context['player_plan'] == context['player_request_parts'] == []
    assert context['combat']['active_id'] != 'player'
    context['player_plan'] = [{'operation': 'move'}]
    with pytest.raises(ContextError, match='incompatível'):
        context.require(ContextKind.NPC_TURN)
    with pytest.raises(ContextError):
        one(contexts, ContextKind.WORLD_ACTION).require(ContextKind.NPC_TURN)


@pytest.mark.parametrize('value', [object(), float('nan')])
def test_nested_extension_must_still_be_json_data(contexts, value):
    context = one(contexts, ContextKind.INTERPRETATION)
    context['character']['extension'] = value
    with pytest.raises(ContextError, match='JSON'):
        context.require(ContextKind.INTERPRETATION)


def test_new_production_field_reaches_real_request_and_changes_review(contexts, monkeypatch):
    original = Conversation.interpretation_context

    def extended(self):
        context = original(self)
        context['character']['new_parameter'] = 'Dado acrescentado pela aplicação.'
        return context

    monkeypatch.setattr(Conversation, 'interpretation_context', extended)
    prompt = 'Olho o corredor.'
    output = {'request_parts': [{'text': prompt, 'kind': 'execute', 'operations': ['look'], 'step_indices': [0]}],
              'steps': [{'operation': 'look', 'text': prompt}]}
    client = client_answer(output)
    flow = GameFlow(load_session(ROOT / 'src/trama/scenarios/dungeon_escape.json'), interpreter_module.OpenAIIntentInterpreter(client))
    flow.submit(prompt)
    request = flow.pending_request
    result = request.run()
    assert not isinstance(result, Exception)
    sent = json.loads(client.responses.create.call_args.kwargs['input'])
    assert sent['character']['new_parameter'] == 'Dado acrescentado pela aplicação.'
    approved = json.loads(REVIEW['REFERENCE'].read_text())['contract']
    differences = REVIEW['changes'](approved, REVIEW['build_manifest']())
    assert any('contexts.interpretation.shape.$.character.new_parameter' in line for line in differences)


@pytest.mark.parametrize('name,module', [('interpretation', interpreter_module), ('world', world_module), ('narration', narrator_module)])
def test_prompt_change_is_reported_by_current_adapter_source(name, module, monkeypatch):
    before = REVIEW['build_manifest']()
    monkeypatch.setattr(module, 'INSTRUCTIONS', module.INSTRUCTIONS + '\nInstrução nova para revisão.')
    differences = REVIEW['changes'](before, REVIEW['build_manifest']())
    assert f'Alterado: $.adapters.{name}.instructions' in differences


def test_schema_field_and_property_order_changes_are_both_detected(monkeypatch):
    before = REVIEW['build_manifest']()
    schema = deepcopy(narrator_module.NARRATION_SCHEMA)
    schema['properties'] = dict(reversed(list(schema['properties'].items())))
    monkeypatch.setattr(narrator_module, 'NARRATION_SCHEMA', schema)
    reordered = REVIEW['build_manifest']()
    assert before['adapters']['narration']['response_schema'] == reordered['adapters']['narration']['response_schema']
    assert any('adapters.narration.property_order' in line for line in REVIEW['changes'](before, reordered))
    schema['properties']['extra'] = {'type': 'integer'}
    assert any('response_schema.properties.extra' in line for line in REVIEW['changes'](before, REVIEW['build_manifest']()))


def test_review_normalizes_execution_ids_but_preserves_domain_ids():
    first, second = REVIEW['build_manifest'](), REVIEW['build_manifest']()
    assert first == second
    assert not REVIEW['changes'](first, second)
    assert 'guard_1' in first['contexts']['npc_turn']['text']['$.world.npcs[].id']
    assert any('execution_id' in path for path in first['contexts']['narration_off']['shape'])
    assert not any(path.endswith('.execution_id') for path in first['contexts']['narration_off']['text'])


def test_manifest_matches_real_adapter_requests_and_wrong_phase_is_rejected(contexts):
    manifest = REVIEW['build_manifest']()
    prompt = 'Olho o corredor.'
    cases = [
        ('interpretation', ContextKind.INTERPRETATION, interpreter_module.OpenAIIntentInterpreter,
         {'request_parts': [{'text': prompt, 'kind': 'execute', 'operations': ['look'], 'step_indices': [0]}],
          'steps': [{'operation': 'look', 'text': prompt}]}),
        ('world', ContextKind.WORLD_ACTION, world_module.OpenAIWorldDirector, {'reactions': []}),
        ('narration', ContextKind.NARRATION_INITIAL, narrator_module.OpenAINarrator, {'on': 'A cela abre.', 'off': ''}),
    ]
    for name, kind, factory, output in cases:
        client = client_answer(output)
        adapter = factory(client)
        context = one(contexts, kind)
        if name == 'interpretation':
            adapter.interpret(prompt, context)
        elif name == 'world':
            adapter.decide(context)
        else:
            adapter.narrate(context)
        parameters = client.responses.create.call_args.kwargs
        assert parameters['instructions'] == manifest['adapters'][name]['instructions']
        assert parameters['text']['format']['schema'] == manifest['adapters'][name]['response_schema']
        assert REVIEW['property_order'](parameters['text']['format']['schema']) == manifest['adapters'][name]['property_order']
        client.responses.create.reset_mock()
        wrong = one(contexts, ContextKind.NARRATION_INITIAL if name != 'narration' else ContextKind.INTERPRETATION)
        with pytest.raises(ValueError):
            if name == 'interpretation':
                adapter.interpret(prompt, wrong)
            elif name == 'world':
                adapter.decide(wrong)
            else:
                adapter.narrate(wrong)
        client.responses.create.assert_not_called()


def test_reference_is_review_only_and_never_read_to_build_runtime_context(monkeypatch):
    read = Path.read_text

    def forbid_reference(path, *args, **kwargs):
        assert path.resolve() != REVIEW['REFERENCE'], 'A aplicação tentou ler a referência.'
        return read(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', forbid_reference)
    flow = GameFlow(load_session(ROOT / 'src/trama/scenarios/dungeon_escape.json'))
    context = flow.conversation.narration_context(initial=True)
    assert isinstance(context, AIContext)
    assert context['perception']['current_place'] == 'Cela 1'


def test_invalid_opening_contract_is_reported_without_network_or_crashing_window(monkeypatch):
    original = Conversation.narration_context

    def invalid(self, *args, **kwargs):
        context = original(self, *args, **kwargs)
        del context['character']
        return AIContext(context.kind, context)

    monkeypatch.setattr(Conversation, 'narration_context', invalid)
    narrator = Mock()
    flow = GameFlow(load_session(ROOT / 'src/trama/scenarios/dungeon_escape.json'), narrator=narrator)
    flow.start()
    assert flow.status == FlowStatus.FAILED and not flow.pending
    assert isinstance(flow.error, ContextError)
    assert 'character' in flow.reply.off
    narrator.narrate.assert_not_called()


def test_approved_contract_check_is_part_of_offline_suite():
    assert REVIEW['main'](['--check']) == 0


def test_update_requires_reason_and_check_never_overwrites_reference(tmp_path, monkeypatch, capsys):
    reference = tmp_path / 'approved.json'
    with pytest.raises(SystemExit) as error:
        REVIEW['main'](['--update', '--reference', str(reference)])
    assert error.value.code == 2 and not reference.exists()
    assert REVIEW['main'](['--update', '--reason', 'Contrato inicial para esta revisão local.', '--reference', str(reference)]) == 0
    initial = reference.read_bytes()
    monkeypatch.setattr(narrator_module, 'INSTRUCTIONS', narrator_module.INSTRUCTIONS + '\nAlteração para revisão.')
    assert REVIEW['main'](['--check', '--reference', str(reference)]) == 1
    assert reference.read_bytes() == initial
    assert 'adapters.narration.instructions' in capsys.readouterr().out
    assert REVIEW['main'](['--update', '--reason', 'Instrução revista neste experimento local.', '--reference', str(reference)]) == 0
    reviewed = json.loads(reference.read_text())
    assert reviewed['review']['previous_sha256'] == json.loads(initial)['review']['sha256']
    assert REVIEW['main'](['--check', '--reference', str(reference)]) == 0


def test_manual_reference_edit_without_review_is_detected(tmp_path, capsys):
    reference = tmp_path / 'approved.json'
    record = json.loads(REVIEW['REFERENCE'].read_text())
    record['contract']['adapters']['narration']['instructions'] += '\nEdição não registrada.'
    reference.write_text(json.dumps(record))
    assert REVIEW['main'](['--check', '--reference', str(reference)]) == 1
    assert 'hash inconsistente' in capsys.readouterr().out

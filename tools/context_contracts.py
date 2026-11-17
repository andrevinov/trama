"""Revisão offline dos contratos atuais; a referência nunca alimenta a aplicação.

Executar da raiz: poetry run python tools/context_contracts.py --check
"""

import argparse
from collections import defaultdict, deque
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from trama.application.context_contracts import CONTRACTS, INTERNAL, OPTIONAL_INTERNAL, ContextKind
from trama.application.conversation import Conversation
from trama.application.dialogue import Speech
from trama.application.intents import ActionPlan, DoorIntent, MovementIntent, MovementSegment, RequestPart, RuleIntent, ScenarioIntent, NarrativeIntent
from trama.application.scenarios import build_session, load_session
from trama.application.parley import InfluenceRequest
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.infrastructure import openai_intent_interpreter, openai_narrator, openai_world_director
from trama.spatial import Position

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'docs/contracts/ai-contexts.json'
VOLATILE_FIELDS = frozenset({'execution_id', 'session_id', 'interaction_id', 'operation_id', 'ai_call_id', 'timestamp'})


class ReviewRoller:
    """Arranjo reproduzível da auditoria; a resolução continua no motor real."""
    def __init__(self, *values):
        self.values = deque(values)

    def roll(self, sides):
        if not self.values:
            raise ValueError(f'A preparação do contrato exige uma nova rolagem de d{sides}; revise o arranjo.')
        value = self.values.popleft()
        if not 1 <= value <= sides:
            raise ValueError('Rolagem incompatível com a preparação do contrato.')
        return value


def action(conversation, prompt, intent):
    """Entrada declarada de preparação, sem interpretação ou chamadas externas."""
    speech = conversation.prepare(prompt)
    operation = getattr(intent, 'operation', 'move')
    plan = ActionPlan((intent,), (RequestPart(speech.on, 'execute', (operation,), (0,)),))
    return speech, plan


def sample_contexts():
    """Observa projeções reais nos seis tipos de contexto; não simula respostas de IA."""
    samples = []
    c = Conversation(load_session(ROOT / 'src/trama/scenarios/dungeon_escape.json', roller=ReviewRoller(20, 20)))
    samples.append(c.narration_context(initial=True))
    # Preparação mecânica até a grade aberta: os dados e as regras são os da aplicação.
    c.execute(ActionPlan((ScenarioIntent('sneak', 'gate_4'), DoorIntent('open', 'gate_4'))))
    speech, plan = action(c, 'Eu checo a cela, procurando por algo útil.', ScenarioIntent('investigate', 'cell_4'))
    samples.extend((c.interpretation_context(), c.world_context(plan)))
    report = c.execute(plan)
    samples.append(c.narration_context(speech, report))
    samples.append(c.interpretation_context())  # Itens conhecidos, lista não vazia.
    samples.append(c.narration_context(c.prepare('[O que descobri?]')))
    speech, plan = action(c, 'Olho ao redor.', NarrativeIntent('Olho ao redor.', 'look'))
    report = c.execute(plan)
    samples.append(c.narration_context(speech, report))  # Memória de testes de perícia permanece narrável.

    data = json.loads((ROOT / 'src/trama/scenarios/dungeon_escape.json').read_text())
    data['start'] = [9, 3]
    npc = Conversation(build_session(data, roller=ReviewRoller(1, 2, 20)))
    npc.session.execute(RuleIntent('start_combat'))
    samples.append(npc.world_context())  # NPC ativo com as extensões da dungeon.

    data = json.loads((ROOT / 'tests/fixtures/scenarios/legacy_cell_and_guards.json').read_text())
    data['start'] = [14, 5]
    next(p for p in data['passages'] if p['id'] == 'guard_door')['is_open'] = True
    c = Conversation(build_session(data, roller=ReviewRoller(20, 19, 1, 1)))
    speech, plan = action(c, 'Ataco o Guarda 1.', RuleIntent('attack', 'guard_1'))
    samples.extend((c.interpretation_context(), c.world_context(plan)))
    report = c.execute(plan)  # Iniciativa, ataque e last_attack reais.
    samples.extend((c.narration_context(speech, report), c.interpretation_context(), c.world_context(plan)))
    speech, plan = action(c, 'Encerro meu turno.', RuleIntent('end_turn'))
    c.execute(plan)
    samples.append(c.world_context())
    report = c.execute_npc_turn(WorldPlan((WorldReaction(0, 0, (
        WorldAction('guard_1', 'move', 'O guarda tenta alcançar a casa bloqueada.', destination=Position(13, 4)),
        WorldAction('guard_1', 'attack', 'O guarda tenta atacar depois.', 'player'),
    )),)))
    samples.append(c.narration_context(report=report))
    samples.append(c.narration_context(c.prepare('[Por que o guarda não atacou?]')))

    # Limite normal de movimento: relatório real sem manter o turno pendente.
    c = Conversation(build_session(dict(width=26, height=5, start=[2, 2], creatures=[
        dict(id='watcher', name='Vigia', position=[21, 2])]), roller=ReviewRoller(20, 19, 1)))
    c.session.execute(RuleIntent('start_combat'))
    c.session.execute(RuleIntent('end_turn'))
    report = c.execute_npc_turn(WorldPlan((WorldReaction(0, 0, (
        WorldAction('watcher', 'move', 'O vigia avança até o limite do turno.', destination=Position(3, 2)),
    )),)))
    samples.append(c.narration_context(report=report))
    samples.append(c.narration_context(c.prepare('[O vigia ainda está agindo?]')))

    c = Conversation(build_session(dict(width=4, height=4, start=[1, 1], blocked=[[2, 1]])))
    samples.append(c.narration_context(initial=True))
    speech, plan = action(c, 'Ando para leste.', MovementIntent((MovementSegment('east', 2),), False, ''))
    samples.extend((c.interpretation_context(), c.world_context(plan)))
    report = c.execute(plan)
    samples.append(c.narration_context(speech, report))
    samples.append(c.narration_context(c.prepare('[Por que parei?]')))
    # Abordagem e Influence gerais, sem adjudicação da dungeon ou payload alternativo.
    for persuasion_roll in (20, 1):
        c = Conversation(build_session(dict(width=24, height=3, start=[1, 1], creatures=[
            dict(id='watcher', name='Vigia', position=[20, 1], hostile=True)]),
            roller=ReviewRoller(persuasion_roll, 1, 2, 20)))
        speech, plan = action(c, 'Olho o corredor.', NarrativeIntent('Olho o corredor.', 'look'))
        report = c.execute(plan, WorldPlan((WorldReaction(0, 0, (
            WorldAction('watcher', 'parley', 'Pare! Identifique-se.'),)),)))
        samples.extend((c.interpretation_context(), c.world_context(plan), c.narration_context(speech, report),
                        c.narration_context(c.prepare('[Posso conversar?]'))))
        speech, plan = action(c, 'Não lute; ouça minha explicação.', NarrativeIntent('Não lute; ouça minha explicação.', 'speak'))
        report = c.execute(plan, WorldPlan((WorldReaction(0, None, (
            WorldAction('watcher', 'influence', 'O vigia hesita em aceitar a explicação.',
                        influence=InfluenceRequest('hesitant', 'persuasion')),)),)))
        samples.extend((c.narration_context(speech, report), c.interpretation_context(), c.world_context(plan)))
        if c.session.encounter.combat:
            samples.append(c.world_context())
    # Percepção geral: ocultação e busca reais em um mapa que não é a dungeon.
    for search_roll in (1, 20):
        c = Conversation(load_session(ROOT / 'src/trama/scenarios/perception_rooms.json', roller=ReviewRoller(20, search_roll)))
        speech, plan = action(c, 'Eu me escondo.', RuleIntent('hide'))
        report = c.execute(plan)
        samples.extend((c.interpretation_context(), c.world_context(plan), c.narration_context(speech, report)))
        speech, plan = action(c, 'Aguardo em silêncio.', NarrativeIntent('Aguardo em silêncio.', 'wait'))
        report = c.execute(plan, WorldPlan((WorldReaction(0, None, (
            WorldAction('watcher', 'search', 'O vigia busca o fugitivo oculto.', 'player'),)),)))
        samples.extend((c.narration_context(speech, report), c.world_context(plan), c.interpretation_context(),
                        c.narration_context(c.prepare('[O que foi percebido?]'))))
    return samples


def describe_contexts(samples):
    result = {}
    for kind in ContextKind:
        shapes, texts = defaultdict(set), defaultdict(set)

        def visit(value, path='$', key=''):
            name = ('object' if isinstance(value, dict) else 'array' if isinstance(value, list) else
                    {str: 'string', bool: 'boolean', int: 'integer', float: 'number', type(None): 'null'}[type(value)])
            shapes[path].add(name)
            if isinstance(value, dict):
                for field, item in value.items():
                    visit(item, f'{path}.{field}', field)
            elif isinstance(value, list):
                for item in value:
                    visit(item, f'{path}[]', key)
            elif isinstance(value, str) and key not in VOLATILE_FIELDS:
                texts[path].add(value)

        selected = [c for c in samples if c.kind == kind]
        if not selected:
            raise ValueError(f'Não há amostra de contexto para {kind}.')
        for context in selected:
            context.require(kind)
            visit(json.loads(json.dumps(context, ensure_ascii=False)))
        result[kind.value] = {
            'shape': {path: '|'.join(sorted(types)) for path, types in sorted(shapes.items())},
            'text': {path: sorted(values) for path, values in sorted(texts.items())},
        }
    return result


def property_order(schema, path='$'):
    """A ordem de properties afeta saída estruturada, mesmo com schemas equivalentes."""
    result = {}
    if isinstance(schema, dict):
        if isinstance(schema.get('properties'), dict):
            result[path] = list(schema['properties'])
        for key, value in schema.items():
            result.update(property_order(value, f'{path}.{key}'))
    elif isinstance(schema, list):
        for index, value in enumerate(schema):
            result.update(property_order(value, f'{path}[{index}]'))
    return result


def build_manifest():
    adapters = {
        'interpretation': (openai_intent_interpreter.INSTRUCTIONS, openai_intent_interpreter.OpenAIIntentInterpreter(None).schema),
        'world': (openai_world_director.INSTRUCTIONS, openai_world_director.WORLD_SCHEMA),
        'narration': (openai_narrator.INSTRUCTIONS, openai_narrator.NARRATION_SCHEMA),
    }
    manifest = {
        'contracts': {kind.value: asdict(contract) for kind, contract in CONTRACTS.items()},
        'internal_fields': INTERNAL, 'optional_internal_fields': sorted(OPTIONAL_INTERNAL),
        'volatile_fields': sorted(VOLATILE_FIELDS),
        'contexts': describe_contexts(sample_contexts()),
        'adapters': {name: {'instructions': text, 'response_schema': schema, 'property_order': property_order(schema)}
                     for name, (text, schema) in adapters.items()},
    }
    # Normaliza tuplas como no transporte e não compartilha os schemas mutáveis.
    return json.loads(json.dumps(manifest, ensure_ascii=False))


def changes(before, after, path='$'):
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in sorted(before.keys() | after.keys()):
            at = f'{path}.{key}'
            if key not in before:
                result.append(f'Adicionado: {at}')
            elif key not in after:
                result.append(f'Removido: {at}')
            else:
                result.extend(changes(before[key], after[key], at))
        return result
    return [] if before == after else [f'Alterado: {path}']


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Compara os contratos atuais com a referência revisada, sem rede.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='Confere o contrato aprovado (padrão).')
    mode.add_argument('--update', action='store_true', help='Registra uma revisão explícita do contrato atual.')
    parser.add_argument('--reason', help='Justificativa obrigatória para registrar a revisão.')
    parser.add_argument('--reference', type=Path, default=REFERENCE)
    args = parser.parse_args(argv)
    if args.update and (not args.reason or not args.reason.strip()):
        parser.error('--update exige --reason com a justificativa da revisão.')
    if args.reason and not args.update:
        parser.error('--reason só se aplica a --update.')
    current = build_manifest()
    previous = json.loads(args.reference.read_text()) if args.reference.exists() else None
    if args.update:
        args.reference.parent.mkdir(parents=True, exist_ok=True)
        record = {'format_version': 1, 'review': {'reason': args.reason.strip(),
                  'previous_sha256': previous['review']['sha256'] if previous else None, 'sha256': digest(current)},
                  'contract': current}
        args.reference.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(f'Revisão registrada em {args.reference}. Confira o diff antes de versionar.')
        return 0
    differences = changes(previous['contract'], current) if previous else ['Referência aprovada ausente.']
    if previous and previous['review']['sha256'] != digest(previous['contract']):
        differences.insert(0, 'Referência alterada sem registro de revisão: hash inconsistente.')
    if differences:
        print('\n'.join(differences))
        print('Revise os campos/instruções/esquemas e registre a justificativa com --update --reason.')
        return 1
    print('Contratos atuais conferem com a referência aprovada. Nenhuma chamada externa.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

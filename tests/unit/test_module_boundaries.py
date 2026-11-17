"""Protege as fronteiras pedidas: regras independentes de IA e visualização."""

import ast
from pathlib import Path

import pytest


@pytest.mark.parametrize("module,allowed", [
    ("spatial", set()),
    ("distances", set()),
    ("actions", set()),
    ("movement", {"trama.spatial", "trama.distances"}),
    ("scene", {"trama.spatial"}),
    ("vision", {"trama.spatial"}),
    ("creatures", {"trama.spatial", "trama.perception"}),
    ("perception", {"trama.spatial", "trama.distances"}),
    ("dice", set()),
    ("characters", {"trama.dice"}),
    ("combat", {"trama.characters", "trama.dice"}),
    ("reactions", {"trama.spatial"}),
    ("application/dialogue", set()),
    ("application/modes", set()),
    ("application/sheet_options", {"trama.actions", "trama.characters", "trama.distances", "trama.movement"}),
    ("application/travel", {"trama.application.modes", "trama.characters", "trama.movement",
                            "trama.reactions", "trama.spatial", "trama.vision"}),
    ("application/world", {"trama.spatial", "trama.application.parley"}),
    ("application/parley", {"trama.spatial"}),
    ("application/authorization", {"trama.application.dialogue", "trama.application.intents"}),
    ("application/interpretation_context", set()),
    ("application/context_contracts", set()),
    ("application/preparation", {"trama.application.intents", "trama.application.routing", "trama.movement", "trama.spatial"}),
    ("application/failures", {"trama.spatial"}),
    ("application/scenarios", {"trama.application.dungeon", "trama.application.session", "trama.characters",
                               "trama.creatures", "trama.dice", "trama.movement", "trama.scene", "trama.spatial", "trama.perception"}),
    ("application/situations", {"trama.application.dialogue", "trama.application.intents", "trama.observability"}),
    ("analysis/interpretation", {"trama.application.dialogue", "trama.application.interpretation_evaluation",
                                 "trama.application.scenarios", "trama.infrastructure.openai_intent_interpreter",
                                 "trama.infrastructure.openai_config", "trama.infrastructure.openai_services",
                                 "trama.observability"}),
    ("application/game_flow", {"trama.application.authorization", "trama.application.conversation",
                               "trama.application.dialogue", "trama.application.intents", "trama.application.session",
                               "trama.application.travel", "trama.application.world", "trama.distances", "trama.observability"}),
    ("application/game_runner", {"trama.application.conversation", "trama.application.dialogue",
                                "trama.application.game_flow", "trama.observability"}),
    ("observability", set()),
    ("bootstrap", {"trama.application.game_flow", "trama.application.game_runner", "trama.application.scenarios", "trama.application.session", "trama.application.situations", "trama.dice",
                   "trama.infrastructure.openai_config", "trama.infrastructure.openai_services", "trama.infrastructure.call_budget"}),
    ("infrastructure/call_budget", set()),
    ("infrastructure/openai_config", set()),
    ("infrastructure/openai_services", {"trama.infrastructure.openai_config", "trama.infrastructure.openai_intent_interpreter",
                                          "trama.infrastructure.openai_narrator", "trama.infrastructure.openai_world_director", "trama.infrastructure.call_budget"}),
    ("infrastructure/openai_json", {"trama.observability", "trama.infrastructure.openai_config", "trama.infrastructure.call_budget"}),
    ("infrastructure/openai_intent_interpreter", {"trama.application.context_contracts", "trama.application.authorization", "trama.application.interpretation_context", "trama.application.modes", "trama.application.intents", "trama.distances", "trama.infrastructure.openai_json", "trama.infrastructure.openai_config", "trama.infrastructure.call_budget", "trama.observability"}),
    ("infrastructure/openai_narrator", {"trama.application.context_contracts", "trama.application.modes", "trama.application.dialogue", "trama.infrastructure.openai_json", "trama.infrastructure.openai_config", "trama.infrastructure.call_budget", "trama.observability"}),
    ("infrastructure/openai_world_director", {"trama.application.parley", "trama.application.context_contracts", "trama.application.modes", "trama.application.world", "trama.spatial", "trama.infrastructure.openai_json", "trama.infrastructure.openai_config", "trama.infrastructure.call_budget", "trama.observability"}),
])
def test_core_modules_do_not_import_each_others_rules_or_adapters(module, allowed):
    source = Path(__file__).resolve().parents[2] / "src/trama" / f"{module}.py"
    tree = ast.parse(source.read_text())
    imports = {node.module for node in ast.walk(tree)
               if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("trama")}
    assert imports <= allowed


def test_pygame_interface_does_not_depend_on_openai_adapter():
    source = Path(__file__).resolve().parents[2] / "src/trama/ui/movement_window.py"
    tree = ast.parse(source.read_text())
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(module and ("infrastructure" in module or "openai" in module) for module in imports)


def test_pygame_interface_delegates_game_decisions_to_flow():
    source = Path(__file__).resolve().parents[2] / 'src/trama/ui/movement_window.py'
    tree = ast.parse(source.read_text())
    calls = {node.func.attr for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not calls & {'interpret', 'decide', 'narrate', 'execute', 'execute_npc_turn', 'next_turn',
                        'prepare', 'finish', 'resolve', 'world_context', 'interpretation_context', 'narration_context'}
    functions = {node.func.id for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert 'GameFlow' in functions
    assert not functions & {'Conversation', 'ExecutionReport', 'TravelExecutor', 'validate_player_plan'}


def test_live_suites_and_interpretation_analysis_use_shared_scenario_construction():
    root = Path(__file__).resolve().parents[2]
    sources = [*sorted((root / 'tests/live').glob('test_*.py')), root / 'src/trama/analysis/interpretation.py']
    constructors = {'GameSession', 'DungeonSession', 'Scene', 'Grid', 'MovementState', 'sheet_from_data', 'creatures_from_data'}
    for source in sources:
        tree = ast.parse(source.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith('trama'):
                assert not constructors & {name.name for name in node.names}, source


def test_live_preparation_does_not_assign_game_state_or_history_directly():
    root = Path(__file__).resolve().parents[2]
    for source in sorted((root / 'tests/live').glob('test_*.py')):
        tree = ast.parse(source.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Attribute):
                        assert target.attr not in {'state', 'messages', 'guard_alert', 'disguise'}, (source, node.lineno)


def test_simulator_live_tests_and_experiment_do_not_compose_openai_clients_or_adapters():
    root = Path(__file__).resolve().parents[2]
    sources = [root / 'src/trama/simulator.py',
               root / 'src/trama/analysis/interpretation.py', root / 'tools/analyze_interpretation.py',
               *sorted((root / 'tests/live').glob('test_*.py'))]
    constructors = {'OpenAI', 'OpenAIIntentInterpreter', 'OpenAINarrator', 'OpenAIWorldDirector'}
    for source in sources:
        tree = ast.parse(source.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else None
                assert name not in constructors, (source, node.lineno)


def test_tests_and_tools_do_not_depend_on_poc_scripts_or_data():
    root = Path(__file__).resolve().parents[2]
    assert not (root / 'pocs').exists(), 'O simulador oficial substituiu as entradas independentes.'
    sources = [p for folder in ('tests', 'tools', 'src') for p in (root / folder).rglob('*.py')]
    prefixes = ('/'.join(('pocs', '')), '\\'.join(('pocs', '')))
    for source in sources:
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not any(prefix in node.value for prefix in prefixes), (source, node.lineno)
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module and node.module.split('.')[0] == 'pocs'), (source, node.lineno)
            elif isinstance(node, ast.Import):
                assert all(name.name.split('.')[0] != 'pocs' for name in node.names), (source, node.lineno)


def test_headless_runner_only_schedules_public_flow_requests():
    source = Path(__file__).resolve().parents[2] / 'src/trama/application/game_runner.py'
    tree = ast.parse(source.read_text())
    calls = {node.func.attr for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not calls & {'interpret', 'decide', 'narrate', 'execute', 'execute_npc_turn', 'next_turn',
                        'resolve', 'prepare', 'finish', 'world_context', 'narration_context', 'interpretation_context'}
    assert {'start', 'submit', 'choose_opportunity', 'reset', 'run', 'receive', 'check_owner'} <= calls


def test_contextual_live_case_uses_runner_without_manual_ai_or_game_transitions():
    source = Path(__file__).resolve().parents[2] / 'tests/live/test_contextual_movement.py'
    tree = ast.parse(source.read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'test_live_contextual_movement')
    calls = {n.func.attr for n in ast.walk(function) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert {'start', 'submit', 'choose_opportunity'} <= calls
    assert not calls & {'interpret', 'decide', 'narrate', 'execute', 'execute_npc_turn', 'next_turn',
                        'receive', 'run', 'prepare', 'finish', 'interpretation_context', 'world_context', 'narration_context'}

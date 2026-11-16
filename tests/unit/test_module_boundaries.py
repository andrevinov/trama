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
    ("creatures", {"trama.spatial"}),
    ("dice", set()),
    ("characters", {"trama.dice"}),
    ("combat", {"trama.characters", "trama.dice"}),
    ("reactions", {"trama.spatial"}),
    ("application/dialogue", set()),
    ("application/modes", set()),
    ("application/sheet_options", {"trama.actions", "trama.characters", "trama.distances", "trama.movement"}),
    ("application/travel", {"trama.application.modes", "trama.characters", "trama.movement",
                            "trama.reactions", "trama.spatial", "trama.vision"}),
    ("application/world", {"trama.spatial"}),
    ("application/authorization", {"trama.application.dialogue", "trama.application.intents"}),
    ("application/interpretation_context", set()),
    ("application/preparation", {"trama.application.intents", "trama.application.routing", "trama.movement", "trama.spatial"}),
    ("application/failures", {"trama.spatial"}),
    ("observability", set()),
    ("infrastructure/openai_json", {"trama.observability"}),
    ("infrastructure/openai_intent_interpreter", {"trama.application.authorization", "trama.application.interpretation_context", "trama.application.modes", "trama.application.intents", "trama.distances", "trama.infrastructure.openai_json", "trama.observability"}),
    ("infrastructure/openai_narrator", {"trama.application.modes", "trama.application.dialogue", "trama.infrastructure.openai_json", "trama.observability"}),
    ("infrastructure/openai_world_director", {"trama.application.modes", "trama.application.world", "trama.spatial", "trama.infrastructure.openai_json", "trama.observability"}),
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

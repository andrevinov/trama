"""Uma construção de cenários para arquivos, variações declaradas e simulador."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from trama.application import scenarios
from trama.application.dungeon import DungeonSession
from trama.application.intents import RuleIntent
from trama.application.scenarios import build_session, load_dungeon, load_session
from trama.spatial import Position

ROOT = Path(__file__).resolve().parents[2]
DUNGEON = ROOT / 'pocs/simulador/dungeon.json'


@pytest.mark.parametrize('scenario,dimensions,start,enemies,armor', [
    ('pocs/simulador/dungeon.json', (19, 25), (3, 21), 1, 11),
    ('pocs/movimento/cela_guardas.json', (19, 11), (3, 5), 3, 17),
    ('pocs/movimento/scenario.json', (10, 10), (4, 4), 0, 17),
])
def test_existing_scenarios_keep_geometry_characters_and_equipment(scenario, dimensions, start, enemies, armor):
    session = load_session(ROOT / scenario)
    assert (session.grid.width, session.grid.height) == dimensions
    assert session.state.position == Position(*start)
    assert len(session.creatures) == enemies
    assert session.encounter.player_sheet.level == 3
    assert session.encounter.player_sheet.armor_class == armor
    assert session.encounter.states['player'].hp == 28
    if scenario == 'pocs/simulador/dungeon.json':
        assert isinstance(session, DungeonSession)
        assert len(session.scene.objects) == 4
        assert session.encounter.player_sheet.weapons == ()
        assert session.dungeon.inventory == set()
        assert session.grid == session.scene.movement_grid
    else:
        assert not isinstance(session, DungeonSession)
        assert session.encounter.player_sheet.weapons == ('greatsword', 'flail', 'javelin')


def test_simple_grid_uses_the_same_builder_without_named_scene():
    session = build_session(dict(width=4, height=4, start=[1, 1], blocked=[[2, 1]], difficult=[[2, 2]]))
    assert session.scene is None
    assert session.grid.blocked == frozenset({Position(2, 1)})
    assert session.grid.difficult == frozenset({Position(2, 2)})
    assert session.state.position == Position(1, 1)


def test_declared_variations_reach_real_map_passage_object_and_sheet_builders(tmp_path):
    data = json.loads(DUNGEON.read_text())
    next(p for p in data['passages'] if p['id'] == 'bathroom_door')['is_open'] = True
    data['player']['abilities'] = {'dexterity': 14}
    data['objects'].append(dict(id='fence', name='Cerca', position=[7, 20],
                                blocks_movement=True, blocks_vision=False))
    original = deepcopy(data)
    path = tmp_path / 'variation.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    for session in (build_session(data), load_session(path)):
        assert session.encounter.player_sheet.armor_class == 12
        assert Position(7, 20) in session.grid.blocked
        assert Position(7, 20) not in session.scene.opaque
        assert Position(14, 2) not in session.grid.blocked
        assert len(session.scene.objects) == 5
        assert all(o.attachment.side == 'east' for o in session.scene.objects if o.kind == 'torch')
    assert data == original
    assert len(load_session(DUNGEON).scene.objects) == 4


@pytest.mark.parametrize('variation', [
    'wall_start', 'occupied_start', 'locked_open_door', 'invalid_attachment',
    'duplicate_object', 'invalid_sheet', 'blocking_object_on_start',
])
def test_invalid_variations_cannot_bypass_existing_validators(variation, tmp_path):
    data = json.loads(DUNGEON.read_text())
    if variation == 'wall_start':
        data['start'] = [0, 0]
    elif variation == 'occupied_start':
        data['creatures'][0]['position'] = data['start'][:]
    elif variation == 'locked_open_door':
        data['passages'][0].update(is_open=True, locked=True)
    elif variation == 'invalid_attachment':
        data['objects'][0]['attachment']['side'] = 'west'
    elif variation == 'duplicate_object':
        data['objects'].append(deepcopy(data['objects'][0]))
    elif variation == 'invalid_sheet':
        data['player']['level'] = 4
    else:
        data['objects'].append(dict(id='crate', name='Caixote', position=data['start'][:], blocks_movement=True))
    path = tmp_path / 'invalid.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    for construct in (lambda: build_session(data), lambda: load_session(path)):
        with pytest.raises(ValueError):
            construct()


def test_roller_is_injected_into_real_encounter(dice):
    roller = dice(20, 19, 1, 1)
    data = json.loads((ROOT / 'pocs/movimento/cela_guardas.json').read_text())
    data['start'] = [14, 5]
    next(p for p in data['passages'] if p['id'] == 'guard_door')['is_open'] = True
    session = build_session(data, roller=roller)
    session.execute(RuleIntent('start_combat'))
    assert roller.sides == [20, 20, 20]
    assert session.encounter.combat.active_id == 'player'


def test_dungeon_compatibility_entry_uses_shared_loader():
    assert isinstance(load_dungeon(DUNGEON), DungeonSession)
    with pytest.raises(ValueError, match='não é uma dungeon'):
        load_dungeon(ROOT / 'pocs/movimento/scenario.json')


def test_file_errors_are_not_replaced_by_another_scenario(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_session(tmp_path / 'missing.json')
    path = tmp_path / 'broken.json'
    path.write_text('{', encoding='utf-8')
    with pytest.raises(json.JSONDecodeError):
        load_session(path)


def test_simulator_cli_uses_shared_construction_without_real_window_or_service(monkeypatch, tmp_path):
    from trama import simulator
    builds, windows = [], []
    original = scenarios.build_session

    def observe(data, **kwargs):
        session = original(data, **kwargs)
        builds.append(session)
        return session

    monkeypatch.setattr(scenarios, 'build_session', observe)
    monkeypatch.setattr(simulator, 'run_window', lambda session, *args, **kwargs: windows.append(session))
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setattr(sys, 'argv', ['simulador', '--scenario', str(DUNGEON),
                                    '--log-file', str(tmp_path / 'cli.jsonl')])
    simulator.main(DUNGEON)
    assert len(builds) == len(windows) == 1
    assert windows[0] is builds[0]
    assert len(windows[0].scene.objects) == 4
    assert windows[0].state.position == Position(3, 21)


def test_loading_does_not_import_graphics_provider_or_cli():
    code = '''
import importlib.abc
from pathlib import Path
import sys
class RejectIO(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'pygame', 'openai', 'argparse'} or fullname.startswith(('trama.ui', 'trama.infrastructure', 'trama.simulator')):
            raise AssertionError('Importação indevida: ' + fullname)
sys.meta_path.insert(0, RejectIO())
from trama.application.scenarios import load_session
session = load_session(Path(sys.argv[1]))
assert session.state.position.x == 3 and len(session.scene.objects) == 4
'''
    result = subprocess.run([sys.executable, '-c', code, str(DUNGEON)], cwd=ROOT,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr

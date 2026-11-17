"""Carregamento compartilhado de cenários, sem CLI, visualização ou provedor de IA."""

import json
from pathlib import Path

from trama.application.dungeon import DungeonSession
from trama.application.session import GameSession
from trama.characters import sheet_from_data
from trama.creatures import creatures_from_data
from trama.dice import Roller
from trama.movement import MovementState
from trama.scene import Scene
from trama.perception import observers_from_data
from trama.spatial import Grid, Position
from trama.knowledge import initial_memories
from trama.social import profiles_from_data


def build_session(data: dict, *, roller: Roller | None = None) -> GameSession:
    """Constrói e valida dados de cenário, inclusive variações declaradas antes da construção.

    Não prepara turnos, inventário ou histórico. Os construtores do domínio e
    da sessão continuam responsáveis por validar mapas, fichas e posições.
    """
    if 'dungeon' in data:
        return DungeonSession.from_data(data, roller=roller)
    scene = Scene.from_data(data) if 'areas' in data else None
    grid = scene.movement_grid if scene else Grid(
        data['width'], data['height'],
        frozenset(Position(*p) for p in data.get('blocked', [])),
        frozenset(Position(*p) for p in data.get('difficult', [])))
    player = sheet_from_data(data.get('player', {}), id='player', name='Jogador', default_level=3)
    return GameSession(
        grid, MovementState(Position(*data['start']), data.get('speed_meters', player.speed_meters)),
        scene, creatures_from_data(data.get('creatures', [])), player_sheet=player,
        enemy_sheets=tuple(sheet_from_data(c.get('sheet', {}), id=c['id'], name=c['name'])
                           for c in data.get('creatures', [])), roller=roller, observers=observers_from_data(data.get("observers", [])),
        memories=initial_memories(data), social_profiles=profiles_from_data(data))


def load_session(path: str | Path, *, roller: Roller | None = None) -> GameSession:
    """Lê o JSON e usa a mesma construção para dungeon, mapa nomeado ou grade simples."""
    return build_session(json.loads(Path(path).read_text(encoding='utf-8')), roller=roller)


def load_dungeon(path: str | Path, *, roller: Roller | None = None) -> DungeonSession:
    """Atalho compatível para consumidores que precisam especificamente da dungeon."""
    session = load_session(path, roller=roller)
    if not isinstance(session, DungeonSession):
        raise ValueError('O cenário informado não é uma dungeon.')
    return session

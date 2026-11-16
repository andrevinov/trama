"""Composição compartilhada da partida; sem visualização ou coordenação alternativa."""

from contextlib import contextmanager
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from trama.application.game_flow import GameFlow
from trama.application.game_runner import GameRunner
from trama.application.scenarios import build_session, load_session
from trama.application.session import GameSession
from trama.application.situations import Situation
from trama.dice import Roller
from trama.infrastructure.openai_config import OpenAIConfig
from trama.infrastructure.call_budget import CallBudget
from trama.infrastructure.openai_services import OpenAIServices, open_services


def compose_game(scenario: GameSession | str | Path | dict, services: OpenAIServices, *, roller: Roller | None = None,
                 setup=None, initial_history=()) -> GameFlow:
    """Aceita cenário ou sessão já preparada; regras e construção continuam compartilhadas."""
    if isinstance(scenario, GameSession):
        if roller is not None:
            raise ValueError('Injete as rolagens ao construir a sessão, não depois de prepará-la.')
        session = scenario
    else:
        session = build_session(scenario, roller=roller) if isinstance(scenario, dict) else load_session(scenario, roller=roller)
    return GameFlow(session, services.interpreter, services.narrator, services.world_director,
                    setup=setup, initial_history=initial_history)


@dataclass(frozen=True)
class GameRuntime:
    flow: GameFlow
    services: OpenAIServices

    @cached_property
    def runner(self) -> GameRunner:
        """Agenda sem janela do mesmo fluxo; só é criada quando solicitada."""
        return GameRunner(self.flow)


@contextmanager
def open_game(scenario, config: OpenAIConfig | None = None, *, roller=None, client=None, allow_unconfigured=False,
              budget: CallBudget | None = None, setup=None, initial_history=()):
    with open_services(config, client=client, allow_unconfigured=allow_unconfigured, budget=budget) as services:
        yield GameRuntime(compose_game(scenario, services, roller=roller, setup=setup, initial_history=initial_history), services)


@contextmanager
def open_situation(situation: Situation, config: OpenAIConfig | None = None, *, roller=None, client=None,
                   allow_unconfigured=False, budget: CallBudget | None = None):
    """Mesma partida da CLI e dos testes; prepara e revalida também ao reiniciar."""
    roller = situation.new_roller() if roller is None else roller
    with open_game(situation.scenario_data(), config, roller=roller, client=client,
                   allow_unconfigured=allow_unconfigured, budget=budget,
                   setup=lambda conversation: situation.initialize(conversation, roller),
                   initial_history=situation.initial_history) as game:
        yield game

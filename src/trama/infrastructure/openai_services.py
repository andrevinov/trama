"""Composição dos adaptadores e ciclo de vida do cliente real da OpenAI."""

from contextlib import contextmanager
from dataclasses import dataclass
import logging
import os
from urllib.parse import urlsplit

import openai
from openai import OpenAI

from trama.infrastructure.openai_config import OpenAIConfig
from trama.infrastructure.call_budget import CallBudget
from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter
from trama.infrastructure.openai_narrator import OpenAINarrator
from trama.infrastructure.openai_world_director import OpenAIWorldDirector

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenAIServices:
    config: OpenAIConfig
    client: OpenAI | None
    interpreter: OpenAIIntentInterpreter | None
    narrator: OpenAINarrator | None
    world_director: OpenAIWorldDirector | None
    metadata: dict


@contextmanager
def open_services(config: OpenAIConfig | None = None, *, client=None, allow_unconfigured=False, budget: CallBudget | None = None):
    """Cliente injetado pertence ao chamador; o criado aqui é fechado inclusive em falhas.

    A opção sem credenciais mantém o simulador visualizável. Live tests não usam
    essa opção: ausência de configuração nunca vira uma execução silenciosa sem IA.
    """
    config = config if config is not None else OpenAIConfig.from_env()
    if not isinstance(config, OpenAIConfig):
        raise ValueError('Use OpenAIConfig para compor os serviços.')
    if budget is not None and not isinstance(budget, CallBudget):
        raise ValueError('Use CallBudget para limitar as chamadas.')
    owned = client is None and not (allow_unconfigured and not os.environ.get('OPENAI_API_KEY'))
    if owned:
        try:
            client = OpenAI(timeout=config.timeout_seconds, max_retries=config.max_retries)
        except Exception:
            logger.exception('ai.services_configuration_failed', extra={'data': {
                **config.metadata(), 'enabled': False, 'sdk_version': openai.__version__,
                'provider_host': None, 'client_source': 'owned', 'status': 'initialization_failed'}})
            raise
    try:
        base_url = getattr(client, 'base_url', None)
        host = urlsplit(str(base_url)).hostname if base_url is not None else None
        metadata = {**config.metadata(), 'enabled': client is not None, 'sdk_version': openai.__version__,
                    'provider_host': host, 'client_source': 'owned' if owned else 'injected' if client is not None else 'unconfigured'}
        if budget is not None:
            metadata['call_budget'] = {'max_calls': budget.max_calls,
                'transport_attempt_upper_bound': budget.max_calls * (config.max_retries + 1)}
        services = OpenAIServices(config, client,
            OpenAIIntentInterpreter(client, config.model, context_mode=config.context_mode,
                max_corrections=config.max_corrections, schema_order=config.schema_order,
                response_options=config.interpretation, budget=budget) if client is not None else None,
            OpenAINarrator(client, config.model, response_options=config.narration, budget=budget) if client is not None else None,
            OpenAIWorldDirector(client, config.model, response_options=config.world, budget=budget) if client is not None else None,
            metadata)
        logger.info('ai.services_configured', extra={'data': metadata})
        yield services
    finally:
        if owned:
            client.close()

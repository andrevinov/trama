"""Registra a configuração efetiva emitida pela composição, inclusive em falhas."""

from copy import deepcopy
import json
import logging

import pytest


@pytest.fixture(autouse=True)
def record_service_configuration(tmp_path):
    configurations = []

    class Recorder(logging.Handler):
        def emit(self, record):
            if record.getMessage() in {'ai.services_configured', 'ai.services_configuration_failed'}:
                configurations.append(deepcopy(record.data))

    logger = logging.getLogger('trama.infrastructure.openai_services')
    handler = Recorder()
    level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level)
        if configurations:
            (tmp_path / 'configurations.json').write_text(json.dumps(configurations, ensure_ascii=False, indent=2) + '\n')

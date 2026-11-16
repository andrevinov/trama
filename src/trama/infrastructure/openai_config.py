"""Configuração explícita e padrões da integração; sem SDK, credenciais ou regras."""

from dataclasses import asdict, dataclass, replace
from math import isfinite
import os

DEFAULT_MODEL = 'gpt-5.6-terra'


@dataclass(frozen=True)
class ResponseOptions:
    max_output_tokens: int = 1000
    reasoning_effort: str = 'low'

    def __post_init__(self):
        if type(self.max_output_tokens) is not int or self.max_output_tokens < 1:
            raise ValueError('O limite de tokens deve ser um inteiro positivo.')
        if not isinstance(self.reasoning_effort, str) or not self.reasoning_effort.strip():
            raise ValueError('Informe o esforço de raciocínio.')


DEFAULT_RESPONSE = ResponseOptions()
DEFAULT_WORLD_RESPONSE = ResponseOptions(max_output_tokens=2000)


@dataclass(frozen=True)
class OpenAIConfig:
    model: str = DEFAULT_MODEL
    timeout_seconds: float = 30
    max_retries: int = 0
    context_mode: str = 'minimal'
    max_corrections: int = 1
    schema_order: str = 'operation-first'
    interpretation: ResponseOptions = DEFAULT_RESPONSE
    narration: ResponseOptions = DEFAULT_RESPONSE
    world: ResponseOptions = DEFAULT_WORLD_RESPONSE
    experiment: str | None = None

    def __post_init__(self):
        if not isinstance(self.model, str) or not self.model.strip() or self.model != self.model.strip():
            raise ValueError('Informe um modelo não vazio, sem espaços nas extremidades.')
        if (type(self.timeout_seconds) not in (int, float) or not isfinite(self.timeout_seconds)
                or self.timeout_seconds <= 0 or type(self.max_retries) is not int or self.max_retries < 0):
            raise ValueError('Timeout deve ser positivo e finito; retries devem ser inteiros não negativos.')
        if (self.context_mode not in ('minimal', 'full') or type(self.max_corrections) is not int
                or self.max_corrections not in (0, 1) or self.schema_order not in ('operation-first', 'legacy')):
            raise ValueError('Configuração de interpretação inválida.')
        if not all(isinstance(o, ResponseOptions) for o in (self.interpretation, self.narration, self.world)):
            raise ValueError('Use ResponseOptions para os parâmetros de cada fase.')
        if self.experiment is not None and (not isinstance(self.experiment, str) or not self.experiment.strip()):
            raise ValueError('Identifique o experimento com texto não vazio.')

    @classmethod
    def from_env(cls, environ=None):
        """Somente o modelo é lido do ambiente; chaves permanecem a cargo do SDK."""
        env = os.environ if environ is None else environ
        return replace(DEFAULT_CONFIG, model=env.get('TRAMA_OPENAI_MODEL', DEFAULT_CONFIG.model))

    def for_experiment(self, name: str, **changes):
        return replace(self, experiment=name, **changes)

    def metadata(self):
        actual, default = asdict(self), asdict(DEFAULT_CONFIG)
        differences = {key: {'default': default[key], 'actual': value}
                       for key, value in actual.items() if key != 'experiment' and value != default[key]}
        return {**actual, 'profile': 'experiment' if self.experiment or differences else 'application_default',
                'experiment': self.experiment or ('configuration_override' if differences else None),
                'differences_from_default': differences}


DEFAULT_CONFIG = OpenAIConfig()

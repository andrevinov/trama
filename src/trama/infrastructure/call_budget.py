"""Limite opcional de chamadas lógicas ao SDK, sem regras de jogo ou preços."""

from threading import Lock
import logging

logger = logging.getLogger(__name__)


class CallBudgetExceeded(ValueError):
    pass


class CallBudget:
    def __init__(self, max_calls: int):
        if type(max_calls) is not int or max_calls < 0:
            raise ValueError('max_calls deve ser um inteiro não negativo.')
        self.max_calls = max_calls
        self._used = 0
        self._exceeded = False
        self._lock = Lock()

    def reserve(self) -> None:
        """Reserva antes de responses.create; falhas de serviço também contam tentativas."""
        with self._lock:
            blocked = self._used >= self.max_calls
            if blocked:
                self._exceeded = True
            else:
                self._used += 1
            used = self._used
        data = {'max_calls': self.max_calls, 'used': used}
        if blocked:
            logger.warning('ai.call_budget_exceeded', extra={'data': data})
            raise CallBudgetExceeded('Orçamento de chamadas ao SDK esgotado; execução incompleta.')
        logger.debug('ai.call_budget_reserved', extra={'data': data})

    def context(self) -> dict:
        with self._lock:
            return {'max_calls': self.max_calls, 'used': self._used,
                    'remaining': self.max_calls - self._used, 'exceeded': self._exceeded}

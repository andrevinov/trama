"""Agenda síncrona do GameFlow, sem janela, SDK, regras ou escolhas implícitas."""

from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
import logging

from trama.application.conversation import ExecutionReport
from trama.application.dialogue import Speech
from trama.application.game_flow import FlowStage, FlowStatus, GameFlow, GameFlowError, ProviderResult
from trama.observability import log_context

logger = logging.getLogger(__name__)


class RunStatus(StrEnum):
    IDLE = 'idle'
    COMPLETED = 'completed'
    AWAITING_REACTION = 'awaiting_reaction'
    FAILED = 'failed'
    REJECTED = 'rejected'
    REQUEST_LIMIT = 'request_limit'
    STALE_RESULT = 'stale_result'


@dataclass(frozen=True)
class RequestTrace:
    request_id: str
    stage: FlowStage
    context: dict
    prompt: str | None
    result: ProviderResult | Exception
    applied: bool


@dataclass(frozen=True)
class RunResult:
    status: RunStatus
    flow_status: FlowStatus
    accepted: bool | None
    requests: tuple[RequestTrace, ...]
    report: ExecutionReport
    reply: Speech | None
    error: Exception | None
    awaiting_reaction: bool
    pending_request_id: str | None


class GameRunner:
    """Conduz o fluxo na thread dona até uma resposta, falha ou limite declarado.

    max_requests limita despachos de FlowRequest nesta invocação, não chamadas
    individuais do SDK: a correção do interpretador pode fazer outra chamada.
    Não há retry nem aceitação/recusa automática de oportunidades.
    """

    def __init__(self, flow: GameFlow):
        flow.check_owner()
        self.flow = flow
        self._dispatched: set[str] = set()

    def _validate(self, max_requests):
        self.flow.check_owner()
        if max_requests is not None and (type(max_requests) is not int or max_requests < 0):
            raise ValueError('max_requests deve ser um inteiro não negativo ou None.')

    def start(self, *, max_requests: int | None = None) -> RunResult:
        self._validate(max_requests)
        return self._run(self.flow.start(), max_requests)

    def submit(self, text: str, *, max_requests: int | None = None) -> RunResult:
        self._validate(max_requests)
        return self._run(self.flow.submit(text), max_requests)

    def choose_opportunity(self, accept: bool, *, max_requests: int | None = None) -> RunResult:
        self._validate(max_requests)
        return self._run(self.flow.choose_opportunity(accept), max_requests)

    def reset(self, *, max_requests: int | None = None) -> RunResult:
        self._validate(max_requests)
        self.flow.reset()
        self._dispatched.clear()
        return self._run(True, max_requests)

    def run_until_input(self, *, max_requests: int | None = None) -> RunResult:
        """Retoma apenas os pedidos pendentes, sem enviar uma nova mensagem."""
        self._validate(max_requests)
        return self._run(None, max_requests)

    def _run(self, accepted, max_requests):
        traces = []
        if accepted is False:
            return self._snapshot(RunStatus.REJECTED, accepted, traces)
        while self.flow.pending_request is not None:
            if max_requests is not None and len(traces) >= max_requests:
                return self._snapshot(RunStatus.REQUEST_LIMIT, accepted, traces)
            request = self.flow.pending_request
            if request.id in self._dispatched:
                raise GameFlowError('Este pedido já foi despachado. Não repita a chamada; reinicie ou entregue seu resultado ao fluxo.')
            self._dispatched.add(request.id)
            context = deepcopy(request.context)
            with log_context(interaction_id=self.flow.interaction_id):
                logger.debug('game_runner.request_dispatched', extra={'data': {
                    'request_id': request.id, 'stage': request.stage}})
            result = request.run()
            applied = self.flow.receive(request.id, result)
            # Exceções são preservadas; o fluxo já as transformou em falha pública.
            recorded = result if isinstance(result, Exception) else deepcopy(result)
            traces.append(RequestTrace(request.id, request.stage, context, request.prompt, recorded, applied))
            if not applied:
                return self._snapshot(RunStatus.STALE_RESULT, accepted, traces)
        if self.flow.status == FlowStatus.FAILED:
            status = RunStatus.FAILED
        elif self.flow.awaiting_reaction:
            status = RunStatus.AWAITING_REACTION
        else:
            status = RunStatus(self.flow.status.value)
        return self._snapshot(status, accepted, traces)

    def _snapshot(self, status, accepted, traces):
        flow = self.flow
        with log_context(interaction_id=flow.interaction_id):
            logger.info('game_runner.stopped', extra={'data': {
                'status': status, 'flow_status': flow.status, 'accepted': accepted,
                'requests_executed': len(traces), 'awaiting_reaction': flow.awaiting_reaction}})
        return RunResult(status, flow.status, accepted, tuple(traces), deepcopy(flow.report),
                         flow.reply, flow.error, flow.awaiting_reaction,
                         flow.pending_request.id if flow.pending_request else None)

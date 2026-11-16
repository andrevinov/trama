"""Coordenação da conversa; chamadas externas separadas da mutação da sessão.

O consumidor executa pending_request.run() na agenda que escolher e devolve o
resultado por receive(). Só o coordenador escolhe a próxima etapa do jogo.
"""

from copy import deepcopy
from dataclasses import dataclass, field, replace
from enum import StrEnum
from functools import partial
import logging
from threading import get_ident
from typing import Callable

from trama.application.authorization import validate_player_plan
from trama.application.conversation import Conversation, ExecutionReport
from trama.application.dialogue import DialogueMessage, Narrator, Speech
from trama.application.intents import ActionPlan, IntentInterpreter
from trama.application.session import GameSession
from trama.application.travel import TravelExecutor
from trama.application.world import WorldDirector, WorldPlan
from trama.distances import format_meters
from trama.observability import current_context, log_context, new_id

logger = logging.getLogger(__name__)


class FlowStatus(StrEnum):
    IDLE = 'idle'
    PENDING = 'pending'
    AWAITING_REACTION = 'awaiting_reaction'
    COMPLETED = 'completed'
    FAILED = 'failed'


class FlowStage(StrEnum):
    INTERPRET = 'interpret'
    WORLD = 'world'
    NPC_TURN = 'npc_turn'
    NARRATE = 'narrate'


class GameFlowError(ValueError):
    """Uso inválido do fluxo ou resposta incompatível com a etapa solicitada."""


ProviderResult = ActionPlan | WorldPlan | Speech


@dataclass(frozen=True)
class FlowRequest:
    id: str
    stage: FlowStage
    context: dict
    prompt: str | None
    _operation: Callable[[dict], ProviderResult] = field(repr=False, compare=False)
    _correlation: dict = field(repr=False, compare=False)

    def run(self) -> ProviderResult | Exception:
        """Executar uma vez por pedido; não acessa nem altera sessão/conversa.

        O adaptador recebe uma cópia do contexto. Exceções voltam como resultado
        para serem tratadas na thread dona, como qualquer outra resposta.
        """
        with log_context(**self._correlation):
            try:
                return self._operation(deepcopy(self.context))
            except Exception as error:
                logger.exception('game_flow.provider_failed', extra={'data': {'stage': self.stage, 'request_id': self.id}})
                return error


class GameFlow:
    def __init__(self, session: GameSession, interpreter: IntentInterpreter | None = None,
                 narrator: Narrator | None = None, world_director: WorldDirector | None = None,
                 *, setup: Callable[[Conversation], None] | None = None,
                 initial_history: tuple[DialogueMessage, ...] = ()) -> None:
        self.session = session
        self.interpreter = interpreter
        self.narrator = narrator
        self.world_director = world_director
        self.conversation = Conversation(session)
        self.status = FlowStatus.IDLE
        self.stage: FlowStage | None = None
        self.pending_request: FlowRequest | None = None
        self.speech = Speech()
        self.report = ExecutionReport()
        self.reply: Speech | None = None
        self.error: Exception | None = None
        self.message = ''
        self.last_prompt = ''
        self.interaction_id: str | None = None
        self._owner = get_ident()
        self._correlation = {}
        self._player_plan: ActionPlan | None = None
        self._narration_context: dict | None = None
        self._npc_turns = 0
        self._deferred_speech: Speech | None = None
        self._paused_report: ExecutionReport | None = None
        self._setup = setup
        self._initial_history = initial_history
        if self._setup is not None:
            self._setup(self.conversation)

    @property
    def pending(self) -> bool:
        return self.pending_request is not None

    @property
    def awaiting_reaction(self) -> bool:
        return not self.pending and self.session.pending_opportunity is not None

    def check_owner(self) -> None:
        """Confere a thread dona antes de agendar chamadas ou alterar o fluxo."""
        if get_ident() != self._owner:
            raise GameFlowError('Altere o fluxo somente na thread dona da sessão.')

    def _begin_interaction(self):
        self.interaction_id = new_id()
        self._correlation = {**current_context(), 'interaction_id': self.interaction_id}
        self.stage = None
        self.error = None
        self.reply = None

    def start(self) -> bool:
        self.check_owner()
        if self.pending or self.status != FlowStatus.IDLE:
            return False
        self._begin_interaction()
        with log_context(**self._correlation):
            try:
                if self.narrator is None:
                    self._fail(GameFlowError('Narrador indisponível. Configure um provedor para iniciar a conversa.'))
                else:
                    self._request_narration(initial=True)
            except Exception as error:
                self._fail(error)
        return True

    def submit(self, raw: str) -> bool:
        self.check_owner()
        if self.pending or not raw.strip():
            return False
        self._begin_interaction()
        with log_context(**self._correlation):
            try:
                self.speech = self.conversation.prepare(raw)
                self.last_prompt = raw.strip()
                if self.session.pending_opportunity and self.speech.on:
                    raise GameFlowError('Escolha atacar com sua reação ou deixar passar para continuar o movimento.')
                if self.speech.on and self.interpreter is None:
                    raise GameFlowError('Interpretador indisponível. Configure um provedor para enviar ações.')
                self.report = ExecutionReport()
                self._player_plan = None
                if not self.session.pending_opportunity:
                    self._npc_turns = 0
                    self._deferred_speech = None
                if not self.speech.on:
                    self._request_narration()
                elif self._npc_active() and self.world_director is not None:
                    self._deferred_speech = self.speech
                    self._continue_turns()
                else:
                    self._request_interpretation()
            except Exception as error:
                self._fail(error)
        return True

    def _request(self, stage: FlowStage, context: dict, operation: Callable[[dict], ProviderResult],
                 *, prompt: str | None = None):
        self.stage = stage
        self.status = FlowStatus.PENDING
        self.pending_request = FlowRequest(new_id(), stage, deepcopy(context), prompt,
                                           operation, self._correlation.copy())
        self.message = {
            FlowStage.INTERPRET: 'Interpretando a ação…', FlowStage.WORLD: 'O Mundo está avaliando sua resposta…',
            FlowStage.NPC_TURN: 'O Mundo está resolvendo o turno dos NPCs…', FlowStage.NARRATE: 'O narrador está respondendo…',
        }[stage]
        logger.debug('game_flow.requested', extra={'data': {'stage': stage, 'request_id': self.pending_request.id}})

    def _request_interpretation(self):
        self._request(FlowStage.INTERPRET, self.conversation.interpretation_context(),
                      partial(self.interpreter.interpret, self.speech.on), prompt=self.speech.on)

    def _request_narration(self, *, initial=False):
        self.stage = FlowStage.NARRATE
        self._narration_context = self.conversation.narration_context(self.speech, self.report, initial=initial)
        if self.narrator is None:
            self._finish(Speech(off=('Narrador indisponível. ' + self._execution_summary()).strip()))
        else:
            self._request(FlowStage.NARRATE, self._narration_context, self.narrator.narrate)

    def receive(self, request_id: str, result: ProviderResult | Exception) -> bool:
        """Aplica um resultado na thread dona; ignora resultados antigos ou duplicados."""
        self.check_owner()
        request = self.pending_request
        if request is None or request.id != request_id:
            with log_context(**self._correlation):
                logger.warning('game_flow.stale_result_ignored', extra={'data': {'request_id': request_id}})
            return False
        with log_context(**self._correlation):
            self.pending_request = None
            try:
                if isinstance(result, Exception):
                    raise result
                expected = {FlowStage.INTERPRET: ActionPlan, FlowStage.WORLD: WorldPlan,
                            FlowStage.NPC_TURN: WorldPlan, FlowStage.NARRATE: Speech}[request.stage]
                if not isinstance(result, expected):
                    raise GameFlowError(f'Resposta incompatível com a etapa {request.stage}.')
                if request.stage == FlowStage.INTERPRET:
                    self._accept_plan(result)
                elif request.stage == FlowStage.NARRATE:
                    self._finish(result)
                elif request.stage == FlowStage.NPC_TURN:
                    self._accept_npc_turn(result)
                else:
                    self._execute_player(result)
            except Exception as error:
                self._fail(error, stage=request.stage)
        return True

    def _accept_plan(self, plan: ActionPlan):
        validate_player_plan(self.speech.on, plan, self.conversation.interpretation_context(), stage='pre_world')
        self._player_plan = plan
        if not plan.steps:
            self.report = self.report.merge(self.conversation.execute(plan, player_prompt=self.speech.on))
            self._request_narration()
        elif self.world_director is None:
            self._execute_player(WorldPlan())
        else:
            self._request(FlowStage.WORLD, self.conversation.world_context(plan), self.world_director.decide)

    def _execute_player(self, world: WorldPlan):
        self.report = self.report.merge(self.conversation.execute(self._player_plan, world, player_prompt=self.speech.on))
        self._continue_turns()

    def _npc_active(self) -> bool:
        combat = self.session.encounter.combat
        return combat is not None and combat.active_id != self.session.encounter.player_id

    def _continue_turns(self):
        alive = self.session.encounter.states[self.session.encounter.player_id].hp > 0
        if self._npc_active() and self.world_director is not None and alive:
            if self._npc_turns >= len(self.session.creatures):
                raise GameFlowError('O Mundo excedeu a sequência de turnos de NPCs; nenhum turno foi repetido.')
            self._request(FlowStage.NPC_TURN, self.conversation.world_context(), self.world_director.decide)
        elif self._deferred_speech is not None and alive:
            self.speech, self._deferred_speech = self._deferred_speech, None
            self._request_interpretation()
        else:
            self._deferred_speech = None
            self._request_narration()

    def _accept_npc_turn(self, world: WorldPlan):
        previous_reason = self.report.stop_reason
        npc_report = self.conversation.execute_npc_turn(world)
        self.report = self.report.merge(npc_report)
        if self.session.pending_opportunity:
            # Guarda os efeitos parciais sem tratar uma escolha resolvida como erro.
            self._paused_report = replace(self.report, stop_reason=previous_reason,
                                          failures=tuple(f for f in self.report.failures if f.code != 'opportunity_pending'))
        else:
            self._npc_turns += 1
        if npc_report.stop_reason:
            self._request_narration()
        else:
            self._continue_turns()

    def choose_opportunity(self, accept: bool) -> bool:
        self.check_owner()
        if type(accept) is not bool:
            raise GameFlowError('A escolha de oportunidade deve ser True ou False.')
        if self.pending:
            return False
        self._begin_interaction()
        with log_context(**self._correlation):
            try:
                continuation = self.conversation.pending_npc_turn
                if continuation is None:
                    raise GameFlowError('Não há movimento de NPC para continuar.')
                event = TravelExecutor(self.session).resolve(accept)
                self.speech = self.conversation.prepare('Faço o ataque de oportunidade.' if accept else
                                                        'Deixo passar sem usar a reação.')
                self.report = (self._paused_report or ExecutionReport()).merge(ExecutionReport(world_events=(event,)))
                self._paused_report = None
                self._accept_npc_turn(continuation)
            except Exception as error:
                self._fail(error)
        return True

    def _finish(self, reply: Speech):
        self.reply = self.conversation.finish(reply, self._narration_context)
        if self._narration_context and self._narration_context['phase'] == 'initial':
            self.conversation.extend_history(self._initial_history)
        self.status = FlowStatus.AWAITING_REACTION if self.session.pending_opportunity else FlowStatus.COMPLETED
        self.message = 'Resposta recebida.'
        logger.info('game_flow.reply_delivered', extra={'data': {'status': self.status}})

    def _execution_summary(self) -> str:
        parts = []
        for event in self.report.events:
            if event['operation'] == 'move':
                parts.append(f"Percorrido {format_meters(event['traveled_meters'])}, custo de {format_meters(event['cost_meters'])}.")
            elif 'summary' in event:
                parts.append(event['summary'])
            elif 'target' in event and 'is_open' in event:
                parts.append(f"{event['target']}: {'aberta' if event['is_open'] else 'fechada'}.")
        return ' '.join(parts)

    def _fail(self, error: Exception, *, stage: str | None = None):
        self.error = error
        self.pending_request = None
        self.status = FlowStatus.FAILED
        reason = str(error).strip() if isinstance(error, ValueError) else ''
        reason = reason or 'Falha ao processar a interação.'
        if (stage or self.stage) in {FlowStage.NARRATE, FlowStage.NPC_TURN}:
            reason = ' '.join(p for p in (reason, self._execution_summary(), self.report.stop_reason) if p)
        self.message = reason.strip()
        self.reply = self.conversation.failure(self.message)
        logger.error('game_flow.failed', extra={'data': {'stage': stage or self.stage, 'reason': self.message}},
                     exc_info=(type(error), error, error.__traceback__))

    def reset(self) -> None:
        """Restaura a partida e pede a abertura; resultados anteriores ficam inválidos."""
        self.check_owner()
        self.pending_request = None
        self.session.reset()
        self.conversation = Conversation(self.session)
        self.status = FlowStatus.IDLE
        self.stage = None
        self.speech = Speech()
        self.report = ExecutionReport()
        self.reply = None
        self.error = None
        self.last_prompt = ''
        self._player_plan = None
        self._narration_context = None
        self._npc_turns = 0
        self._deferred_speech = None
        self._paused_report = None
        try:
            if self._setup is not None:
                self._setup(self.conversation)
        except Exception as error:
            self._fail(error)
            return
        self.start()

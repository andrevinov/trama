"""Janela real delegando ao fluxo real; somente as respostas externas são fixas."""

from threading import Event, Lock, get_ident
from unittest.mock import Mock

import pygame
import pytest

from conftest import sourced_plan
from trama.application.dialogue import Speech
from trama.application.game_flow import GameFlow, FlowStatus
from trama.application.game_runner import GameRunner
from trama.application.intents import ActionPlan, MovementIntent, MovementSegment, RuleIntent
from trama.application.scenarios import build_session
from trama.application.world import WorldAction, WorldPlan, WorldReaction
from trama.spatial import Position
from trama.ui.movement_window import MovementWindow, WINDOW_SIZE


@pytest.fixture
def screen(monkeypatch):
    monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
    pygame.display.init()
    pygame.font.init()
    yield pygame.display.set_mode(WINDOW_SIZE)
    pygame.quit()


class Interpreter:
    def __init__(self, *plans):
        self.plans = iter(plans)
        self.calls = []

    def interpret(self, prompt, context):
        self.calls.append((prompt, context, get_ident()))
        return sourced_plan(next(self.plans), prompt)


class Director:
    def __init__(self, *plans):
        self.plans = iter(plans)
        self.calls = []

    def decide(self, context):
        self.calls.append((context, get_ident()))
        return next(self.plans)


class Narrator:
    def __init__(self):
        self.calls = []

    def narrate(self, context):
        self.calls.append((context, get_ident()))
        return Speech(on='Descrição dos efeitos registrados.', off='Resposta em off.')


def game():
    return build_session(dict(width=10, height=10, start=[4, 4]))


def move(direction='north', squares=2):
    return ActionPlan((MovementIntent((MovementSegment(direction, squares),), False, ''),))


def pump(window):
    result = window.results.get(timeout=3)
    window.results.put(result)
    window.poll()


def click(window, rect):
    window.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1))


def test_window_public_actions_delegate_and_views_reference_flow_state(screen, monkeypatch):
    window = MovementWindow(game(), Interpreter(move()), 'local', Narrator())
    for name in ('start', 'submit', 'receive', 'reset'):
        monkeypatch.setattr(window.flow, name, Mock(wraps=getattr(window.flow, name)))
    assert isinstance(window.flow, GameFlow)
    assert window.session is window.flow.session
    assert window.conversation is window.flow.conversation
    assert window.report is window.flow.report
    window.start()
    window.flow.start.assert_called_once_with()
    pump(window)
    window.input.insert('Ando 3 metros para o norte.')
    window.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
    window.flow.submit.assert_called_once_with('Ando 3 metros para o norte.')
    pump(window)
    pump(window)
    assert window.flow.receive.call_count == 3
    assert window.session.state.position == Position(4, 2)
    assert window.flow.status == FlowStatus.COMPLETED and not window.pending
    old_conversation, old_panel = window.conversation, window.character_panel
    window.sheet_scroll, window.scroll = 200, 140
    click(window, window.reset_button)
    window.flow.reset.assert_called_once_with()
    assert window.conversation is window.flow.conversation and window.conversation is not old_conversation
    assert window.character_panel is not old_panel
    assert window.sheet_scroll == window.scroll == 0
    assert window.session.state.position == Position(4, 4)
    pump(window)
    assert len(window.conversation.messages) == 1
    window.draw(screen)


def test_repeated_frames_dispatch_each_request_only_once(screen):
    release, started = Event(), Event()

    class BlockedInterpreter(Interpreter):
        def interpret(self, prompt, context):
            started.set()
            assert release.wait(3)
            return super().interpret(prompt, context)

    interpreter = BlockedInterpreter(move())
    window = MovementWindow(game(), interpreter, 'local')
    window.input.insert('Ando para o norte.')
    window.submit()
    try:
        assert started.wait(2)
        request = window.flow.pending_request
        for _ in range(5):
            window.poll()
            window.draw(screen)
        assert window.flow.pending_request is request
        assert window.session.state.position == Position(4, 4)
    finally:
        release.set()
    pump(window)
    for _ in range(3):
        window.poll()
    assert len(interpreter.calls) == 1
    assert window.session.state.position == Position(4, 2)
    assert not window.pending and window.results.empty()


def test_providers_run_in_workers_and_mutations_run_in_owner_thread(screen, monkeypatch):
    owner = get_ident()
    interpreter, director, narrator = Interpreter(move()), Director(WorldPlan()), Narrator()
    window = MovementWindow(game(), interpreter, 'local', narrator, director)
    executed = []
    execute = window.session.execute
    receive = window.flow.receive

    def observe_execution(*args, **kwargs):
        executed.append(get_ident())
        return execute(*args, **kwargs)

    received = []

    def observe_receive(*args, **kwargs):
        received.append(get_ident())
        return receive(*args, **kwargs)

    monkeypatch.setattr(window.session, 'execute', observe_execution)
    monkeypatch.setattr(window.flow, 'receive', observe_receive)
    window.input.insert('Ando para o norte.')
    window.submit()
    for _ in range(3):
        pump(window)
    assert received == [owner] * 3
    assert executed == [owner]
    assert interpreter.calls[0][2] != owner
    assert director.calls[0][1] != owner
    assert narrator.calls[0][1] != owner
    assert window.session.state.position == Position(4, 2)


def test_duplicate_worker_result_does_not_repeat_action_or_narration(screen):
    started, release = Event(), Event()

    class BlockedNarrator(Narrator):
        def narrate(self, context):
            started.set()
            assert release.wait(3)
            return super().narrate(context)

    narrator = BlockedNarrator()
    window = MovementWindow(game(), Interpreter(move()), 'local', narrator)
    window.input.insert('Ando para o norte.')
    window.submit()
    result = window.results.get(timeout=3)
    window.results.put(result)
    window.poll()
    try:
        assert started.wait(2)
        narration = window.flow.pending_request
        window.results.put(result)
        window.poll()
        assert window.flow.pending_request is narration
        assert window.session.state.position == Position(4, 2)
    finally:
        release.set()
    pump(window)
    assert len(narrator.calls) == 1
    assert len(window.report.events) == 1
    assert not window.pending


def test_old_worker_completion_after_reset_does_not_replace_new_opening(screen):
    started, release, lock = Event(), Event(), Lock()

    class OpeningNarrator:
        calls = 0

        def narrate(self, context):
            with lock:
                self.calls += 1
                call = self.calls
            if call == 1:
                started.set()
                assert release.wait(3)
            return Speech(on='Abertura antiga.' if call == 1 else 'Abertura nova.')

    narrator = OpeningNarrator()
    window = MovementWindow(game(), None, 'local', narrator)
    window.start()
    try:
        assert started.wait(2)
        old_id = window.flow.pending_request.id
        # Reset pela entrada da janela; os botões continuam bloqueados durante pending.
        window._reset()
        assert window.flow.pending_request.id != old_id
        pump(window)
        assert window.flow.reply.on == 'Abertura nova.'
    finally:
        release.set()
    pump(window)
    assert window.flow.reply.on == 'Abertura nova.'
    assert len(window.conversation.messages) == 1
    assert narrator.calls == 2 and not window.pending


def test_worker_start_failure_is_delivered_to_flow_without_sticking(screen, monkeypatch):
    error = RuntimeError('Falha ao criar worker.')

    class BrokenThread:
        def __init__(self, **kwargs):
            pass

        def start(self):
            raise error

    monkeypatch.setattr('trama.ui.movement_window.Thread', BrokenThread)
    interpreter = Interpreter(move())
    window = MovementWindow(game(), interpreter, 'local')
    window.input.insert('Ando para o norte.')
    window.submit()
    window.poll()
    assert window.flow.status == FlowStatus.FAILED and not window.pending
    assert window.flow.error is error
    assert window.session.state.position == Position(4, 4)
    assert not interpreter.calls
    window.poll()
    assert window.results.empty()


def test_off_during_reaction_does_not_lose_deferred_message_in_window(screen, dice):
    session = build_session(dict(width=8, height=8, start=[2, 3], creatures=[
        dict(id='guard', name='Guarda', position=[3, 3]),
    ]), roller=dice(1, 2, 20))
    session.execute(RuleIntent('start_combat'))
    npc = WorldPlan((WorldReaction(0, 0, (
        WorldAction('guard', 'say', 'Afaste-se!'),
        WorldAction('guard', 'move', 'O guarda recua.', destination=Position(5, 3)),
    )),))
    interpreter, director = Interpreter(move('west', 1)), Director(npc, WorldPlan())
    window = MovementWindow(session, interpreter, 'local', Narrator(), director)
    choose = window.flow.choose_opportunity
    window.flow.choose_opportunity = Mock(wraps=choose)
    window.input.insert('Recuo para oeste.')
    window.submit()
    pump(window)  # NPC antes de interpretar a mensagem.
    pump(window)  # Narração da oportunidade pendente.
    assert window.flow.awaiting_reaction and not interpreter.calls
    window.input.insert('[Qual é a minha opção de reação?]')
    window.submit()
    pump(window)
    click(window, window.reaction_buttons[False])
    window.flow.choose_opportunity.assert_called_once_with(False)
    for _ in range(3):
        pump(window)
    assert interpreter.calls[0][0] == 'Recuo para oeste.'
    assert len(interpreter.calls) == 1
    assert [context['phase'] for context, _ in director.calls] == ['npc_turn', 'player_action']
    assert session.state.position == Position(1, 3)
    assert session.creatures[0].position == Position(5, 3)
    assert window.report.stop_reason is None
    assert len([e for e in window.report.world_events if e['operation'] == 'say']) == 1
    window.draw(screen)


@pytest.mark.parametrize('direction,squares,expected', [('north', 2, Position(4, 2)), ('east', 20, Position(9, 4))])
def test_window_and_headless_runner_have_same_reports_and_contexts(screen, direction, squares, expected):
    def ports():
        return Interpreter(move(direction, squares)), Director(WorldPlan()), Narrator()

    i1, w1, n1 = ports()
    i2, w2, n2 = ports()
    window = MovementWindow(game(), i1, 'local', n1, w1)
    direct = GameFlow(game(), i2, n2, w2)
    runner = GameRunner(direct)
    prompt = 'Ando na direção indicada.'
    window.input.insert(prompt)
    window.submit()
    result = runner.submit(prompt)
    for _ in range(3):
        pump(window)

    def without_correlation(value):
        if isinstance(value, dict):
            return {key: without_correlation(item) for key, item in value.items() if key != 'execution_id'}
        if isinstance(value, list):
            return [without_correlation(item) for item in value]
        return value

    assert window.session.state.position == direct.session.state.position == expected
    assert window.flow.status == direct.status == FlowStatus.COMPLETED
    assert result.status == 'completed' and len(result.requests) == 3
    assert without_correlation(window.report.context()) == without_correlation(direct.report.context())
    assert i1.calls[0][:2] == i2.calls[0][:2]
    assert w1.calls[0][0] == w2.calls[0][0]
    assert without_correlation(n1.calls[0][0]) == without_correlation(n2.calls[0][0])
    assert window.conversation.messages == direct.conversation.messages


@pytest.mark.parametrize('accept', [False, True])
def test_window_and_runner_share_opening_reaction_continuation_and_reset(screen, dice, accept):
    def flow():
        scenario = dict(width=8, height=6, start=[2, 3], creatures=[
            dict(id='guard', name='Guarda', position=[3, 3], hostile=True)])
        session = build_session(scenario, roller=dice(20, 19, 1, *([1] if accept else [])))
        session.execute(RuleIntent('start_combat'))
        npc = WorldPlan((WorldReaction(0, 0, (
            WorldAction('guard', 'move', 'O guarda recua.', destination=Position(5, 3)),
            WorldAction('guard', 'say', 'Afaste-se!'),
        )),))
        return GameFlow(session, Interpreter(ActionPlan((RuleIntent('end_turn'),))),
                        Narrator(), Director(WorldPlan(), npc))

    graphical, direct = flow(), flow()
    window = MovementWindow(graphical.session, graphical.interpreter, 'local', graphical.narrator,
                            graphical.world_director, flow=graphical)
    runner = GameRunner(direct)
    window.start()
    pump(window)
    assert runner.start().status == 'completed'
    assert window.conversation.messages == direct.conversation.messages
    window.input.insert('Encerro meu turno.')
    window.submit()
    paused = runner.submit('Encerro meu turno.')
    for _ in range(4):
        pump(window)
    assert window.flow.awaiting_reaction and paused.status == 'awaiting_reaction'
    assert window.session.creatures == direct.session.creatures
    assert window.conversation.messages == direct.conversation.messages
    click(window, window.reaction_buttons[accept])
    pump(window)
    continued = runner.choose_opportunity(accept)
    assert continued.status == 'completed' and window.flow.status == FlowStatus.COMPLETED
    assert window.session.creatures == direct.session.creatures
    assert window.session.encounter.states == direct.session.encounter.states
    assert window.session.encounter.budgets == direct.session.encounter.budgets
    assert window.session.creatures[0].position == Position(5, 3)
    assert window.session.encounter.states['guard'].hp == (9 if accept else 12)
    assert window.conversation.messages == direct.conversation.messages
    assert len([e for e in continued.report.world_events if e['operation'] == 'say']) == 1
    click(window, window.reset_button)
    pump(window)
    restarted = runner.reset()
    assert restarted.status == 'completed'
    assert window.session.state == direct.session.state == direct.session.initial_state
    assert window.session.encounter.combat is direct.session.encounter.combat is None
    assert window.conversation.messages == direct.conversation.messages
    assert len(direct.conversation.messages) == 1

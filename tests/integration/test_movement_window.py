from threading import Event

import pygame
import pytest

from trama.application.session import GameSession
from trama.application.intents import ActionPlan, MovementIntent, MovementSegment
from trama.infrastructure.openai_intent_interpreter import InterpretationError
from trama.movement import Grid, MovementState, Position
from trama.ui.movement_window import ACCENT, CELL_SIZE, GRID_ORIGIN, WINDOW_SIZE, MovementWindow


@pytest.fixture
def screen(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.display.init()
    pygame.font.init()
    yield pygame.display.set_mode(WINDOW_SIZE)
    pygame.quit()


def make_session():
    return GameSession(Grid(10, 10), MovementState(Position(4, 4)))


def test_typing_prompt_async_interpretation_validation_and_rendering(screen):
    release = Event()

    class FakeInterpreter:
        def interpret(self, prompt, context):
            assert prompt == "ande duas casas para cima"
            assert context["character"]["column"] == 5
            assert context["character"]["row"] == 5
            assert release.wait(2)
            return ActionPlan((MovementIntent((MovementSegment("north", 2),), False, ""),))

    session = make_session()
    window = MovementWindow(session, FakeInterpreter(), "simulado")
    window.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="ande duas casas para cima"))
    window.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
    assert window.pending
    # Enquanto a resposta está pendente, os botões não alteram o snapshot enviado.
    for button in (window.next_button, window.reset_button, window.send_button):
        window.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=button.center, button=1))
    assert session.state == session.initial_state
    window.draw(screen)
    release.set()
    result = window.results.get(timeout=2)
    window.results.put(result)
    window.poll()
    assert not window.pending
    assert session.state.position == Position(4, 2)
    assert session.state.remaining_meters == 6
    assert len(session.last_path) == 3
    window.draw(screen)
    pixel = (GRID_ORIGIN[0] + 4 * CELL_SIZE + CELL_SIZE // 2,
             GRID_ORIGIN[1] + 2 * CELL_SIZE + CELL_SIZE // 2)
    assert screen.get_at(pixel)[:3] == ACCENT
    assert window.input.text == ""


def test_interpretation_failure_keeps_window_and_state_usable(screen):
    window = MovementWindow(make_session(), None, "simulado")
    window.results.put(InterpretationError("Serviço indisponível"))
    window.pending = True
    window.poll()
    assert window.failed
    assert not window.pending
    assert window.session.state == window.session.initial_state
    assert window.message == "Serviço indisponível"
    window.draw(screen)


def test_missing_credentials_does_not_start_a_request(screen):
    window = MovementWindow(make_session(), None, "simulado")
    window.input.insert("ande uma casa para cima")
    window.submit()
    assert not window.pending
    assert "OPENAI_API_KEY" in window.message
    assert window.session.state == window.session.initial_state


def test_edit_unicode_input_and_recover_from_invalid_movement(screen):
    window = MovementWindow(make_session(), None, "simulado")
    window.input.insert("vá para o sul")
    window.input.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_CTRL))
    window.input.insert("ação")
    assert window.input.text == "ação"
    window.results.put(ActionPlan((MovementIntent((MovementSegment("east", 20),), False, ""),)))
    window.poll()
    assert not window.failed
    assert "limites" in window.conversation.messages[-1].speech.off
    assert window.session.state.position == Position(9, 4)
    window.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=window.next_button.center, button=1))
    assert window.session.state.turn == 2
    window.draw(screen)


def test_named_scene_is_sent_to_interpreter_and_large_map_is_drawn(screen):
    import json
    from pathlib import Path
    from trama.scene import Scene

    data = json.loads((Path(__file__).resolve().parents[2] / "pocs/movimento/cela_guardas.json").read_text())
    scene = Scene.from_data(data)
    session = GameSession(scene.grid, MovementState(Position(*data["start"])), scene)

    class FakeInterpreter:
        def interpret(self, prompt, context):
            assert context["character"]["current_area"] == "cell"
            assert prompt == "correr até a porta da Sala dos Guardas"
            return ActionPlan((MovementIntent((), True, "", "guard_door"),))

    window = MovementWindow(session, FakeInterpreter(), "simulado")
    window.input.insert("correr até a porta da Sala dos Guardas")
    window.submit()
    result = window.results.get(timeout=2)
    window.results.put(result)
    window.poll()
    assert not window.failed
    assert session.state.position == Position(12, 5)
    window.draw(screen)
    cell = window.cell_size
    pixel = (GRID_ORIGIN[0] + 12 * cell + cell // 2, GRID_ORIGIN[1] + 5 * cell + cell // 2)
    assert screen.get_at(pixel)[:3] == ACCENT


def test_door_actions_update_rendered_visibility_and_hide_guards(screen):
    import json
    from pathlib import Path
    from trama.application.intents import DoorIntent
    from trama.creatures import creatures_from_data
    from trama.scene import Scene
    from trama.ui.movement_window import RED

    data = json.loads((Path(__file__).resolve().parents[2] / "pocs/movimento/cela_guardas.json").read_text())
    scene = Scene.from_data(data)
    session = GameSession(scene.grid, MovementState(Position(*data["start"])), scene,
                          creatures_from_data(data["creatures"]))
    window = MovementWindow(session, None, "simulado")

    def guards_drawn():
        window.draw(screen)
        count = 0
        for creature in session.creatures:
            x0 = GRID_ORIGIN[0] + creature.position.x * window.cell_size
            y0 = GRID_ORIGIN[1] + creature.position.y * window.cell_size
            if any(screen.get_at((x, y))[:3] == RED
                   for y in range(y0, y0 + window.cell_size)
                   for x in range(x0, x0 + window.cell_size)):
                count += 1
        return count

    assert guards_drawn() == 0
    session.execute(MovementIntent((), True, "", "guard_door"))
    window.results.put(ActionPlan((DoorIntent("open", "guard_door"),)))
    window.poll()
    assert not window.failed
    assert "aberta" in window.conversation.messages[-1].speech.off
    assert guards_drawn() == 3
    session.next_turn()
    window.results.put(ActionPlan((DoorIntent("close", "guard_door"),)))
    window.poll()
    assert "fechada" in window.conversation.messages[-1].speech.off
    assert guards_drawn() == 0


def test_window_displays_meter_speed_budget_grid_and_execution_message(screen, monkeypatch):
    original_font = pygame.font.Font
    rendered = []

    class RecordingFont:
        def __init__(self, *args, **kwargs):
            self.font = original_font(*args, **kwargs)

        def render(self, text, *args, **kwargs):
            rendered.append(text)
            return self.font.render(text, *args, **kwargs)

        def __getattr__(self, name):
            return getattr(self.font, name)

    monkeypatch.setattr(pygame.font, "Font", RecordingFont)
    session = make_session()
    window = MovementWindow(session, None, "simulado")
    window.results.put(ActionPlan((MovementIntent((MovementSegment("east", 1),), False, ""),)))
    window.poll()
    window.draw(screen)
    assert "Velocidade: 9 m" in rendered
    assert "Movimento restante: 7,5 m" in rendered
    assert any("grade de 1,5 m" in line for line in rendered)
    assert "custo de 1,5 m" in window.conversation.messages[-1].speech.off
    assert not any("pés" in line for line in rendered)


def pump(window):
    result = window.results.get(timeout=3)
    window.results.put(result)
    window.poll()


def test_initial_narration_and_mixed_prompt_flow_with_partial_execution(screen):
    from decimal import Decimal
    from trama.application.dialogue import Speech

    class FakeInterpreter:
        def __init__(self):
            self.prompts = []

        def interpret(self, prompt, context):
            self.prompts.append(prompt)
            assert "Como funciona Dash" not in str(context)
            return ActionPlan((MovementIntent((MovementSegment("north", 3, Decimal("0.5")),), False, ""),))

    class FakeNarrator:
        def __init__(self):
            self.requests = []

        def narrate(self, context):
            self.requests.append(context)
            if context["phase"] == "initial":
                return Speech("Você está no tabuleiro iluminado.")
            assert context["player"]["off"] == "Como funciona Dash?"
            assert context["execution"]["events"][0]["traveled_meters"] == 4.5
            return Speech("Você caminhou 4,5 m para o norte.", "Dash acrescenta movimento igual à velocidade.")

    interpreter, narrator = FakeInterpreter(), FakeNarrator()
    window = MovementWindow(make_session(), interpreter, "simulado", narrator)
    window.start()
    assert window.pending
    pump(window)
    assert window.conversation.messages[0].speech.on == "Você está no tabuleiro iluminado."
    window.input.insert("Ande 5 m para o norte.\n[Como funciona Dash?]")
    window.submit()
    pump(window)
    assert window.pending  # Execução já ocorreu; ainda falta a narração.
    assert window.session.state.position == Position(4, 1)
    pump(window)
    assert not window.pending
    assert interpreter.prompts == ["Ande 5 m para o norte."]
    reply = window.conversation.messages[-1].speech
    assert "4,5 m" in reply.on
    assert "Dash" in reply.off
    assert "0,5 m" in reply.off
    assert len(window.conversation.messages) == 3
    window.draw(screen)


def test_off_only_does_not_call_interpreter_or_execute_actions(screen):
    from trama.application.dialogue import Speech

    class MustNotInterpret:
        def interpret(self, prompt, context):
            raise AssertionError("Fala off não pode ser interpretada como ação")

    class FakeNarrator:
        def narrate(self, context):
            assert context["player"]["off"] == "Ande 3 m. Quanto posso andar?"
            return Speech("Você andou 3 m.", "Seu saldo é 9 m.")

    window = MovementWindow(make_session(), MustNotInterpret(), "simulado", FakeNarrator())
    window.input.insert("[Ande 3 m. Quanto posso andar?]")
    window.submit()
    pump(window)
    assert window.session.state == window.session.initial_state
    assert window.conversation.messages[-1].speech.on == ""
    assert window.conversation.messages[-1].speech.off == "Seu saldo é 9 m."


def test_narration_failure_preserves_executed_movement_without_replay(screen):
    from trama.application.dialogue import NarrationError

    class FakeInterpreter:
        def interpret(self, prompt, context):
            return ActionPlan((MovementIntent((MovementSegment("north", 2),), False, ""),))

    class FailedNarrator:
        def narrate(self, context):
            raise NarrationError("Serviço indisponível")

    window = MovementWindow(make_session(), FakeInterpreter(), "simulado", FailedNarrator())
    window.input.insert("Ande duas casas para o norte")
    window.submit()
    pump(window)
    state = window.session.state
    pump(window)
    assert window.failed
    assert not window.pending
    assert window.session.state == state
    assert state.position == Position(4, 2)
    assert state.spent_meters == 3
    assert "Percorrido 3 m" in window.conversation.messages[-1].speech.off
    window.poll()
    assert window.session.state == state


def test_conversation_scroll_and_multiline_input(screen):
    window = MovementWindow(make_session(), None, "simulado")
    for i in range(20):
        window.conversation.failure(f"Mensagem {i}: " + "Uma explicação longa. " * 10)
    window.draw(screen)
    window.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=4))
    window.draw(screen)
    assert window.scroll > 0
    window.input.insert("Ande 3 m.")
    window.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=pygame.KMOD_SHIFT))
    window.input.insert("[Quanto resta?]")
    assert window.input.text == "Ande 3 m.\n[Quanto resta?]"
    assert not window.pending

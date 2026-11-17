from conftest import sourced_plan, scripted_responses
from threading import Event

import pygame
import pytest

from trama.application.session import GameSession
from trama.application.intents import ActionPlan, MovementIntent, MovementSegment
from trama.application.dialogue import Speech
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


class FixedInterpreter:
    """Respostas locais explícitas; mensagens passam pela entrada real do fluxo."""
    def __init__(self, *plans):
        self.plans = iter(plans)
        self.calls = []

    def interpret(self, prompt, context):
        self.calls.append((prompt, context))
        return sourced_plan(next(self.plans), prompt)


class FixedNarrator:
    def narrate(self, context):
        return Speech(on="Descrição do cenário.")


def test_typing_prompt_async_interpretation_validation_and_rendering(screen):
    release = Event()

    class FakeInterpreter:
        def interpret(self, prompt, context):
            assert prompt == "ande duas casas para cima"
            assert context["character"]["column"] == 5
            assert context["character"]["row"] == 5
            assert release.wait(2)
            return sourced_plan(ActionPlan((MovementIntent((MovementSegment("north", 2),), False, ""),)), prompt)

    session = make_session()
    window = MovementWindow(session, FakeInterpreter(), "simulado")
    window.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="ande duas casas para cima"))
    window.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
    assert window.pending
    # Enquanto a resposta está pendente, os botões não alteram o snapshot enviado.
    for button in (window.reset_button, window.send_button):
        window.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=button.center, button=1))
    assert session.state == session.initial_state
    window.draw(screen)
    release.set()
    result = window.results.get(timeout=2)
    window.results.put(result)
    window.poll()
    assert not window.pending
    assert session.state.position == Position(4, 2)
    assert session.interpreter_context()["character"]["remaining_meters"] is None
    assert len(session.last_path) == 3
    window.draw(screen)
    pixel = (GRID_ORIGIN[0] + 4 * CELL_SIZE + CELL_SIZE // 2,
             GRID_ORIGIN[1] + 2 * CELL_SIZE + CELL_SIZE // 2)
    assert screen.get_at(pixel)[:3] == ACCENT
    assert window.input.text == ""


def test_interpretation_failure_keeps_window_and_state_usable(screen):
    class FailedInterpreter:
        def interpret(self, prompt, context):
            raise InterpretationError("Serviço indisponível")

    window = MovementWindow(make_session(), FailedInterpreter(), "simulado")
    window.input.insert("Ando para o norte.")
    window.submit()
    pump(window)
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
    interpreter = FixedInterpreter(ActionPlan((MovementIntent((MovementSegment("east", 20),), False, ""),)))
    window = MovementWindow(make_session(), interpreter, "simulado")
    window.input.insert("vá para o sul")
    window.input.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_CTRL))
    window.input.insert("ação")
    assert window.input.text == "ação"
    window.input.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_CTRL))
    window.input.insert("Ande vinte casas para leste.")
    window.submit()
    pump(window)
    assert not window.failed
    assert "limites" in window.conversation.messages[-1].speech.off
    assert window.session.state.position == Position(9, 4)
    assert not hasattr(window, "next_button")
    assert window.session.state.turn == 1
    window.draw(screen)


def test_named_scene_is_sent_to_interpreter_and_large_map_is_drawn(screen):
    import json
    from pathlib import Path
    from trama.scene import Scene

    data = json.loads((Path(__file__).resolve().parents[2] / "tests/fixtures/scenarios/legacy_cell_and_guards.json").read_text())
    scene = Scene.from_data(data)
    session = GameSession(scene.grid, MovementState(Position(*data["start"])), scene)

    class FakeInterpreter:
        def interpret(self, prompt, context):
            assert context["character"]["current_area"] == "cell"
            assert prompt == "correr até a porta da Sala dos Guardas"
            return sourced_plan(ActionPlan((MovementIntent((), True, "", "guard_door"),)), prompt)

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

    data = json.loads((Path(__file__).resolve().parents[2] / "tests/fixtures/scenarios/legacy_cell_and_guards.json").read_text())
    scene = Scene.from_data(data)
    session = GameSession(scene.grid, MovementState(Position(*data["start"])), scene,
                          creatures_from_data(data["creatures"]))
    interpreter = FixedInterpreter(ActionPlan((DoorIntent("open", "guard_door"),)),
                                   ActionPlan((DoorIntent("close", "guard_door"),)))
    window = MovementWindow(session, interpreter, "simulado")

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
    window.input.insert("Abra a porta da Sala dos Guardas.")
    window.submit()
    pump(window)
    assert not window.failed
    assert "aberta" in window.conversation.messages[-1].speech.off
    assert guards_drawn() == 3
    session.next_turn()
    window.input.insert("Feche a porta da Sala dos Guardas.")
    window.submit()
    pump(window)
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
    window = MovementWindow(session, FixedInterpreter(ActionPlan((MovementIntent((MovementSegment("east", 1),), False, ""),))), "simulado")
    window.input.insert("Ande uma casa para leste.")
    window.submit()
    pump(window)
    window.draw(screen)
    assert "Velocidade: 9 m" in rendered
    assert "Movimento sem limite de turno" in rendered
    assert any("grade de 1,5 m" in line for line in rendered)
    assert "custo de 1,5 m" in window.conversation.messages[-1].speech.off
    assert not any("pés" in line for line in rendered)


def pump(window):
    result = window.results.get(timeout=3)
    window.results.put(result)
    window.poll()


def test_untrusted_interpreter_cannot_spend_resource_or_consult_world_for_walk(screen):
    from unittest.mock import Mock
    from trama.application.intents import RuleIntent

    interpreter = Mock()
    interpreter.interpret.return_value = ActionPlan((RuleIntent("second_wind"),))
    world = Mock()
    session = make_session()
    states = session.encounter.states.copy()
    window = MovementWindow(session, interpreter, "simulado", world_director=world)
    window.input.insert("Ande 3 m para o norte.")
    window.submit()
    pump(window)
    assert window.failed and not window.pending
    assert session.state == session.initial_state and session.encounter.states == states
    world.decide.assert_not_called()


def test_on_question_with_no_actions_skips_world_and_requests_only_answer(screen):
    from unittest.mock import Mock
    from trama.application.dialogue import Speech
    from trama.application.intents import RequestPart

    prompt = "Posso usar Retomar o Fôlego?"
    interpreter, world, narrator = Mock(), Mock(), Mock()
    interpreter.interpret.return_value = ActionPlan((), (RequestPart(prompt, "question"),))
    narrator.narrate.return_value = Speech(off="É uma ação bônus e consome um uso.")
    window = MovementWindow(make_session(), interpreter, "simulado", narrator, world)
    resources = window.session.encounter.states.copy()
    window.input.insert(prompt)
    window.submit()
    pump(window)
    pump(window)
    assert not window.pending and not window.failed
    world.decide.assert_not_called()
    assert narrator.narrate.call_args.args[0]["execution"]["questions"] == [prompt]
    assert window.session.encounter.states == resources
    assert window.session.state == window.session.initial_state
    assert window.conversation.messages[-1].speech.off


def test_off_question_keeps_failed_npc_execution_after_window_report_reset(screen, dice):
    from trama.application.dialogue import Speech
    from trama.application.intents import RuleIntent
    from trama.application.world import WorldAction, WorldPlan, WorldReaction
    from trama.creatures import Creature

    session = GameSession(Grid(8, 8, blocked=frozenset({Position(5, 3)})), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda 1", Position(5, 4)),), roller=dice(20, 19, 1))
    session.execute(RuleIntent("start_combat"))

    class Interpreter:
        calls = 0
        def interpret(self, prompt, context):
            self.calls += 1
            return sourced_plan(ActionPlan((RuleIntent("end_turn"),)), prompt)

    class World:
        calls = 0
        def decide(self, context):
            self.calls += 1
            if context["phase"] == "player_action":
                return WorldPlan()
            return WorldPlan((WorldReaction(0, 0, (
                WorldAction("g1", "move", "Tenta se aproximar.", destination=Position(5, 3)),
                WorldAction("g1", "attack", "Ataca o Jogador.", "player"),
            )),))

    class Narrator:
        contexts = []
        def narrate(self, context):
            self.contexts.append(context)
            return Speech(off="O guarda tentou entrar em (6,4), uma casa bloqueada. O ataque seguinte não aconteceu e o turno dele foi encerrado.")

    interpreter, world, narrator = Interpreter(), World(), Narrator()
    window = MovementWindow(session, interpreter, "simulado", narrator, world)
    window.input.insert("Encerro meu turno.")
    window.submit()
    for _ in range(4):
        pump(window)
    assert not window.pending and session.encounter.combat.active_id == "player"
    execution_id = window.report.execution_id
    states = session.encounter.states.copy()
    window.input.insert("[Ele não me atacou por quê?]")
    window.submit()
    pump(window)
    context = narrator.contexts[-1]
    assert context["execution"]["stop_reason"] is None
    assert context["previous_execution"]["execution_id"] == execution_id
    failure = context["previous_execution"]["execution"]["failures"][0]
    assert failure["code"] == "destination_blocked" and failure["destination"] == [6, 4]
    assert failure["skipped_actions"][0]["operation"] == "attack"
    assert interpreter.calls == 1 and world.calls == 2 and len(narrator.contexts) == 2
    assert not window.failed and not window.pending
    assert session.encounter.states == states and session.encounter.combat.active_id == "player"
    assert not context['previous_execution']['situation']['turn_pending']


def test_separate_player_world_and_narration_requests_execute_in_main_thread(screen):
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import Mock
    from trama.creatures import creatures_from_data
    from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter
    from trama.infrastructure.openai_world_director import OpenAIWorldDirector
    from trama.infrastructure.openai_narrator import OpenAINarrator
    from trama.scene import Scene

    data = json.loads((Path(__file__).resolve().parents[2] / "tests/fixtures/scenarios/legacy_cell_and_guards.json").read_text())
    scene = Scene.from_data(data)
    session = GameSession(scene.grid, MovementState(Position(*data["start"])), scene, creatures_from_data(data["creatures"]))
    client = Mock()
    outputs = [
        {"steps": [{"operation": "move", "target_id": "guard_door", "segments": [], "dash": False, "clarification": ""}]},
        {"reactions": []},
        {"on": "Você atravessa o corredor e para diante da porta fechada.", "off": ""},
    ]
    client.responses.create.side_effect = scripted_responses(*[SimpleNamespace(status="completed", output=[], output_text=json.dumps(value)) for value in outputs])
    window = MovementWindow(session, OpenAIIntentInterpreter(client), "simulado", OpenAINarrator(client), OpenAIWorldDirector(client))
    window.input.insert("Eu caminho até a direção da porta da sala dos guardas.")
    window.submit()
    pump(window)  # Interpretação concluída; consulta ao Mundo ainda não altera a posição.
    assert session.state == session.initial_state and window.stage == "world"
    pump(window)  # Mundo sem impedimento; execução local e pedido de narração.
    assert session.state.position == Position(12, 5) and window.stage == "narrate"
    pump(window)
    assert not window.pending and not window.failed
    assert window.conversation.messages[-1].speech.on
    names = [call.kwargs["text"]["format"]["name"] for call in client.responses.create.call_args_list]
    assert names == ["action_plan", "world_response", "narrator_reply"]
    request = json.loads(client.responses.create.call_args_list[-1].kwargs["input"])
    assert request["execution"]["player_movement"] == {
        "occurred": True, "traveled_meters": 13.5, "from": [4, 6], "to": [13, 6],
    }
    assert session.mode == "narrated" and not session.budget.action_used
    window.draw(screen)
    def center(position):
        return (GRID_ORIGIN[0] + position.x * window.cell_size + window.cell_size // 2,
                GRID_ORIGIN[1] + position.y * window.cell_size + window.cell_size // 2)
    assert screen.get_at(center(Position(12, 5)))[:3] == ACCENT
    assert screen.get_at(center(Position(3, 5)))[:3] != ACCENT


@pytest.mark.parametrize("prompt", ["Encerro meu turno.", "Eu fico parado na mesma posição.",
                                   "Não faço nada.", "Não faço mais nada nesta vez.", "Aguardo."])
def test_npc_turns_advance_via_world_decisions_and_return_to_player(screen, dice, prompt):
    from trama.application.intents import RuleIntent
    from trama.application.world import WorldPlan
    from trama.application.dialogue import Speech
    from trama.creatures import Creature

    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda 1", Position(5, 4)),), roller=dice(20, 19, 1))
    session.execute(RuleIntent("start_combat"))

    class Interpreter:
        def interpret(self, prompt, context):
            return sourced_plan(ActionPlan((RuleIntent("end_turn"),)), prompt)

    class World:
        def __init__(self):
            self.phases = []

        def decide(self, context):
            self.phases.append(context["phase"])
            return WorldPlan()

    class Narrator:
        def narrate(self, context):
            assert context["combat"]["player_turn"]
            return Speech("O guarda aguarda. É sua vez novamente.")

    world = World()
    window = MovementWindow(session, Interpreter(), "simulado", Narrator(), world)
    window.input.insert(prompt)
    window.submit()
    for _ in range(4):
        pump(window)
    assert world.phases == ["player_action", "npc_turn"]
    assert session.encounter.combat.active_id == "player" and session.state.turn == 2
    assert not window.pending


def test_initial_narration_and_mixed_prompt_flow_with_partial_execution(screen):
    from decimal import Decimal
    from trama.application.dialogue import Speech

    class FakeInterpreter:
        def __init__(self):
            self.prompts = []

        def interpret(self, prompt, context):
            self.prompts.append(prompt)
            assert "Como funciona Dash" not in str(context)
            return sourced_plan(ActionPlan((MovementIntent((MovementSegment("north", 3, Decimal("0.5")),), False, ""),)), prompt)

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
            return sourced_plan(ActionPlan((MovementIntent((MovementSegment("north", 2),), False, ""),)), prompt)

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
    assert state.spent_meters == 0
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


def test_sheet_tab_scrolls_and_can_be_opened_while_waiting(screen, monkeypatch):
    window = MovementWindow(make_session(), None, "simulado", FixedNarrator())
    window.start()
    assert window.pending
    window.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=window.tabs["Ficha"].center, button=1))
    assert window.active_tab == "Ficha"
    old = window.session.state
    window.draw(screen)
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (100, 200))
    window.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, y=-5))
    window.draw(screen)
    assert window.sheet_scroll > 0 and window.scroll == 0
    assert window.session.state == old


def test_sheet_sections_and_click_details_preserve_game_state(screen, monkeypatch):
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
    window = MovementWindow(make_session(), None, "simulado", FixedNarrator())
    window.active_tab = "Ficha"
    window.start()  # Consulta deve funcionar mesmo durante uma chamada à IA.
    assert window.pending
    before = (window.session.state, window.session.budget, window.session.encounter.states.copy())
    window.draw(screen)
    assert any("Guerreiro 3" in text for text in rendered)
    assert any("PV 28/28" in text for text in rendered)
    assert any("Campeão" in text for text in rendered)
    assert "O que posso fazer" in rendered
    assert "Caminhar" in rendered
    assert "Bônus · 2/2 usos" in rendered
    assert not any("Força: 17" in text for text in rendered)
    panel = window.character_panel
    def click(rect):
        window.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=rect.center, button=1))
        window.draw(screen)

    click(panel.item_rects["move"])
    assert "move" in panel.expanded
    assert any("Como pedir: Caminho" in text for text in rendered)
    click(panel.item_rects["move"])
    assert "move" not in panel.expanded
    click(panel.section_rects["data"])
    assert window.sheet_scroll == 0
    click(panel.item_rects["attributes"])
    assert any("Força: 17 (+3)" in text for text in rendered)
    window.sheet_scroll = 10000
    window.draw(screen)
    click(panel.item_rects["traits"])
    assert any("Crítico Aprimorado" in text for text in rendered)
    assert any("Atleta Notável" in text for text in rendered)
    click(panel.section_rects["resources"])
    assert window.sheet_scroll == 0
    assert "Fora do turno e recuperação" in rendered
    assert "Não implementado" in rendered
    window.sheet_scroll = 10000
    window.draw(screen)
    assert "Itens mágicos" in rendered
    assert "Nenhum efeito registrado" in rendered
    assert (window.session.state, window.session.budget, window.session.encounter.states) == before


def test_sheet_clicks_use_only_visible_headers_after_scroll(screen):
    window = MovementWindow(make_session(), None, "simulado")
    window.active_tab = "Ficha"
    window.draw(screen)
    old_position = window.character_panel.item_rects["move"].center
    window.sheet_scroll = 10000
    window.draw(screen)
    assert "move" not in window.character_panel.item_rects
    window.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=old_position, button=1))
    assert "move" not in window.character_panel.expanded


@pytest.mark.parametrize("accept", [True, False])
def test_opportunity_buttons_resume_npc_without_new_interpretation(screen, dice, accept):
    from trama.application.world import WorldAction, WorldPlan, WorldReaction
    from trama.creatures import Creature

    from trama.application.intents import RuleIntent

    session = GameSession(Grid(8, 8), MovementState(Position(2, 3)),
                          creatures=(Creature("g1", "Guarda 1", Position(3, 3)),), roller=dice(20, 19, 1))
    session.encounter.start(("g1",))
    world = WorldPlan((WorldReaction(0, 0, (
        WorldAction("g1", "move", "O guarda recua.", destination=Position(5, 3)),
    )),))
    class Director:
        def __init__(self):
            self.calls = []

        def decide(self, context):
            self.calls.append(context)
            return WorldPlan() if context['phase'] == 'player_action' else world

    director = Director()
    interpreter = FixedInterpreter(ActionPlan((RuleIntent('end_turn'),)))
    window = MovementWindow(session, interpreter, "simulado", world_director=director)
    window.input.insert('Encerro meu turno.')
    window.submit()
    for _ in range(3):
        pump(window)
    assert session.pending_opportunity
    window.draw(screen)
    session.encounter.roller = dice(1) if accept else dice()
    window.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=window.reaction_buttons[accept].center, button=1))
    assert session.pending_opportunity is None
    assert session.creatures[0].position == Position(5, 3)
    assert session.encounter.combat.active_id == "player"
    assert session.encounter.states["g1"].hp == (9 if accept else 12)
    assert len(interpreter.calls) == 1 and len(director.calls) == 2
    assert window.conversation.messages[0].speech.on
    window.draw(screen)


def test_enemy_tab_and_combat_controls_respect_visibility_and_turns(screen, dice):
    from trama.application.intents import RuleIntent
    from trama.creatures import Creature
    from trama.ui.character_panel import enemy_paragraphs

    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda 1", Position(5, 4)),), roller=dice(15, 16, 10))
    window = MovementWindow(session, None, "simulado")
    window.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=window.tabs["Inimigos"].center, button=1))
    window.draw(screen)
    lines = enemy_paragraphs(session.visible_enemy_summaries())
    assert any("Guarda 1" in text for text in lines) and any("PV 12/12" in text for text in lines)
    zero_hp_enemy = {**session.visible_enemy_summaries()[0], "hp": 0, "at_zero_hp": True}
    assert "PV zerados (0 PV)" in enemy_paragraphs([zero_hp_enemy])
    assert enemy_paragraphs([])[0] == "Nenhum inimigo visível."
    session.execute(RuleIntent("start_combat"))
    assert session.encounter.combat.active_id == "player"
    window.draw(screen)
    session.execute(RuleIntent("end_turn"))
    assert session.encounter.combat.active_id == "g1"
    window.draw(screen)
    from trama.application.world import WorldPlan
    window.conversation.execute_npc_turn(WorldPlan())
    assert session.encounter.combat.active_id == "player"


def test_combat_report_fallback_and_failed_narration_preserve_resolved_attack(screen, dice):
    from trama.application.dialogue import NarrationError
    from trama.application.intents import RuleIntent
    from trama.creatures import Creature

    class FailedNarrator:
        def narrate(self, context):
            raise NarrationError("Falha simulada")

    session = GameSession(Grid(10, 10), MovementState(Position(4, 4)),
                          creatures=(Creature("g1", "Guarda 1", Position(5, 4)),), roller=dice(15, 16, 10, 15, 1, 2))
    session.execute(RuleIntent("start_combat"))
    interpreter = FixedInterpreter(ActionPlan((RuleIntent("attack", "g1", "flail"),)))
    window = MovementWindow(session, interpreter, "simulado", FailedNarrator())
    window.input.insert('Ataco o Guarda 1 com o mangual.')
    window.submit()
    pump(window)
    pump(window)
    assert window.failed and not window.pending
    assert session.encounter.states["g1"].hp == 7 and not session.budget.action_available
    assert "5 de dano" in window.conversation.messages[-1].speech.off
    window.poll()
    assert session.encounter.states["g1"].hp == 7


def test_narrated_window_has_no_combat_or_turn_buttons(screen):
    window = MovementWindow(make_session(), None, "simulado")
    assert not hasattr(window, "combat_button")
    assert not hasattr(window, "next_button")
    assert window.session.encounter.combat is None
    window.draw(screen)


def test_logging_correlates_ai_threads_and_game_execution_without_frame_spam(screen, capture_logs):
    import json
    from types import SimpleNamespace
    from unittest.mock import Mock
    from trama.infrastructure.openai_intent_interpreter import OpenAIIntentInterpreter
    from trama.infrastructure.openai_narrator import OpenAINarrator

    move = {"operation": "move", "target_id": None, "dash": False, "clarification": "",
            "segments": [{"direction": "north", "distance": 1.5, "unit": "meters"}]}
    client = Mock()
    client.responses.create.side_effect = scripted_responses(*[
        SimpleNamespace(status="completed", output=[], output_text=json.dumps({"steps": [move]})),
        SimpleNamespace(status="completed", output=[], output_text=json.dumps({"on": "Você andou 1,5 m.", "off": ""})),
    ])
    with capture_logs() as stream:
        window = MovementWindow(make_session(), OpenAIIntentInterpreter(client), "simulado", OpenAINarrator(client))
        window.input.insert("Ande 1,5 m para o norte.")
        window.submit()
        pump(window)
        pump(window)
        window.draw(screen)
        before = stream.getvalue()
        window.draw(screen)
        window.poll()
        assert stream.getvalue() == before
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    involved = [r for r in records if r["event"] in {"ui.message_submitted", "ai.request_started", "ai.decision",
                                                    "movement.resolved", "game.operation_completed", "conversation.reply_delivered"}]
    assert {r["interaction_id"] for r in involved} == {window.interaction_id}
    assert window.interaction_id and not window.pending
    calls = [r["ai_call_id"] for r in records if r["event"] == "ai.request_started"]
    assert len(calls) == len(set(calls)) == 2 and all(calls)
    movement = next(r for r in records if r["event"] == "movement.resolved")
    assert movement["operation_id"]
    assert window.session.state.position == Position(4, 3)

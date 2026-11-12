"""Janela da POC. Rede em thread separada; estado e desenho na thread principal."""

from queue import Empty, Queue
from threading import Thread

import pygame

from trama.application.intents import ActionPlan, IntentInterpreter, InterpretationError
from trama.application.dialogue import Narrator, NarrationError, Speech
from trama.application.conversation import Conversation, ExecutionReport
from trama.application.session import GameSession
from trama.actions import ActionError, DoorActionResult
from trama.movement import MovementError
from trama.spatial import Position
from trama.distances import CELL_METERS, format_meters

BACKGROUND = (20, 26, 35)
PANEL = (31, 40, 52)
TEXT = (233, 239, 244)
MUTED = (163, 180, 196)
ACCENT = (91, 217, 190)
GOLD = (230, 183, 96)
RED = (247, 149, 145)
GRID_ORIGIN = (52, 104)
CELL_SIZE = 46
WINDOW_SIZE = (1040, 900)


def character_lines(text: str, font, width: int) -> list[str]:
    lines = [""]
    for char in text:
        if char == "\n":
            lines.append("")
        elif font.size(lines[-1] + char)[0] > width:
            lines.append(char)
        else:
            lines[-1] += char
    return lines


def word_lines(text: str, font, width: int) -> list[str]:
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
        while paragraph:
            count = 0
            while count < len(paragraph) and font.size(paragraph[:count + 1])[0] <= width:
                count += 1
            count = max(1, count)
            if count < len(paragraph):
                split = paragraph.rfind(" ", 0, count + 1)
                if split > 0:
                    count = split
            lines.append(paragraph[:count])
            paragraph = paragraph[count:].lstrip()
    return lines


class PromptInput:
    """Campo de linha única com cursor, seleção total e colagem de texto."""

    def __init__(self) -> None:
        self.text = ""
        self.cursor = 0
        self.selected = False

    def insert(self, text: str) -> None:
        text = "".join(c for c in text if c.isprintable() or c == "\n")
        if self.selected:
            self.text, self.cursor, self.selected = "", 0, False
        text = text[:2000 - len(self.text)]
        self.text = self.text[:self.cursor] + text + self.text[self.cursor:]
        self.cursor += len(text)

    def handle(self, event: pygame.event.Event) -> None:
        if event.type == pygame.TEXTINPUT:
            self.insert(event.text)
        elif event.type == pygame.KEYDOWN:
            control = event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)
            if control and event.key == pygame.K_a:
                self.selected = True
            elif control and event.key == pygame.K_v:
                try:
                    self.insert(pygame.scrap.get_text())
                except pygame.error:
                    pass
            elif event.key in (pygame.K_BACKSPACE, pygame.K_DELETE):
                if self.selected:
                    self.text, self.cursor, self.selected = "", 0, False
                elif event.key == pygame.K_BACKSPACE and self.cursor:
                    self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]
                    self.cursor -= 1
                elif event.key == pygame.K_DELETE:
                    self.text = self.text[:self.cursor] + self.text[self.cursor + 1:]
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_HOME, pygame.K_END):
                if event.key == pygame.K_HOME:
                    self.cursor = 0
                elif event.key == pygame.K_END:
                    self.cursor = len(self.text)
                else:
                    self.cursor = max(0, min(len(self.text), self.cursor + (1 if event.key == pygame.K_RIGHT else -1)))
                self.selected = False


class MovementWindow:
    def __init__(
        self, session: GameSession, interpreter: IntentInterpreter | None,
        model: str, narrator: Narrator | None = None,
    ) -> None:
        self.cell_size = min(CELL_SIZE, 460 // session.grid.width, 460 // session.grid.height)
        if self.cell_size < 12:
            raise ValueError("O mapa é grande demais para esta janela.")
        self.session = session
        self.interpreter = interpreter
        self.narrator = narrator
        self.conversation = Conversation(session)
        self.speech = Speech()
        self.report = ExecutionReport()
        self.narration_request: dict | None = None
        self.stage = "interpret"
        self.scroll = 0
        self._chat_key = None
        self._chat_lines = []
        self.model = model
        self.input = PromptInput()
        self.pending = False
        self.results: Queue[ActionPlan | Speech | Exception] = Queue()
        self.message = "Digite um pedido abaixo e pressione Enter. Cada casa mede 1,5 m."
        if interpreter is None:
            self.message = "Configure OPENAI_API_KEY no ambiente e reinicie para enviar pedidos."
        self.failed = False
        self.last_prompt = ""
        self.send_button = pygame.Rect(878, 798, 130, 56)
        self.next_button = pygame.Rect(52, 550, 200, 42)
        self.reset_button = pygame.Rect(270, 550, 242, 42)
        self.input_rect = pygame.Rect(32, 798, 830, 56)

    def _worker(self, operation) -> None:
        self.pending = True
        def run() -> None:
            try:
                self.results.put(operation())
            except Exception as error:
                self.results.put(error)
        Thread(target=run, daemon=True).start()

    def start(self) -> None:
        if self.narrator is not None:
            self._request_narration(self.conversation.narration_context(initial=True))
        elif not self.conversation.messages:
            self.conversation.failure("Configure OPENAI_API_KEY e reinicie para conversar com o narrador.")

    def _request_narration(self, context: dict) -> None:
        self.narration_request = context
        self.stage = "narrate"
        self.message = "O narrador está respondendo…"
        if self.narrator is not None:
            self._worker(lambda: self.narrator.narrate(context))
        else:
            # Resultado local explícito quando o provedor não está configurado.
            details = self._execution_summary()
            self._finish(Speech(off="Narrador indisponível. " + details))

    def _execution_summary(self) -> str:
        parts = []
        for event in self.report.events:
            if event["operation"] == "move":
                parts.append(f"Percorrido {format_meters(event['traveled_meters'])}, custo de {format_meters(event['cost_meters'])}.")
            elif event["changed"]:
                parts.append(f"{event['target']}: {'aberta' if event['is_open'] else 'fechada'}.")
        return " ".join(parts)

    def _finish(self, reply: Speech) -> None:
        self.conversation.finish(reply, self.narration_request)
        self.pending = False
        self.failed = False
        self.scroll = 0
        self.message = "Resposta recebida."

    def submit(self) -> None:
        if self.pending or not self.input.text.strip():
            return
        try:
            self.speech = self.conversation.prepare(self.input.text)
        except ValueError as error:
            self.conversation.failure(str(error))
            self.message, self.failed = str(error), True
            self.scroll = 0
            return
        self.last_prompt = self.input.text.strip()
        if self.speech.on and self.interpreter is None:
            self.message = "Configure OPENAI_API_KEY no ambiente e reinicie para enviar pedidos."
            self.conversation.failure(self.message)
            self.failed = True
            self.scroll = 0
            return
        self.input = PromptInput()
        self.scroll = 0
        self.failed = False
        self.report = ExecutionReport()
        if not self.speech.on:
            self._request_narration(self.conversation.narration_context(self.speech))
            return
        context = self.conversation.interpretation_context()
        self.stage = "interpret"
        self.message = "Interpretando a ação…"
        self._worker(lambda: self.interpreter.interpret(self.speech.on, context))

    def poll(self) -> None:
        try:
            result = self.results.get_nowait()
        except Empty:
            return
        if isinstance(result, Exception):
            self.pending = False
            self.failed = True
            reason = str(result) if isinstance(result, (InterpretationError, NarrationError)) else "Falha no serviço de IA."
            if self.stage == "narrate":
                # A narração falhar não desfaz nem repete as ações já realizadas.
                reason += " " + self._execution_summary()
                if self.report.stop_reason:
                    reason += " " + self.report.stop_reason
            self.message = reason.strip()
            self.conversation.failure(self.message)
            self.scroll = 0
            return
        if isinstance(result, Speech):
            self._finish(result)
            return
        self.report = self.conversation.execute(result)
        self._request_narration(self.conversation.narration_context(self.speech, self.report))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return False
        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll + event.y * 60)
            return True
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self.scroll = max(0, self.scroll + (300 if event.key == pygame.K_PAGEUP else -300))
            return True
        if self.pending:
            return True
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if getattr(event, "mod", 0) & pygame.KMOD_SHIFT:
                self.input.insert("\n")
            else:
                self.submit()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.send_button.collidepoint(event.pos):
                self.submit()
            elif self.next_button.collidepoint(event.pos):
                self.session.next_turn()
                self.failed = False
                self.message = "Novo turno: movimento, ação e interação renovados."
                self.conversation.failure(self.message)
                self.scroll = 0
            elif self.reset_button.collidepoint(event.pos):
                self.session.reset()
                self.failed = False
                self.message = "Cenário reiniciado."
                self.conversation = Conversation(self.session)
                self.report = ExecutionReport()
                self.start()
        else:
            self.input.handle(event)
        return True

    def _draw_conversation(self, screen: pygame.Surface, font) -> None:
        pygame.draw.rect(screen, PANEL, (550, 252, 458, 438), border_radius=10)
        screen.blit(font.render("Conversa · roda do mouse / PgUp / PgDn", True, MUTED), (568, 266))
        viewport = pygame.Rect(566, 297, 426, 377)
        key = (id(self.conversation), len(self.conversation.messages), viewport.width)
        if key != self._chat_key:
            lines = []
            for message in self.conversation.messages:
                role = "Você" if message.role == "player" else "Narrador"
                lines.append((role, ACCENT if message.role == "player" else TEXT))
                for text, color in ((message.speech.on, TEXT),
                                    (f"[{message.speech.off}]" if message.speech.off else "", GOLD)):
                    if text:
                        lines.extend((line, color) for line in word_lines(text, font, viewport.width - 8))
                lines.append(("", MUTED))
            self._chat_key, self._chat_lines = key, lines
        lines = self._chat_lines
        total = len(lines) * 21
        self.scroll = min(self.scroll, max(0, total - viewport.height))
        y = viewport.bottom - total + self.scroll if total > viewport.height else viewport.y
        old_clip = screen.get_clip()
        screen.set_clip(viewport)
        for line, color in lines:
            if viewport.y - 21 < y < viewport.bottom:
                screen.blit(font.render(line, True, color), (viewport.x, y))
            y += 21
        screen.set_clip(old_clip)

    def draw(self, screen: pygame.Surface) -> None:
        font = pygame.font.Font(None, 25)
        small = pygame.font.Font(None, 22)
        title = pygame.font.Font(None, 38)
        screen.fill(BACKGROUND)

        def label(text: str, x: int, y: int, color=TEXT, face=font) -> None:
            screen.blit(face.render(text, True, color), (x, y))

        def paragraph(text: str, x: int, y: int, width: int, lines: int, color=MUTED) -> None:
            # Quebra inclusive palavras longas, mantendo toda mensagem dentro do painel.
            remaining = text
            for line_number in range(lines):
                if not remaining:
                    break
                count = 0
                while count < len(remaining) and small.size(remaining[:count + 1])[0] <= width:
                    count += 1
                if count < len(remaining):
                    split = remaining.rfind(" ", 0, count)
                    if split > 0:
                        count = split
                line, remaining = remaining[:count], remaining[count:].lstrip()
                if line_number == lines - 1 and remaining:
                    line = line[:-3] + "…"
                label(line, x, y + line_number * 23, color, small)

        label("TRAMA / Cela e Guardas", 32, 18, face=title)
        label("D&D 2024 · grade de 1,5 m · norte para cima", 32, 60, MUTED)
        cell_size = self.cell_size
        scene = self.session.scene
        visibility = self.session.visibility

        def center(p: Position) -> tuple[int, int]:
            return (GRID_ORIGIN[0] + p.x * cell_size + cell_size // 2,
                    GRID_ORIGIN[1] + p.y * cell_size + cell_size // 2)

        coordinate_font = pygame.font.Font(None, min(22, cell_size - 3))
        area_colors = ((44, 62, 77), (40, 64, 60), (69, 56, 49))
        for y in range(self.session.grid.height):
            label(str(y + 1), 26, GRID_ORIGIN[1] + y * cell_size + cell_size // 3, MUTED, coordinate_font)
            for x in range(self.session.grid.width):
                p = Position(x, y)
                rect = pygame.Rect(GRID_ORIGIN[0] + x * cell_size,
                                   GRID_ORIGIN[1] + y * cell_size, cell_size, cell_size)
                color = (45, 56, 69) if (x + y) % 2 else (39, 50, 63)
                if scene:
                    for area, area_color in zip(scene.areas, area_colors, strict=False):
                        if p in area.cells:
                            color = area_color
                if p in self.session.grid.blocked:
                    color = (109, 124, 142)
                elif p in self.session.grid.difficult:
                    color = (108, 80, 43)
                if p not in visibility.visible:
                    color = tuple(max(12, component // 4) for component in color)
                elif p in visibility.lightly_obscured:
                    color = tuple(component * 2 // 3 for component in color)
                pygame.draw.rect(screen, color, rect)
                pygame.draw.rect(screen, BACKGROUND, rect, 1)
        for x in range(self.session.grid.width):
            label(str(x + 1), GRID_ORIGIN[0] + x * cell_size + cell_size // 3, 82, MUTED, coordinate_font)
        if scene:
            for area in scene.areas:
                # Nomes dentro dos cômodos, acima do percurso central.
                x = GRID_ORIGIN[0] + area.x * cell_size + 4
                y = GRID_ORIGIN[1] + area.y * cell_size + 5
                paragraph(area.name, x, y, area.width * cell_size - 8, 2, TEXT)
                if area.description:
                    paragraph(format_meters(area.width * CELL_METERS), x, y + 48, area.width * cell_size - 8, 1, MUTED)
            for passage in scene.passages:
                if passage.position not in visibility.visible:
                    continue
                cx, cy = center(passage.position)
                radius = cell_size // 2 - 3
                if passage.kind == "gate":
                    # Grade aberta recolhida na lateral; fechada ocupa a passagem.
                    bars_x = cx - radius if passage.is_open else cx
                    for offset in (-4, 0, 4):
                        pygame.draw.line(screen, ACCENT, (bars_x + offset, cy - radius),
                                         (bars_x + offset, cy + radius), 2)
                else:
                    door = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)
                    pygame.draw.rect(screen, GOLD, door, 2 if passage.is_open else 0)
                    if not passage.is_open:
                        pygame.draw.circle(screen, BACKGROUND, (cx + radius // 2, cy), 2)
        if len(self.session.last_path) > 1:
            pygame.draw.lines(screen, GOLD, False, [center(p) for p in self.session.last_path], 3)
        for number, creature in enumerate(self.session.creatures, 1):
            if creature.position in visibility.visible:
                cx, cy = center(creature.position)
                pygame.draw.circle(screen, RED, (cx, cy), max(5, cell_size // 2 - 3))
                label(str(number), cx - 4, cy - 7, BACKGROUND, small)
        radius = max(4, min(15, cell_size // 2 - 4))
        pygame.draw.circle(screen, ACCENT, center(self.session.state.position), radius)
        pygame.draw.circle(screen, TEXT, center(self.session.state.position), radius, 2)
        if scene:
            details_y = GRID_ORIGIN[1] + self.session.grid.height * cell_size + 20
            for passage in scene.passages:
                if passage.position not in visibility.visible:
                    paragraph(f"{passage.name}: fora de visão.", 52, details_y, 460, 2, MUTED)
                    details_y += 48
                    continue
                state_label = "aberta" if passage.is_open else "fechada"
                lock_label = "trancada" if passage.locked else "destrancada"
                paragraph(f"{passage.name}: {state_label}, {lock_label}.",
                          52, details_y, 460, 2, ACCENT if passage.is_open else GOLD)
                details_y += 48
            visible_guards = [c for c in self.session.creatures if c.position in visibility.visible]
            label(f"Guardas visíveis: {len(visible_guards)}", 52, details_y, RED, small)
            label("Humano · visão normal · áreas claras: visão atual", 52, details_y + 28, MUTED, small)
        label("Colunas: direita / Linhas: baixo", 52, 603, MUTED, small)
        pygame.draw.rect(screen, PANEL, (550, 104, 458, 132), border_radius=10)
        state = self.session.state
        label(f"Turno {state.turn}", 570, 114, ACCENT, title)
        label(f"Posição: coluna {state.position.x + 1}, linha {state.position.y + 1}", 570, 153, TEXT, small)
        label(f"Velocidade: {format_meters(state.speed_meters)}", 570, 180, TEXT, small)
        label(f"Movimento restante: {format_meters(state.remaining_meters)}", 738, 180, TEXT, small)
        action_label = "utilizada" if self.session.budget.action_used else "disponível"
        interaction_label = "usada" if self.session.budget.free_interaction_used else "livre"
        label(f"Ação: {action_label} · interação: {interaction_label}", 570, 208, MUTED, small)
        for rect, text in ((self.next_button, "Novo turno"), (self.reset_button, "Reiniciar cenário"),
                           (self.send_button, "Aguarde…" if self.pending else "Enviar")):
            pygame.draw.rect(screen, (53, 67, 80) if self.pending else (46, 90, 87), rect, border_radius=6)
            label(text, rect.x + 14, rect.y + 12, MUTED if self.pending else TEXT)
        label("On: ações e narrativa · [Off: regras e dúvidas]", 52, 620, MUTED, small)
        paragraph("Ex.: Entre no Corredor. [Quanto movimento me resta?]", 52, 650, 460, 2)
        self._draw_conversation(screen, small)
        pygame.draw.rect(screen, PANEL, (32, 712, 976, 44), border_radius=6)
        paragraph(self.message, 46, 717, 948, 2, RED if self.failed else ACCENT)
        label("Sua mensagem · Shift+Enter: nova linha", 32, 772)
        label(f"{len(self.input.text)}/2000 caracteres", 690, 772, MUTED, small)
        pygame.draw.rect(screen, PANEL, self.input_rect, border_radius=6)
        pygame.draw.rect(screen, ACCENT, self.input_rect, 1, border_radius=6)
        old_clip = screen.get_clip()
        screen.set_clip(self.input_rect.inflate(-16, -8))
        before = self.input.text[:self.input.cursor]
        lines_before = character_lines(before, font, self.input_rect.width - 28)
        all_lines = character_lines(self.input.text, font, self.input_rect.width - 28)
        first_line = max(0, len(lines_before) - 2)
        if self.input.selected:
            pygame.draw.rect(screen, (49, 91, 112), self.input_rect.inflate(-18, -12))
        for i, line in enumerate(all_lines[first_line:first_line + 2]):
            label(line, self.input_rect.x + 12, self.input_rect.y + 7 + i * 22)
        if not self.input.text:
            label("Digite sua ação e/ou uma pergunta [em off]…", self.input_rect.x + 12,
                  self.input_rect.y + 12, MUTED)
        if not self.pending and pygame.time.get_ticks() % 1000 < 600:
            cx = self.input_rect.x + 12 + font.size(lines_before[-1])[0]
            cy = self.input_rect.y + 7 + (len(lines_before) - 1 - first_line) * 22
            pygame.draw.line(screen, ACCENT, (cx, cy), (cx, cy + 20), 2)
        screen.set_clip(old_clip)
        paragraph(f"Enter: enviar · Ctrl+V: colar · Ctrl+A: selecionar · Esc: sair · modelo: {self.model}",
                  32, 876, 976, 1)


def run_window(session: GameSession, interpreter: IntentInterpreter | None, model: str,
               narrator: Narrator | None = None) -> None:
    pygame.display.init()
    pygame.font.init()
    try:
        screen = pygame.display.set_mode(WINDOW_SIZE)
        pygame.display.set_caption("Trama — conversa e mapa")
        pygame.key.start_text_input()
        pygame.key.set_text_input_rect(pygame.Rect(32, 798, 830, 56))
        pygame.key.set_repeat(400, 35)
        window = MovementWindow(session, interpreter, model, narrator)
        window.start()
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if not window.handle_event(event):
                    running = False
                    break
            window.poll()
            window.draw(screen)
            pygame.display.flip()
            clock.tick(30)
    finally:
        pygame.quit()

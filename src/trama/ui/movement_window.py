"""Janela da POC. Rede em thread separada; estado e desenho na thread principal."""

from queue import Empty, Queue
from threading import Thread
from contextvars import copy_context
import logging

import pygame

from trama.application.intents import ActionPlan, IntentInterpreter, InterpretationError, RuleIntent
from trama.application.dialogue import Narrator, NarrationError, Speech
from trama.application.conversation import Conversation, ExecutionReport
from trama.application.session import GameSession
from trama.application.authorization import PlanAuthorizationError, validate_player_plan
from trama.application.world import WorldDirector, WorldPlan, WorldError
from trama.application.travel import TravelExecutor
from trama.spatial import Position
from trama.distances import CELL_METERS, format_meters
from trama.ui.text import word_lines
from trama.ui.character_panel import CharacterPanel, draw_panel, enemy_paragraphs
from trama.observability import log_context, new_id

logger = logging.getLogger(__name__)

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
        model: str, narrator: Narrator | None = None, world_director: WorldDirector | None = None,
    ) -> None:
        self.cell_size = min(CELL_SIZE, 460 // session.grid.width, (380 if session.map_view()["compact"] else 460) // session.grid.height)
        if self.cell_size < 12:
            raise ValueError("O mapa é grande demais para esta janela.")
        self.session = session
        self.interpreter = interpreter
        self.narrator = narrator
        self.world_director = world_director
        self.player_plan: ActionPlan | None = None
        self.resume_player = False
        self.npc_turns = 0
        self.conversation = Conversation(session)
        self.speech = Speech()
        self.report = ExecutionReport()
        self.narration_request: dict | None = None
        self.stage = "interpret"
        self.scroll = 0
        self.active_tab = "Jogo"
        self.sheet_scroll = 0
        self.character_panel = CharacterPanel()
        self.tabs = {name: pygame.Rect(550 + i * 156, 60, 146, 34)
                     for i, name in enumerate(("Jogo", "Ficha", "Inimigos"))}
        self._chat_key = None
        self._chat_lines = []
        self.model = model
        self.input = PromptInput()
        self.pending = False
        self.interaction_id: str | None = None
        self.results: Queue[ActionPlan | Speech | Exception] = Queue()
        self.message = "Digite um pedido abaixo e pressione Enter. Cada casa mede 1,5 m."
        if interpreter is None:
            self.message = "Configure OPENAI_API_KEY no ambiente e reinicie para enviar pedidos."
        self.failed = False
        self.last_prompt = ""
        self.send_button = pygame.Rect(878, 798, 130, 56)
        self.reset_button = pygame.Rect(362, 550, 150, 42)
        self.input_rect = pygame.Rect(32, 798, 830, 56)
        self.reaction_buttons = {True: pygame.Rect(568, 210, 204, 26),
                                 False: pygame.Rect(780, 210, 208, 26)}

    def _worker(self, operation) -> None:
        self.pending = True
        def run() -> None:
            try:
                self.results.put(operation())
            except Exception as error:
                logger.exception("ui.worker_failed", extra={"data": {"stage": self.stage}})
                self.results.put(error)
        context = copy_context()
        Thread(target=context.run, args=(run,), daemon=True).start()

    def start(self) -> None:
        self.interaction_id = new_id()
        with log_context(interaction_id=self.interaction_id):
            self._start()

    def _start(self) -> None:
        logger.info("ui.initial_description_requested")
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
            elif "summary" in event:
                parts.append(event["summary"])
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
        self.interaction_id = new_id()
        with log_context(interaction_id=self.interaction_id):
            self._submit()

    def _submit(self) -> None:
        logger.info("ui.message_submitted", extra={"data": {"length": len(self.input.text)}})
        try:
            self.speech = self.conversation.prepare(self.input.text)
        except ValueError as error:
            logger.warning("ui.message_rejected", extra={"data": {"reason": str(error)}}, exc_info=True)
            self.conversation.failure(str(error))
            self.message, self.failed = str(error), True
            self.scroll = 0
            return
        self.last_prompt = self.input.text.strip()
        if self.session.pending_opportunity and self.speech.on:
            self.message = "Escolha Atacar (reação) ou Deixar passar para continuar o movimento."
            self.conversation.failure(self.message)
            return
        if self.speech.on and self.interpreter is None:
            logger.warning("ui.interpreter_unavailable")
            self.message = "Configure OPENAI_API_KEY no ambiente e reinicie para enviar pedidos."
            self.conversation.failure(self.message)
            self.failed = True
            self.scroll = 0
            return
        self.input = PromptInput()
        self.scroll = 0
        self.failed = False
        self.report = ExecutionReport()
        self.player_plan = None
        self.npc_turns = 0
        if not self.speech.on:
            self._request_narration(self.conversation.narration_context(self.speech))
            return
        if self._npc_active() and self.world_director is not None:
            self.resume_player = True
            self._request_npc_turn()
        else:
            self._request_interpretation()

    def _request_interpretation(self):
        context = self.conversation.interpretation_context()
        self.stage = "interpret"
        self.message = "Interpretando a ação…"
        self._worker(lambda: self.interpreter.interpret(self.speech.on, context))

    def _npc_active(self):
        combat = self.session.encounter.combat
        return combat is not None and combat.active_id != self.session.encounter.player_id

    def _request_npc_turn(self):
        if self._npc_active() and self.world_director is not None and self.session.encounter.states[self.session.encounter.player_id].hp > 0:
            if self.npc_turns >= len(self.session.creatures):
                self.conversation.failure("O Mundo excedeu a sequência de turnos de NPCs; nenhum turno foi repetido.")
                self.pending = False
                return
            self.stage = "npc_turn"
            self.message = "O Mundo está resolvendo o turno dos guardas…"
            context = self.conversation.world_context()
            self._worker(lambda: self.world_director.decide(context))
        elif self.resume_player:
            self.resume_player = False
            self._request_interpretation()
        else:
            self._request_narration(self.conversation.narration_context(self.speech, self.report))

    def poll(self) -> None:
        with log_context(interaction_id=self.interaction_id):
            self._poll()

    def _poll(self) -> None:
        try:
            result = self.results.get_nowait()
        except Empty:
            return
        if isinstance(result, ActionPlan) and self.speech.on:
            try:
                validate_player_plan(self.speech.on, result, self.conversation.interpretation_context(), stage="pre_world")
            except PlanAuthorizationError as error:
                result = error
        if isinstance(result, Exception):
            logger.error("ui.request_failed", extra={"data": {"stage": self.stage}},
                         exc_info=(type(result), result, result.__traceback__))
            self.pending = False
            self.failed = True
            reason = str(result) if isinstance(result, (InterpretationError, NarrationError, WorldError)) else "Falha no serviço de IA."
            if self.stage in {"narrate", "npc_turn"}:
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
        if isinstance(result, ActionPlan):
            self.player_plan = result
            if not result.steps:
                self.report = self.conversation.execute(result, player_prompt=self.speech.on)
                self._request_narration(self.conversation.narration_context(self.speech, self.report))
                return
            if self.world_director is not None:
                context = self.conversation.world_context(result)
                self.stage = "world"
                self.message = "O Mundo está avaliando sua resposta…"
                self._worker(lambda: self.world_director.decide(context))
                return
            result = WorldPlan()
        if isinstance(result, WorldPlan):
            try:
                if self.stage == "npc_turn":
                    npc_report = self.conversation.execute_npc_turn(result)
                    self.report = self.report.merge(npc_report)
                    if not self.session.pending_opportunity:
                        self.npc_turns += 1
                    if npc_report.stop_reason:
                        # Erro ou reação pendente pausa o turno, sem repetir ações já realizadas.
                        self._request_narration(self.conversation.narration_context(self.speech, self.report))
                        return
                else:
                    self.report = self.report.merge(self.conversation.execute(self.player_plan, result, player_prompt=self.speech.on or None))
                self._request_npc_turn()
            except (WorldError, PlanAuthorizationError) as error:
                self.pending = False
                self.failed = True
                self.message = str(error)
                self.conversation.failure(self.message)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return False
        if event.type == pygame.MOUSEWHEEL:
            if self.active_tab != "Jogo" and pygame.Rect(32, 104, 480, 438).collidepoint(pygame.mouse.get_pos()):
                self.sheet_scroll = max(0, self.sheet_scroll - event.y * 60)
                self.character_panel.item_rects.clear()
            else:
                self.scroll = max(0, self.scroll + event.y * 60)
            return True
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self.scroll = max(0, self.scroll + (300 if event.key == pygame.K_PAGEUP else -300))
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for name, rect in self.tabs.items():
                if rect.collidepoint(event.pos):
                    self.active_tab, self.sheet_scroll = name, 0
                    self.character_panel.item_rects.clear()
                    return True
            if self.active_tab == "Ficha":
                clicked = self.character_panel.click(event.pos)
                if clicked:
                    if clicked == "section":
                        self.sheet_scroll = 0
                    return True
        if self.pending:
            return True
        if self.session.pending_opportunity and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for accept, rect in self.reaction_buttons.items():
                if rect.collidepoint(event.pos):
                    self._choose_opportunity(accept)
                    return True
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if getattr(event, "mod", 0) & pygame.KMOD_SHIFT:
                self.input.insert("\n")
            else:
                self.submit()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.send_button.collidepoint(event.pos):
                self.submit()
            elif self.reset_button.collidepoint(event.pos):
                self._reset()
        else:
            self.input.handle(event)
        return True

    def _choose_opportunity(self, accept: bool) -> None:
        self.interaction_id = new_id()
        with log_context(interaction_id=self.interaction_id):
            continuation = self.conversation.pending_npc_turn
            if continuation is None:
                raise WorldError("Não há movimento de NPC para continuar.")
            event = TravelExecutor(self.session).resolve(accept)
            self.speech = self.conversation.prepare("Faço o ataque de oportunidade." if accept else "Deixo passar sem usar a reação.")
            self.report = ExecutionReport(world_events=(event,))
            report = self.conversation.execute_npc_turn(continuation)
            self.report = self.report.merge(report)
            if not self.session.pending_opportunity:
                self.npc_turns += 1
            if report.stop_reason:
                self._request_narration(self.conversation.narration_context(self.speech, self.report))
            else:
                self._request_npc_turn()

    def _reset(self) -> None:
        with log_context(interaction_id=new_id(), operation_id=new_id()):
            logger.info("ui.reset_requested")
            self.session.reset()
            self.failed = False
            self.message = "Cenário reiniciado."
            self.conversation = Conversation(self.session)
            self.report = ExecutionReport()
            self.character_panel = CharacterPanel()
            self.sheet_scroll = 0
        self.start()

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

        map_view = self.session.map_view()
        label("TRAMA / " + map_view["title"], 32, 18, face=title)
        label("D&D 2024 · grade de 1,5 m · norte para cima", 32, 60, MUTED)
        for name, rect in self.tabs.items():
            pygame.draw.rect(screen, (46, 90, 87) if self.active_tab == name else PANEL, rect, border_radius=6)
            label(name, rect.x + 24, rect.y + 7)
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
                if p in (scene.grid.blocked if scene else self.session.grid.blocked):
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
                if map_view['compact']:
                    if area.cells & visibility.visible:
                        map_font = pygame.font.Font(None, 16)
                        label(area.name if area.width > 2 else '3 m', x, y, TEXT, map_font)
                else:
                    paragraph(area.name, x, y, area.width * cell_size - 8, 2, TEXT)
                if area.description and not map_view['compact']:
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
        for marker in map_view['markers']:
            if marker['kind'] != 'scene_object':
                continue
            position = Position(marker['position'][0] - 1, marker['position'][1] - 1)
            cx, cy = center(position)
            attachment = marker['attachment']
            if attachment['surface'] == 'wall':
                dx, dy = {'north': (0, -1), 'east': (1, 0),
                          'south': (0, 1), 'west': (-1, 0)}[attachment['side']]
                offset = cell_size // 2 - 3
                cx, cy = cx + dx * offset, cy + dy * offset
                pygame.draw.line(screen, MUTED, (cx, cy), (cx + dx * 3, cy + dy * 3), 2)
            if marker['appearance'] == 'torch':
                pygame.draw.circle(screen, GOLD, (cx, cy), 2)
            else:
                rect = pygame.Rect(cx - 3, cy - 3, 6, 6)
                pygame.draw.rect(screen, GOLD, rect, 0 if marker['blocks_movement'] else 1)
                if marker['blocks_vision']:
                    pygame.draw.line(screen, MUTED, rect.topleft, rect.bottomright, 2)
        for number, creature in enumerate(self.session.creatures, 1):
            if creature.position in visibility.visible:
                cx, cy = center(creature.position)
                radius = max(5, cell_size // 2 - 3)
                at_zero_hp = self.session.encounter.states[creature.id].hp == 0
                pygame.draw.circle(screen, (76, 65, 69) if at_zero_hp else RED, (cx, cy), radius)
                if at_zero_hp:
                    pygame.draw.circle(screen, MUTED, (cx, cy), radius, 1)
                    # Selo no canto mantém o número legível, mesmo na grade pequena.
                    badge = pygame.Rect(cx + radius - 5, cy - radius - 2, 8, 8)
                    pygame.draw.rect(screen, BACKGROUND, badge, border_radius=2)
                    pygame.draw.line(screen, TEXT, (badge.left + 2, badge.top + 2),
                                     (badge.right - 2, badge.bottom - 2), 2)
                    pygame.draw.line(screen, TEXT, (badge.right - 2, badge.top + 2),
                                     (badge.left + 2, badge.bottom - 2), 2)
                label(str(number), cx - 4, cy - 7, MUTED if at_zero_hp else BACKGROUND, small)
        for marker in map_view['markers']:
            position = Position(marker['position'][0] - 1, marker['position'][1] - 1)
            cx, cy = center(position)
            if marker['kind'] == 'ally':
                pygame.draw.circle(screen, MUTED, (cx, cy), max(5, cell_size // 2 - 2))
                label(marker.get('label', ''), cx - 4, cy - 6, BACKGROUND, coordinate_font)
            elif marker['kind'] == 'item':
                pygame.draw.rect(screen, GOLD, (cx - 3, cy - 3, 6, 6))
        radius = max(4, min(15, cell_size // 2 - 4))
        pygame.draw.circle(screen, ACCENT, center(self.session.state.position), radius)
        pygame.draw.circle(screen, TEXT, center(self.session.state.position), radius, 2)
        if scene:
            details_y = GRID_ORIGIN[1] + self.session.grid.height * cell_size + 20
            passages = scene.passages
            if map_view['compact']:
                passages = sorted((p for p in passages if p.position in visibility.visible),
                                  key=lambda p: max(abs(p.position.x - self.session.state.position.x),
                                                    abs(p.position.y - self.session.state.position.y)))[:1]
            for passage in passages:
                if passage.position not in visibility.visible:
                    paragraph(f"{passage.name}: fora de visão.", 52, details_y, 460, 2, MUTED)
                    details_y += 48
                    continue
                state_label = "aberta" if passage.is_open else "fechada"
                lock_label = "trancada" if passage.locked else "destrancada"
                lock_label = map_view['passage_lock_labels'].get(passage.id, lock_label)
                paragraph(f"{passage.name}: {state_label}, {lock_label}.",
                          52, details_y, 460, 2, ACCENT if passage.is_open else GOLD)
                details_y += 48
            visible_guards = [c for c in self.session.creatures if c.position in visibility.visible]
            label(f"Guardas visíveis: {len(visible_guards)}", 52, details_y, RED, small)
            label(map_view['legend'], 52, details_y + 24, MUTED, small)
        if map_view['compact']:
            paragraph(map_view['equipment'], 52, 590, 460, 1)
        else:
            label("Colunas: direita / Linhas: baixo", 52, 603, MUTED, small)
        if self.active_tab == "Ficha":
            self.sheet_scroll = self.character_panel.draw(screen, self.session.character_context(),
                                                          self.session.character_options(), self.sheet_scroll)
        elif self.active_tab == "Inimigos":
            self.sheet_scroll = draw_panel(screen, enemy_paragraphs(self.session.visible_enemy_summaries()),
                                           self.active_tab, self.sheet_scroll)
        pygame.draw.rect(screen, PANEL, (550, 104, 458, 138), border_radius=10)
        state = self.session.state
        combat = self.session.combat_context()
        turn_label = f"Por turnos · rodada {combat['round']} · {combat['active']}" if combat else "Modo narrado · exploração"
        label(turn_label, 570, 114, ACCENT, font)
        player = self.session.character_context()
        label(f"PV {player['hp']}/{player['max_hp']} · CA {player['armor_class']} · Coluna {state.position.x + 1}, linha {state.position.y + 1}", 570, 142, TEXT, small)
        label(f"Velocidade: {format_meters(state.effective_speed_meters)}", 570, 167, TEXT, small)
        label(f"Restante: {format_meters(state.remaining_meters)}" if combat else "Movimento sem limite de turno", 738, 167, TEXT, small)
        waiting = combat is not None and not combat["player_turn"]
        action_label = "aguarde" if waiting else ("livre" if self.session.budget.action_available else "usada")
        bonus = "aguarde" if waiting else ("usada" if self.session.budget.bonus_action_used else "livre")
        reaction = "usada" if self.session.budget.reaction_used else "livre"
        interaction = "aguarde" if waiting else ("usada" if self.session.budget.free_interaction_used else "livre")
        label(f"Ação: {action_label} · bônus: {bonus} · extras: {self.session.budget.extra_actions}" if combat else "Ações e respostas pela conversa", 570, 191, MUTED, small)
        if self.session.pending_opportunity:
            for accept, rect in self.reaction_buttons.items():
                pygame.draw.rect(screen, (53, 67, 80) if self.pending else (46, 90, 87), rect, border_radius=4)
                label("Atacar (reação)" if accept else "Deixar passar", rect.x + 9, rect.y + 6, TEXT, small)
        else:
            label(f"Reação: {reaction} · interação: {interaction}" if combat else "O Mundo pode agir e interromper seu percurso", 570, 215, MUTED, small)
        for rect, text in ((self.reset_button, "Reiniciar"),
                           (self.send_button, "Aguarde…" if self.pending else "Enviar")):
            pygame.draw.rect(screen, (53, 67, 80) if self.pending else (46, 90, 87), rect, border_radius=6)
            label(text, rect.x + 10, rect.y + 12, MUTED if self.pending else TEXT, small)
        label("On: ações e narrativa · [Off: regras e dúvidas]", 52, 620, MUTED, small)
        paragraph("Ex.: Caminho até a porta. · Abra a porta. Em conflito: ataque o Guarda 1. · Encerro meu turno.", 52, 646, 460, 2)
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
               narrator: Narrator | None = None, world_director: WorldDirector | None = None) -> None:
    pygame.display.init()
    pygame.font.init()
    try:
        screen = pygame.display.set_mode(WINDOW_SIZE)
        pygame.display.set_caption("Trama — simulador")
        pygame.key.start_text_input()
        pygame.key.set_text_input_rect(pygame.Rect(32, 798, 830, 56))
        pygame.key.set_repeat(400, 35)
        window = MovementWindow(session, interpreter, model, narrator, world_director)
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

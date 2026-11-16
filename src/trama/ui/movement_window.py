"""Entrada, desenho e agenda de workers; a coordenação do jogo pertence a GameFlow."""

from queue import Empty, Queue
from threading import Thread
import logging

import pygame

from trama.application.intents import IntentInterpreter
from trama.application.dialogue import Narrator
from trama.application.game_flow import GameFlow, FlowStatus, ProviderResult
from trama.application.session import GameSession
from trama.application.world import WorldDirector
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
        *, flow: GameFlow | None = None,
    ) -> None:
        self.cell_size = min(CELL_SIZE, 460 // session.grid.width, (380 if session.map_view()["compact"] else 460) // session.grid.height)
        if self.cell_size < 12:
            raise ValueError("O mapa é grande demais para esta janela.")
        if flow is not None and (flow.session is not session or flow.interpreter is not interpreter
                or flow.narrator is not narrator or flow.world_director is not world_director):
            raise ValueError('A janela deve receber a sessão e os serviços do fluxo composto.')
        self.flow = flow if flow is not None else GameFlow(session, interpreter, narrator, world_director)
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
        self.results: Queue[tuple[str, ProviderResult | Exception]] = Queue()
        self._dispatched_request_id: str | None = None
        self._configuration_hint = ("Configure OPENAI_API_KEY no ambiente e reinicie para enviar pedidos."
                                    if interpreter is None else "")
        self.send_button = pygame.Rect(878, 798, 130, 56)
        self.reset_button = pygame.Rect(362, 550, 150, 42)
        self.input_rect = pygame.Rect(32, 798, 830, 56)
        self.reaction_buttons = {True: pygame.Rect(568, 210, 204, 26),
                                 False: pygame.Rect(780, 210, 208, 26)}

    @property
    def session(self):
        return self.flow.session

    @property
    def conversation(self):
        return self.flow.conversation

    @property
    def report(self):
        return self.flow.report

    @property
    def pending(self) -> bool:
        return self.flow.pending

    @property
    def stage(self):
        return self.flow.stage

    @property
    def failed(self) -> bool:
        return self.flow.status == FlowStatus.FAILED

    @property
    def interaction_id(self):
        return self.flow.interaction_id

    @property
    def message(self) -> str:
        if self.flow.message:
            return " ".join(p for p in (self.flow.message, self._configuration_hint if self.failed else "") if p)
        return self._configuration_hint or "Digite um pedido abaixo e pressione Enter. Cada casa mede 1,5 m."

    def _dispatch_pending(self) -> None:
        request = self.flow.pending_request
        if request is None or request.id == self._dispatched_request_id:
            return
        self._dispatched_request_id = request.id

        def run() -> None:
            self.results.put((request.id, request.run()))

        try:
            Thread(target=run, daemon=True).start()
        except Exception as error:
            # A falha de agendamento também é entregue ao fluxo na thread dona.
            self.results.put((request.id, error))

    def start(self) -> None:
        if self.flow.start():
            with log_context(interaction_id=self.interaction_id):
                logger.info("ui.initial_description_requested")
            self._dispatch_pending()

    def submit(self) -> None:
        text = self.input.text
        if not self.flow.submit(text):
            return
        with log_context(interaction_id=self.interaction_id):
            logger.info("ui.message_submitted", extra={"data": {"length": len(text)}})
        if not self.failed:
            self.input = PromptInput()
        self.scroll = 0
        self._dispatch_pending()

    def poll(self) -> None:
        try:
            request_id, result = self.results.get_nowait()
        except Empty:
            self._dispatch_pending()
            return
        if request_id == self._dispatched_request_id:
            self._dispatched_request_id = None
        if self.flow.receive(request_id, result) and not self.pending:
            self.scroll = 0
        self._dispatch_pending()

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
        if self.flow.choose_opportunity(accept):
            self.scroll = 0
            self._dispatch_pending()

    def _reset(self) -> None:
        with log_context(interaction_id=new_id(), operation_id=new_id()):
            logger.info("ui.reset_requested")
            self.flow.reset()
        self.character_panel = CharacterPanel()
        self.sheet_scroll = 0
        self.scroll = 0
        self._dispatch_pending()

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
               narrator: Narrator | None = None, world_director: WorldDirector | None = None,
               *, flow: GameFlow | None = None) -> None:
    pygame.display.init()
    pygame.font.init()
    try:
        screen = pygame.display.set_mode(WINDOW_SIZE)
        pygame.display.set_caption("Trama — simulador")
        pygame.key.start_text_input()
        pygame.key.set_text_input_rect(pygame.Rect(32, 798, 830, 56))
        pygame.key.set_repeat(400, 35)
        window = MovementWindow(session, interpreter, model, narrator, world_director, flow=flow)
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

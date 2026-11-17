"""Mostrador de iniciativa com rolagem própria; recebe apenas a projeção pública."""

import pygame

from trama.distances import format_meters
from trama.ui.text import word_lines

BACKGROUND = (20, 26, 35)
PANEL = (31, 40, 52)
TEXT = (233, 239, 244)
MUTED = (163, 180, 196)
ACCENT = (91, 217, 190)
GOLD = (230, 183, 96)
ROW_HEIGHT = 56
PAGE_SIZE = 2


class TurnPanel:
    def __init__(self):
        self.offset = 0
        self._active = None

    def rect(self, view):
        count = min(PAGE_SIZE, len(view['entries']))
        return pygame.Rect(550, 252, 458, 68 + count * ROW_HEIGHT)

    def scroll(self, amount, view):
        self.offset = max(0, min(max(0, len(view['entries']) - PAGE_SIZE), self.offset + amount))

    def _follow_turn(self, view):
        key = (view['round'], view['active_id'])
        if key != self._active:
            current = next((i for i, e in enumerate(view['entries']) if e['phase'] == 'current'), None)
            if current is not None and not self.offset <= current < self.offset + PAGE_SIZE:
                self.offset = current
            self._active = key
        self.scroll(0, view)

    def draw(self, screen, view):
        self._follow_turn(view)
        rect = self.rect(view)
        title = pygame.font.Font(None, 22)
        name_font = pygame.font.Font(None, 21)
        detail = pygame.font.Font(None, 18)
        pygame.draw.rect(screen, PANEL, rect, border_radius=10)
        screen.blit(title.render(f"Iniciativa · rodada {view['round']}", True, ACCENT), (rect.x + 16, rect.y + 9))
        if len(view['entries']) > PAGE_SIZE:
            counter = f"{self.offset + 1}–{min(self.offset + PAGE_SIZE, len(view['entries']))}/{len(view['entries'])} · roda"
            rendered = detail.render(counter, True, MUTED)
            screen.blit(rendered, (rect.right - rendered.get_width() - 16, rect.y + 11))
        phase_names = dict(current='AGORA', upcoming='A seguir', finished='Encerrado', unavailable='0 PV')
        for index, entry in enumerate(view['entries'][self.offset:self.offset + PAGE_SIZE], self.offset):
            row = pygame.Rect(rect.x + 10, rect.y + 32 + (index-self.offset)*ROW_HEIGHT, rect.width - 20, ROW_HEIGHT - 4)
            active = entry['phase'] == 'current'
            pygame.draw.rect(screen, (38, 66, 65) if active else BACKGROUND, row, border_radius=5)
            if active:
                pygame.draw.rect(screen, ACCENT, row, 1, border_radius=5)
            state = name_font.render(phase_names[entry['phase']], True, ACCENT if active else MUTED)
            screen.blit(state, (row.right - state.get_width() - 8, row.y + 4))
            name = entry['name']
            prefix, suffix = f"{index+1}. ", f" · inic. {entry['initiative']}"
            limit = row.width - state.get_width() - 28 - name_font.size(prefix + suffix)[0]
            if name_font.size(name)[0] > limit:
                while name and name_font.size(name + '…')[0] > limit:
                    name = name[:-1]
                name += '…'
            screen.blit(name_font.render(prefix + name + suffix, True, TEXT), (row.x + 8, row.y + 4))
            reaction = 'livre' if entry['reaction_available'] else 'usada'
            if active:
                action = ('extra' if entry['normal_action_used'] else 'livre') if entry['action_available'] else 'usada'
                bonus = 'livre' if entry['bonus_available'] else 'usada'
                interaction = 'livre' if entry['interaction_available'] else 'usada'
                first = f"Mov. {format_meters(entry['movement_meters'])} · Ação {action} · Bônus {bonus}"
                second = f"Reação {reaction} · Interação {interaction} · Extras {entry['extra_actions']}"
            elif entry['phase'] == 'upcoming':
                first, second = 'Movimento, ação e bônus na próxima vez.', f'Reação {reaction} agora.'
            elif entry['phase'] == 'finished':
                first, second = 'Movimento, ação e bônus encerrados.', f'Reação {reaction} até o início da próxima vez.'
            else:
                first, second = 'Sem condições de agir.', 'Sem ações ou reação disponíveis.'
            screen.blit(detail.render(first, True, MUTED), (row.x + 8, row.y + 22))
            screen.blit(detail.render(second, True, MUTED), (row.x + 8, row.y + 37))
        for i, line in enumerate(word_lines(view['pending'], detail, rect.width - 32)[:2]):
            screen.blit(detail.render(line, True, GOLD), (rect.x + 16, rect.bottom - 30 + i*14))
        return rect

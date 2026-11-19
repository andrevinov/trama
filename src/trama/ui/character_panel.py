"""Ficha e resumos a partir de projeções da aplicação, sem alterar regras."""

import pygame

from trama.distances import format_meters
from trama.ui.text import word_lines

ABILITIES = {"strength": "Força", "dexterity": "Destreza", "constitution": "Constituição",
             "intelligence": "Inteligência", "wisdom": "Sabedoria", "charisma": "Carisma"}
SKILLS = {"acrobatics": "Acrobacia", "animal_handling": "Lidar com Animais", "arcana": "Arcanismo",
          "athletics": "Atletismo", "deception": "Enganação", "history": "História", "insight": "Intuição",
          "intimidation": "Intimidação", "investigation": "Investigação", "medicine": "Medicina",
          "nature": "Natureza", "perception": "Percepção", "performance": "Atuação",
          "persuasion": "Persuasão", "religion": "Religião", "sleight_of_hand": "Prestidigitação",
          "stealth": "Furtividade", "survival": "Sobrevivência"}
FEATURES = {
    "Resourceful": "Engenhoso: recebe Inspiração Heroica ao concluir um descanso longo. Rerrola um dado e mantém o novo resultado.",
    "Skillful": "Habilidoso: proficiência em Sobrevivência, escolhida para este Humano.",
    "Versatile: Skilled": "Versátil: talento de origem Skilled; Acrobacia, História e Investigação.",
    "Soldier: Savage Attacker": "Soldado / Savage Attacker: uma vez por turno, rola os dados de dano da arma duas vezes e usa um resultado. Aqui o código escolhe o maior.",
    "Fighting Style: Defense": "Defesa: +1 CA enquanto usa armadura (já incluído).",
    "Second Wind": "Retomar o Fôlego: ação bônus, cura 1d10 + nível de Guerreiro. Recupera 1 uso no descanso curto; todos no longo.",
    "Weapon Mastery": "Maestria em Armas: três armas escolhidas. Pode trocar uma escolha após descanso longo.",
    "Action Surge": "Surto de Ação: uma ação adicional neste turno, exceto Magia. Recupera no descanso curto ou longo.",
    "Tactical Mind": "Mente Tática: soma 1d10 a um teste de atributo falho. Gasta Retomar o Fôlego somente se o teste passar.",
    "Improved Critical": "Crítico Aprimorado: armas e ataques desarmados causam crítico com 19 ou 20 natural.",
    "Remarkable Athlete": "Atleta Notável: vantagem em iniciativa e Atletismo. Após crítico, movimento imediato até metade da velocidade sem ataques de oportunidade.",
}
MASTERY = {"graze": "Graze: erro causa dano igual ao modificador do ataque.",
           "sap": "Sap: acerto impõe desvantagem no próximo ataque do alvo até seu próximo turno.",
           "slow": "Slow: acerto com dano reduz a velocidade do alvo em 3 m até seu próximo turno; não acumula."}


def sheet_paragraphs(sheet: dict) -> list[str]:
    lines = [f"{sheet['name']} · Humano Médio · Guerreiro {sheet['level']}",
             f"Campeão · Soldado · Estilo Defesa" if sheet["subclass"] else "Soldado · Estilo Defesa",
             f"PV {sheet['hp']}/{sheet['max_hp']} · CA {sheet['armor_class']} · Proficiência +{sheet['proficiency_bonus']}",
             f"Velocidade {format_meters(sheet['speed_meters'])} · Dados de Vida {sheet['hit_dice']}",
             "", "ATRIBUTOS / SALVAGUARDAS"]
    for name, label in ABILITIES.items():
        a = sheet["abilities"][name]
        lines.append(f"{label}: {a['score']} ({a['modifier']:+d}) · salvaguarda {sheet['saving_throws'][name]:+d}")
    lines += ["", "RECURSOS",
              f"Retomar o Fôlego: {sheet['second_wind_uses']}/2 · Surto de Ação: {sheet['action_surge_uses']}/1",
              f"Inspiração Heroica: {'disponível' if sheet['heroic_inspiration'] else 'usada'}",
              "", "PERÍCIAS (* proficiente)" + (" · Atletismo com vantagem" if sheet['subclass'] else "")]
    for name, skill in sheet["skills"].items():
        lines.append(f"{'* ' if skill['proficient'] else ''}{SKILLS[name]} {skill['bonus']:+d}")
    lines += ["", "EQUIPAMENTO E TREINAMENTO",
              "Cota de malha" if sheet["armor"] == "chain_mail" else "Sem armadura"]
    if "clothing" in sheet:
        lines += [sheet["clothing"], "Inventário: " + (", ".join(sheet["inventory"]) or "nenhum"),
                  "Espada oculta sob a roupa" if sheet.get("sword_concealed") else ""]
    lines.extend(f"{w['name']}: ataque {w['attack_bonus']:+d}, dano {w['damage']} {w['damage_type']}"
                 for w in sheet["weapons"])
    lines += [f"Azagaias: {sheet['javelins']} · armas simples e marciais",
              "Armaduras leves, médias, pesadas e escudos",
              "Ferramentas: " + ", ".join(sheet["tool_proficiencies"]), "", "MAESTRIAS"]
    for mastery in sheet["masteries"]:
        lines.append(f"{mastery['weapon']} — {MASTERY[mastery['property']]}")
    lines += ["", "TRAÇOS E CARACTERÍSTICAS"]
    for feature in sheet["features"]:
        if feature == "Skillful":
            lines.append("Habilidoso: proficiência em " + SKILLS[sheet["human_skill"]] + ".")
        elif feature == "Versatile: Skilled":
            lines.append("Versátil / Skilled: " + ", ".join(SKILLS[s] for s in sheet["skilled_choices"]) + ".")
        elif feature == "Fighting Style: Defense" and sheet["armor"] == "none":
            lines.append("Defesa: +1 CA com armadura; inativo enquanto estiver sem armadura.")
        else:
            lines.append(FEATURES[feature])
    lines += ["", "Descansos, testes de atributo e troca de maestria ainda não podem ser solicitados pela conversa."]
    return lines


def data_section(sheet: dict) -> dict:
    """Os dados extensos ficam agrupados e recolhidos até um clique."""
    groups = {
        "ATRIBUTOS / SALVAGUARDAS": ("attributes", "Atributos e salvaguardas", "Valores, modificadores e resistências"),
        "EQUIPAMENTO E TREINAMENTO": ("equipment", "Equipamento e treinamento", "Armadura, armas e proficiências"),
        "MAESTRIAS": ("masteries", "Maestrias em Armas", "Propriedades das três armas escolhidas"),
        "TRAÇOS E CARACTERÍSTICAS": ("traits", "Traços e características", "Humano, Guerreiro e subclasse"),
    }
    items = []
    current = None
    for paragraph in sheet_paragraphs(sheet)[5:]:
        if paragraph.startswith("PERÍCIAS"):
            key, title, summary = "skills", "Perícias", "Bônus, proficiências e vantagem em Atletismo" if sheet["subclass"] else "Bônus e proficiências"
        elif paragraph in groups:
            key, title, summary = groups[paragraph]
        elif paragraph == "RECURSOS":
            current = None  # Possuem uma seção própria, com estado e recuperação.
            continue
        else:
            if current is not None and paragraph:
                current["details"].append(paragraph)
            continue
        current = {"id": key, "title": title, "summary": summary, "status": "information", "details": []}
        items.append(current)
    return {"id": "data", "title": "Dados do personagem", "items": items}


class CharacterPanel:
    """Consulta com seções e detalhes expansíveis; cliques nunca executam ações."""

    viewport = pygame.Rect(48, 252, 448, 256)
    colors = {"available": (91, 217, 190), "conditional": (245, 189, 81),
              "unavailable": (255, 144, 137), "not_implemented": (163, 180, 196),
              "information": (163, 180, 196)}
    labels = {"available": "Disponível", "conditional": "Condicional", "unavailable": "Indisponível",
              "not_implemented": "Não implementado", "information": "Detalhes"}

    def __init__(self):
        self.section = "actions"
        self.expanded: set[str] = set()
        self.item_rects: dict[str, pygame.Rect] = {}
        self.section_rects = {key: pygame.Rect(48 + i * 152, 192, 144, 28)
                              for i, key in enumerate(("actions", "resources", "data"))}

    def click(self, position) -> str | None:
        for key, rect in self.section_rects.items():
            if rect.collidepoint(position):
                self.section = key
                self.item_rects.clear()
                return "section"
        for key, rect in self.item_rects.items():
            if rect.collidepoint(position):
                if key in self.expanded:
                    self.expanded.remove(key)
                else:
                    self.expanded.add(key)
                self.item_rects.clear()
                return "detail"
        return None

    @staticmethod
    def _shorten(text, font, width):
        if font.size(text)[0] <= width:
            return text
        while text and font.size(text + "…")[0] > width:
            text = text[:-1]
        return text.rstrip() + "…"

    def draw(self, screen, sheet: dict, sections: list[dict], scroll: int) -> int:
        pygame.draw.rect(screen, (20, 26, 35), (16, 80, 512, 464))
        pygame.draw.rect(screen, (31, 40, 52), (32, 104, 480, 438), border_radius=10)
        font = pygame.font.Font(None, 23)
        small = pygame.font.Font(None, 20)
        badge_font = pygame.font.Font(None, 18)
        text, muted = (233, 239, 244), (163, 180, 196)
        screen.blit(font.render("Ficha", True, self.colors["available"]), (48, 116))
        screen.blit(small.render("Clique em um cartão para ver detalhes", True, muted), (200, 118))
        identity = f"{sheet['name']} · Humano · Guerreiro {sheet['level']}"
        if sheet["subclass"]:
            identity += " · " + sheet["subclass"]
        screen.blit(font.render(self._shorten(identity, font, 448), True, text), (48, 145))
        summary = (f"PV {sheet['hp']}/{sheet['max_hp']} · CA {sheet['armor_class']} · "
                   f"Vel. {format_meters(sheet['speed_meters'])} · Prof. +{sheet['proficiency_bonus']}")
        screen.blit(small.render(summary, True, muted), (48, 169))
        for key, label in (("actions", "Agora"), ("resources", "Recursos"), ("data", "Dados")):
            rect = self.section_rects[key]
            pygame.draw.rect(screen, (46, 90, 87) if key == self.section else (42, 53, 67), rect, border_radius=5)
            screen.blit(small.render(label, True, text), (rect.x + 12, rect.y + 6))
        section = next(s for s in [*sections, data_section(sheet)] if s["id"] == self.section)
        screen.blit(font.render(section["title"], True, self.colors["available"]), (48, 228))
        rows = []
        offset = 0
        for item in section["items"]:
            detail_lines = []
            if item["id"] in self.expanded:
                for paragraph in item["details"]:
                    detail_lines.extend(word_lines(paragraph, small, self.viewport.width - 32))
                    detail_lines.append("")
            height = 54 + len(detail_lines) * 20
            rows.append((offset, height, item, detail_lines))
            offset += height + 6
        maximum = max(0, offset - 6 - self.viewport.height)
        scroll = min(maximum, max(0, scroll))
        self.item_rects.clear()
        previous_clip = screen.get_clip()
        screen.set_clip(self.viewport)
        for offset, height, item, detail_lines in rows:
            rect = pygame.Rect(self.viewport.x, self.viewport.y + offset - scroll, self.viewport.width - 8, height)
            if not rect.colliderect(self.viewport):
                continue
            header = pygame.Rect(rect.x, rect.y, rect.width, 54)
            self.item_rects[item["id"]] = header.clip(self.viewport)
            hovered = header.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(screen, (47, 62, 76) if hovered else (38, 49, 63), rect, border_radius=6)
            color = self.colors[item["status"]]
            badge = self.labels[item["status"]]
            badge_width = badge_font.size(badge)[0]
            screen.blit(badge_font.render(badge, True, color), (rect.right - badge_width - 10, rect.y + 10))
            mark = "−" if item["id"] in self.expanded else "+"
            screen.blit(font.render(mark, True, muted), (rect.x + 8, rect.y + 7))
            title = self._shorten(item["title"], font, rect.width - badge_width - 48)
            screen.blit(font.render(title, True, text), (rect.x + 25, rect.y + 7))
            summary = self._shorten(item["summary"], small, rect.width - 20)
            screen.blit(small.render(summary, True, muted), (rect.x + 10, rect.y + 32))
            for index, line in enumerate(detail_lines):
                screen.blit(small.render(line, True, text), (rect.x + 16, rect.y + 56 + index * 20))
        screen.set_clip(previous_clip)
        if maximum:
            thumb_height = max(18, self.viewport.height * self.viewport.height // (offset - 6))
            thumb_y = self.viewport.y + (self.viewport.height - thumb_height) * scroll // maximum
            pygame.draw.rect(screen, muted, (self.viewport.right - 4, thumb_y, 3, thumb_height), border_radius=1)
        screen.blit(small.render("Role aqui · clique abre/fecha detalhes · ações pela conversa", True, muted), (48, 520))
        return scroll


def enemy_paragraphs(enemies: list[dict]) -> list[str]:
    if not enemies:
        return ["Nenhum NPC com ficha visível.", "Somente personagens no campo de visão aparecem aqui."]
    lines = []
    for enemy in enemies:
        lines += [f"{enemy['name']} · Humano · Guerreiro {enemy['level']}",
                  f"PV {enemy['hp']}/{enemy['max_hp']} · CA {enemy['armor_class']}",
                  f"Arma: {enemy['weapon']}",
                  "PV zerados (0 PV)" if enemy["at_zero_hp"] else "Ações decididas pelo Mundo", ""]
    return lines


def draw_panel(screen, paragraphs: list[str], title: str, scroll: int) -> int:
    # Cobre também os números nas margens do mapa ao trocar de guia.
    pygame.draw.rect(screen, (20, 26, 35), (16, 80, 512, 464))
    rect = pygame.Rect(32, 104, 480, 438)
    pygame.draw.rect(screen, (31, 40, 52), rect, border_radius=10)
    font = pygame.font.Font(None, 23)
    screen.blit(font.render(title, True, (91, 217, 190)), (48, 116))
    viewport = pygame.Rect(48, 148, 448, 364)
    lines = [line for p in paragraphs for line in word_lines(p, font, viewport.width - 8)]
    maximum = max(0, len(lines) * 22 - viewport.height)
    scroll = min(maximum, max(0, scroll))
    old_clip = screen.get_clip()
    screen.set_clip(viewport)
    for index, line in enumerate(lines):
        y = viewport.y + index * 22 - scroll
        if viewport.y - 22 < y < viewport.bottom:
            screen.blit(font.render(line, True, (233, 239, 244)), (viewport.x, y))
    screen.set_clip(old_clip)
    hint = "Role sobre a ficha para ler mais" if maximum else "Informações dos NPCs atualmente visíveis"
    screen.blit(font.render(hint, True, (163, 180, 196)), (48, 518))
    return scroll

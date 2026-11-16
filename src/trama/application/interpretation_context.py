"""Projeção pequena para interpretação; o contexto do Mundo permanece completo."""

from copy import deepcopy


def compact_context(context: dict) -> dict:
    original_map = context.get("map", {})
    map_context = {key: original_map[key] for key in ("columns", "rows", "distance_unit", "cell_size_meters") if key in original_map}
    scene = original_map.get("scene")
    if scene:
        map_context["scene"] = {
            "areas": [{k: a[k] for k in ("id", "name", "column", "row") if k in a} for a in scene.get("areas", [])],
            "passages": deepcopy(scene.get("passages", [])),
            "objects": deepcopy([o for o in scene.get("objects", []) if o.get("visible")]),
        }
    character = context.get("character", {})
    sheet = context.get("player_sheet", {})
    actions = context.get("available_actions") or [
        {"operation": "move", "description": "Caminhar, voltar, retornar ou recuar até lugar/criatura, coordenadas ou direção/distância; postura é detalhe narrativo."},
        {"operation": "open", "description": "Aproximar-se se necessário e abrir passagem; se já aberta, continuar sem custo. allow_approach=false proíbe deslocamento."},
        {"operation": "close", "description": "Aproximar-se se necessário e fechar passagem; se já fechada, continuar sem custo. allow_approach=false proíbe deslocamento."},
        {"operation": "look", "description": "Olhar a partir da posição atual, sem teste."},
        {"operation": "speak", "description": "Falar ou perguntar a alguém no mundo."},
        {"operation": "wait", "description": "Permanecer ou aguardar no modo narrado, sem turnos. Em combate, passar a vez usa end_turn."},
        {"operation": "challenge", "description": "Anunciar um desafio."},
        {"operation": "attack", "description": "Atacar alvo visível. Movimento contextual aproxima ao alcance; a iniciativa precede essa caminhada em combate. allow_approach=false proíbe aproximar."},
        {"operation": "end_turn", "description": "Passar a vez em conflito, inclusive ao dizer que fica parado, não faz nada ou aguarda sem outra ação; pode abrir mão de recursos ainda livres."},
        {"operation": "second_wind", "name": "Retomar o Fôlego", "uses_remaining": sheet.get("second_wind_uses")},
        {"operation": "action_surge", "name": "Surto de Ação", "uses_remaining": sheet.get("action_surge_uses"),
         "description": "Concede ação adicional no turno. Pedido para usá-lo e atacar exige action_surge seguido de attack, na mesma mensagem."},
    ]
    combat = context.get("combat")
    result = {
        "mode": context.get("mode", "narrated"), "map": map_context,
        "character": {key: character[key] for key in ("column", "row", "current_area", "speed_meters", "remaining_meters") if key in character},
        "visible_creatures": deepcopy(context.get("visible_creatures", [])),
        "combat": ({key: combat[key] for key in ("round", "active_id", "player_turn") if key in combat} if combat else None),
        "available_actions": deepcopy(actions),
        "equipped_weapons": deepcopy(context.get("equipped_weapons", [])),
        "last_attack": deepcopy(context.get("last_attack")),
        "turn_resources": deepcopy(context.get("turn_resources", {
            key: sheet.get(key) for key in ("action_available", "bonus_action_available", "reaction_available", "extra_actions")
        })),
        "recent_messages": [{"role": message["role"], "on": message["on"]}
                            for message in context.get("recent_messages", [])[-6:] if message.get("on")],
    }
    if "scenario" in context:
        result["scenario"] = deepcopy(context["scenario"])
        result["visible_objects"] = deepcopy(context.get("visible_objects", []))
    return result

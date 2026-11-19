"""Projeção pequena para interpretação; o contexto do Mundo permanece completo.

Conversation envolve o resultado em AIContext validado. O adaptador preserva
essa projeção já preparada; este helper também atende os experimentos com dict.
"""

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
        {"operation": "inspect_passage", "description": "Conferir se porta/grade está trancada usa method=mechanism, ao alcance, sem abrir/destrancar. Sem barulho: volume=quiet. Só olhar: method=visual, volume=normal, allow_approach=false; não revela fechadura desconhecida."},
        {"operation": "hide", "description": "Esconder-se com cobertura/ocultação e fora da visão inimiga; CD 15, total define a detecção posterior."},
        {"operation": "sneak", "description": "Mover-se furtivamente até target_id, com Hide se necessário. Disponível em qualquer cenário; não duplica move."},
        {"operation": "look", "description": "Olhar a partir da posição atual, sem teste."},
        {"operation": "speak", "description": "Falar, responder à abordagem ou tentar convencer alguém no mundo. Proponha speak; o Mundo julga Influence, sem inventar sucesso."},
        {"operation": "gesture", "description": "Comunicar por sinal, gesto, aceno ou piscadela a um NPC conhecido. text descreve o movimento visível; message é intenção, não compreensão garantida. subtle=true para gestos finos/discretos. Não aproxima, não fala e não é mero detalhe narrativo."},
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
        "parley": deepcopy(context.get("parley")),
        "sensing": deepcopy(context.get("sensing", {"hidden": False, "can_hide": False})),
        'knowledge': deepcopy(context.get('knowledge', [])),
        'conversations': deepcopy(context.get('conversations', [])),
        "character": {key: character[key] for key in ("column", "row", "current_area", "speed_meters", "remaining_meters") if key in character},
        "visible_creatures": deepcopy(context.get("visible_creatures", [])),
        "communication_targets": deepcopy(context.get('communication_targets', context.get('visible_creatures', []))),
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

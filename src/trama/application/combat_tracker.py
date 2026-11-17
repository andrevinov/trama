"""Projeção de leitura do combate para a interface; não entra nos contextos de IA."""


def combat_tracker_view(flow):
    session = flow.session
    encounter = session.encounter
    combat = encounter.combat
    if combat is None:
        return None
    public = session.combat_context()
    positions = {entry.id: index for index, entry in enumerate(combat.order)}
    entries = []
    for entry in public['order']:
        actor = entry['id']
        budget = encounter.budgets[actor]
        alive = encounter.states[actor].hp > 0
        phase = ('unavailable' if not alive else 'current' if actor == combat.active_id else
                 'finished' if positions[actor] < combat.index else 'upcoming')
        movement = session.state if actor == encounter.player_id else session.npc_movement.get(actor)
        remaining = movement.remaining_meters if movement is not None else encounter.speed(actor)
        entries.append({**entry, 'phase': phase,
            'movement_meters': float(remaining),
            'action_available': alive and budget.action_available,
            'normal_action_used': budget.action_used,
            'bonus_available': alive and not budget.bonus_action_used,
            'reaction_available': alive and not budget.reaction_used,
            'interaction_available': alive and not budget.free_interaction_used,
            'extra_actions': budget.extra_actions})
    if session.pending_opportunity:
        pending = 'Você: decidir o ataque de oportunidade.'
    elif flow.pending:
        pending = {'interpret': 'Interpretando sua ação…',
                   'world': 'Aguardando resposta do Mundo…',
                   'npc_turn': f"Resolvendo o turno de {public['active']}…",
                   'narrate': 'Preparando a narração do resultado…'}[flow.stage]
    elif flow.status == 'failed':
        pending = 'Falha na resposta. Aguardando nova entrada.'
    elif public['player_turn']:
        pending = ('Você está com 0 PV.' if encounter.states[encounter.player_id].hp == 0 else
                   'Sua vez: declare sua ação ou encerre o turno.')
    else:
        pending = f"Vez de {public['active']}: aguardando resolução."
    return dict(round=combat.round, active_id=(combat.active_id if any(
        e['id'] == combat.active_id for e in entries) else None), active_name=public['active'],
        entries=entries, pending=pending)

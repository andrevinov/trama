"""Projeção das possibilidades atuais da ficha; não executa nem autoriza ações.

Descreve somente as regras e comandos já existentes nesta demonstração.
Disponibilidade é uma fotografia; a execução sempre volta a validar o pedido.
"""

from trama.actions import ActionBudget
from trama.characters import WEAPONS, FighterSheet, FighterState
from trama.distances import CELL_METERS, format_meters
from trama.movement import MovementState


def sheet_options(
    sheet: FighterSheet, state: FighterState, budget: ActionBudget, movement: MovementState,
    *, turn_based: bool, player_turn: bool, can_step: bool, can_move: bool,
    attack_targets: tuple[str, ...], door_targets: tuple[str, ...],
) -> list[dict]:
    """Dados para consulta: estado, motivo, momento, custo e exemplo de uso."""
    gate = "Personagem com 0 PV." if state.hp == 0 else (
        "Aguarde seu turno." if turn_based and not player_turn else "")
    action_gate = gate or ("Ação já utilizada." if turn_based and not budget.action_available else "")
    bonus_gate = gate or ("Ação bônus já utilizada." if turn_based and budget.bonus_action_used else "")

    def entry(id, title, summary, details, *, blocked="", conditional="", implemented=True):
        status = "not_implemented" if not implemented else (
            "unavailable" if blocked else "conditional" if conditional else "available")
        reason = "Sem comando nesta versão." if not implemented else blocked or conditional or "Disponível agora."
        return {"id": id, "title": title, "summary": summary, "status": status,
                "reason": reason, "details": [reason, *details]}

    movement_block = gate or ("Sem passo livre ao redor." if not can_step else (
        "Saldo insuficiente para o próximo passo." if turn_based and not can_move else ""))
    actions = [
        entry("move", "Caminhar", format_meters(movement.remaining_meters) + " restantes" if turn_based else "Sem limite de turno", [
            "Quando: no seu turno; na exploração, sem orçamento por mensagem.",
            "Custo: movimento, sem gastar ação. Terreno difícil custa o dobro; paredes e ocupantes impedem a passagem.",
            "Como pedir: Caminho até a porta da Sala dos Guardas.",
            "Movimento imediato após crítico: " + format_meters(movement.free_meters) + " disponíveis; termina ao realizar outra operação.",
        ], blocked=movement_block),
        entry("attack", "Atacar", "Ação · corpo a corpo · alcance 1,5 m", [
            "Quando: no seu turno. Escolha um inimigo visível; se estiver longe, o movimento contextual aproxima ao alcance de 1,5 m, respeitando caminho e saldo.",
            "Custo: uma ação. Armas equipadas: " + (", ".join(WEAPONS[w].name for w in sheet.weapons) or "nenhuma; ataque desarmado disponível") + ".",
            "Alvos ao alcance: " + (", ".join(attack_targets) or "nenhum") + ".",
            "Como pedir: Ataque o Guarda 1 com a espada grande.",
            "Fora de conflito, o pedido inicia iniciativa antes do golpe; não concede ataque gratuito.",
        ], blocked=action_gate, conditional=("Sem alvo ao alcance." if not attack_targets else (
            "Iniciativa antes do ataque." if not turn_based else ""))),
        entry("second_wind", "Retomar o Fôlego", f"Bônus · {state.second_wind_uses}/2 usos", [
            f"Quando: no seu turno, ou na exploração. Cura 1d10 + {sheet.level} PV, até o máximo.",
            "Custo: ação bônus e um uso. Pode ser usado com PV completos, consumindo o uso sem curar.",
            "Recuperação: um uso no descanso curto; todos no descanso longo.",
            "Como pedir: Use Retomar o Fôlego.",
        ], blocked=bonus_gate or ("Sem usos restantes." if not state.second_wind_uses else ""),
              conditional="PV completos; uso seria gasto." if state.hp == sheet.max_hp else ""),
    ]
    if sheet.level >= 2:
        actions.append(entry("action_surge", "Surto de Ação", f"Sem ação · {state.action_surge_uses}/1 uso", [
            "Quando: no seu turno, mesmo depois de gastar sua ação normal.",
            "Custo: um uso; concede uma ação adicional neste turno, exceto para Magia. Não gasta ação bônus.",
            "Recuperação: descanso curto ou longo.",
            "Como pedir: Use Surto de Ação e ataque o Guarda 1.",
        ], blocked=gate or ("Só no modo por turnos." if not turn_based else (
            "Sem usos restantes." if not state.action_surge_uses else ""))))
    interaction_block = gate or ("Interação e ação já utilizadas." if turn_based
                                 and budget.free_interaction_used and not budget.action_available else "")
    actions.extend([
        entry("doors", "Abrir / fechar", "Interação livre" if not turn_based or not budget.free_interaction_used else "Consome ação", [
            "Quando: no seu turno ou na exploração, a até 1,5 m da passagem e com visão dela.",
            "Pedir para abrir/fechar autoriza aproximar-se caminhando, usando o movimento disponível. Diga sem sair do lugar para proibir essa aproximação.",
            "Passagem já no estado pedido: nenhuma aproximação ou gasto; o restante do pedido continua.",
            "Custo: primeira interação livre no turno; as seguintes usam ação. Na exploração não há esse limite por mensagem.",
            "A porta deve estar destrancada para abrir, e a passagem desocupada para fechar.",
            "Passagens utilizáveis próximas: " + (", ".join(door_targets) or "nenhuma") + ".",
            "Como pedir: Abra a porta da Sala dos Guardas.",
        ], blocked=interaction_block, conditional="Aproxime-se de uma passagem utilizável." if not door_targets else ""),
        entry("dash", "Correr (Dash)", "Ação · movimento adicional" if turn_based else "Exploração sem saldo por turno", [
            "Quando: no seu turno. Usa uma ação para somar sua velocidade efetiva ao movimento disponível.",
            "A distância adicional também paga terreno difícil e não permite atravessar obstáculos.",
            "Como pedir: Corra até a porta.",
            "No modo narrado, correr não cria nem gasta um orçamento de turno.",
        ], blocked=action_gate or ("Sem passo livre ao redor." if not can_step else (
            "Velocidade insuficiente para uma casa." if movement.effective_speed_meters < CELL_METERS else ""))),
        entry("interact", "Falar / observar", "Interação narrativa", [
            "Quando: no seu turno ou na exploração. Falar ou observar não consome uma ação neste recorte.",
            "Não executa testes de atributo, deslocamentos nem ataques. O Mundo pode responder ao que você diz.",
            "Como pedir: Pergunto aos guardas por que estou preso.",
        ], blocked=gate),
        entry("end_turn", "Encerrar turno", "Passa a vez na iniciativa", [
            "Quando: no seu turno, mesmo que ainda tenha movimento, ação ou bônus.",
            "Como pedir: Encerro meu turno; fico parado; ou não faço mais nada nesta vez.",
            "Os NPCs agem e o jogo avança até sua próxima vez. Seus recursos de turno retornam no início dela.",
        ], blocked=gate or ("Não há turnos na exploração." if not turn_based else "")),
        entry("ready", "Preparar", "Ação com gatilho e resposta", [
            "A ação Preparar e sua reação ainda não têm execução nesta demonstração.",
            "Descrevê-la na conversa não reserva um ataque nem gasta ação ou reação.",
        ], implemented=False),
    ])
    resources = [
        entry("reaction", "Reação", "Usada" if budget.reaction_used else "Livre", [
            "Momento: depende de um gatilho. O orçamento é recuperado no início do seu próximo turno.",
            "Ataque de oportunidade: quando um inimigo visível vai sair do seu alcance de 1,5 m. Um ataque corpo a corpo antes da saída; não gasta sua ação normal.",
            "O jogo pausa e oferece Atacar (reação) ou Deixar passar. Recusar mantém sua reação disponível.",
            "Entrar no alcance ou caminhar dentro dele não provoca. O movimento protegido de Campeão após crítico também não provoca.",
            "Usa a primeira arma equipada na ficha; ataques de oportunidade dos guardas são automáticos neste cenário.",
            "A ação Preparar e sua resposta continuam sem execução.",
        ], blocked="Personagem com 0 PV." if state.hp == 0 else ("Reação já utilizada." if budget.reaction_used else ""),
              conditional="Aguarda um gatilho de oportunidade."),
        entry("inspiration", "Inspiração Heroica", "1 uso disponível" if state.heroic_inspiration else "Sem uso restante", [
            "Não gasta ação, bônus ou reação. Rerrola um dado e mantém o novo resultado.",
            "Nesta demonstração, o comando está integrado ao ataque do seu turno; não há comando independente para outros dados ou ataques fora do turno.",
            "Como pedir: Ataque o Guarda 1 com o mangual usando Inspiração Heroica.",
            "Recuperação: o traço Humano Engenhoso concede Inspiração ao concluir descanso longo. Inspirações não se acumulam.",
        ], blocked="Sem Inspiração Heroica." if not state.heroic_inspiration else (
            "Personagem com 0 PV." if state.hp == 0 else ""), conditional="Uso integrado ao ataque."),
        entry("recovery", "Recargas e descansos", f"Fôlego {state.second_wind_uses}/2 · Surto {state.action_surge_uses}/1" if sheet.level >= 2 else f"Fôlego {state.second_wind_uses}/2", [
            "Descanso curto concluído (1 hora): recupera um Retomar o Fôlego e o Surto de Ação, se adquirido.",
            "Descanso longo válido: recupera PV, todos os usos, Dados de Vida e Inspiração Heroica deste Humano.",
            f"Dados de Vida restantes: {state.hit_dice_available}/{sheet.level} d10. No descanso curto, curam 1d10 + Constituição por dado gasto (mínimo 1).",
            "Descansos ainda não podem ser solicitados pela conversa; o jogo ainda não acompanha o tempo de descanso.",
        ], implemented=False),
        entry("magic_items", "Itens mágicos", "Nenhum efeito registrado", [
            "Este cenário ainda não registra itens mágicos, efeitos, cargas ou recargas de itens na ficha.",
        ], implemented=False),
    ]
    if sheet.level >= 2:
        resources.insert(2, entry("tactical_mind", "Mente Tática", f"Compartilha Fôlego · {state.second_wind_uses}/2", [
            "Momento: após falhar em um teste de atributo. Soma 1d10 ao total; só gasta um uso de Retomar o Fôlego se o teste passar.",
            "Não gasta ação ou reação. O uso depende do teste; não cura PV e compartilha a reserva de Retomar o Fôlego.",
            "Testes do Jogador e este uso ainda não estão disponíveis pela conversa.",
        ], implemented=False))
    return [{"id": "actions", "title": "O que posso fazer", "items": actions},
            {"id": "resources", "title": "Fora do turno e recuperação", "items": resources}]

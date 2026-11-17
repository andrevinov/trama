# Execução das respostas do Mundo

Tier 3 · [Aplicação](README.md) · [Visão geral](../../../README.md)

## Respostas do Mundo

`WorldPlan` é separado de `ActionPlan`. Cada `WorldReaction` aponta para uma
etapa do Jogador (`step_index`, base zero) e um ponto de execução:

- `after_squares=0`: antes da etapa;
- inteiro positivo: após essa quantidade de casas realmente percorridas na etapa;
- `null`: depois da etapa concluída.

Se uma porta ou o saldo de combate impedir alcançar o ponto, a resposta não
dispara. Trechos anteriores ficam realizados; portas e criaturas são verificados
de novo ao prosseguir. `interrupt` exige uma justificativa do Mundo. Ouvir passos
ou falar não interrompe automaticamente uma caminhada. Iniciar conflito pausa
a ação para respeitar a iniciativa.

NPCs existentes podem falar, mover-se, abrir/fechar passagens, aguardar, atacar
corpo a corpo e iniciar/encerrar conflito. A IA não pode mover o Jogador, atravessar
paredes, atacar fora de alcance ou ignorar a ordem e os recursos de turno. Um
deslocamento de NPC usa a mesma busca de caminho de menor custo do Jogador,
respeitando paredes, quinas, terreno difícil e casas ocupadas. A IA escolhe o
destino; o Python encontra o percurso. A casa de uma porta aberta pode ser ocupada.
Sem caminho livre, uma rota arquitetônica permite aproximar-se de uma porta
fechada, mas a execução para nela, sem abri-la ou atravessá-la. Sem rota até o
destino, a ação é rejeitada. Isso não escolhe alvos ou táticas pelo NPC.

Se um movimento parar antes do destino, inclusive por saldo insuficiente no
turno, o relatório preserva a posição, o custo e o motivo da parada. As ações
seguintes da resposta não são executadas, evitando tentar um ataque cuja
aproximação falhou. Em turno de NPC, o fluxo encerra a vez após resolver o possível, registrando
a continuação impedida; não repete automaticamente a decisão. Os logs incluem o percurso encontrado e
`world.reaction_interrupted` com motivo e quantidade de ações restantes.

A [avaliação contextual de dificuldades](avaliacao-de-dificuldade.md) usa
`WorldPlan.adjudications`, resolvidas antes das ações. O código solicita apenas
tarefas que precisam de julgamento e valida IDs, fatos e completude. Categorias
típicas e vantagem/desvantagem são propostas; dados, CDs fixas e efeitos continuam
no motor. Não há chamada extra ao provedor para essa avaliação.

`PerceptionCheck` permanece legível em gravações anteriores: sua execução usa
Search real com os sentidos do NPC e o total guardado de Furtividade, sem aceitar
uma CD substituta proposta pelo Mundo. A aquisição de memórias exige compreensão
da fala, separadamente de perceber sua voz. Referências públicas `memory_ids`
aparecem somente em `say`; Influence usa fundamentação privada.

Descrições e falas são narrativas. Alterações mecânicas exigem operações
estruturadas. `describe` não cria objetos, obstáculos ou condições persistentes;
novos tipos de alteração do Mundo precisam de implementação própria.

O acompanhamento `npc_agency` aceita `IntentDecision` e 1–3 ações próprias
validadas. Não aceita deslocamentos, ataques ou Influence sem fala executada.
`resume_activity` somente nessa etapa encerra a conversa sem efeitos espaciais;
`start_conflict` preserva posições até a iniciativa. O executor preserva ações
já realizadas quando uma continuação falha. Objetivos privados não são eventos
públicos. Consulte [intenções dos NPCs](intencoes-dos-npcs.md).

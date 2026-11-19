# Sessão, conversa e histórico

Tier 3 · [Aplicação](README.md) · [Visão geral](../../../README.md)

## Entradas e estado

Código: [session.py](../../../src/trama/application/session.py),
[conversation.py](../../../src/trama/application/conversation.py),
[dialogue.py](../../../src/trama/application/dialogue.py).
`GameSession` reúne movimento, cena, criaturas, encontro e projeções de leitura.
`execute` é a entrada determinística de uma operação; o chamador precisa fornecer
intenções válidas. `Conversation` coordena planos completos e relatórios,
incluindo preparação espacial e respostas do Mundo.

O jogador comum entra pelo [GameFlow](fluxo-do-jogo.md), que usa esses serviços
para preparar mensagem, validar plano, escolher consultas e entregar respostas.
Usar diretamente a sessão não é uma segunda interpretação de linguagem natural.

## Conversa on/off

`Speech` separa on e off. `split_speech` lê colchetes na mensagem; colchetes
desbalanceados são rejeitados antes da execução. Somente o texto on pode servir
de origem para ações. Perguntas exclusivamente off não executam a intenção nem
avançam NPCs; o contexto do interpretador exclui off também no histórico.

`DialogueMessage` registra papel (`player` ou `narrator`) e os dois canais.
`Conversation.prepare` registra a entrada atual; `finish` acrescenta a resposta;
`failure` registra o retorno de falha. A API validada `extend_history` é usada
nesses caminhos e na reprodução de mensagens registradas.

## Histórico e memória mecânica

O [estado próprio da conversa](estado-da-conversa.md) é separado do histórico
textual: acompanha foco, participantes, objetivos privados de NPCs, pendências
e versões de propostas em `GameSession.conversations`. Só falas executadas o
atualizam; cada personagem recebe sua perspectiva conforme a audição real.

O histórico textual não é a fonte de posição, inventário ou recursos. Acrescentar
mensagens de uma sessão real não executa as ações descritas nem restaura estado.
O lote é validado antes da inclusão, preservando papéis e canais; campos extras,
mensagens vazias e instruções de sistema não são aceitos como mensagens do jogador.
A [preparação de cenários](../qualidade/preparacao-de-cenarios.md)
detalha essa API e os limites do histórico congelado.

O registro da última execução é separado das mensagens. Perguntas sucessivas
podem explicar um impedimento sem apagá-lo ou repetir efeitos. Veja
[resultados e impedimentos](resultados-e-impedimentos.md).

## Execução até o primeiro impedimento

O plano pode conter várias etapas ordenadas. Uma etapa concluída pode habilitar
a seguinte; a primeira impedida interrompe as posteriores. A execução conserva
a aproximação e os gastos já aplicados. Uma falha posterior da narração não
reverte nem repete o plano.

Operações já satisfeitas não precisam de aproximação ou gasto. Detalhes de
postura podem acompanhar ações sem criar mecânica de orientação. Interações
como falar ou observar podem gerar narração sem deslocamento; isso não autoriza
inventar efeitos mecânicos. As condições são registradas no relatório real.

## Consultas, reinício e verificação

`map_view`, `character_context`, `character_options` e resumos de inimigos
fornecem projeções de leitura para as interfaces. Consultá-las não gasta ações.
O reinício pelo fluxo restaura a sessão, limpa conversa e memória de execução
e invalida resultados antigos. Não há persistência geral de partida em disco.

As regressões de [histórico](../../../tests/integration/test_conversation_history.py),
[fluxo](../../../tests/integration/test_game_flow.py) e
[diálogo](../../../tests/unit/test_dialogue.py) usam entradas públicas e dados controlados.
Consulte [planos](planos-e-validacao.md), [contextos](../ia/contextos-e-contratos.md)
e [modos](fluxo-do-jogo.md#modos) para suas fronteiras.

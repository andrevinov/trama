# Movimento contextual e preparação espacial

Tier 3 · [Aplicação](README.md) · [Visão geral](../../../README.md)

## Aproximação de criaturas e oportunidades

Criaturas visíveis também são destinos de `move`: a aplicação busca uma casa
livre adjacente à posição atual do alvo, sem entrar no espaço dele. Os números
exibidos no mapa são enviados à interpretação junto do id e nome. Aproximar-se
e atacar continuam etapas distintas, cada uma validada antes de executar.

Durante movimentos em conflito, o coordenador de deslocamento verifica saídas
do alcance antes de cada passo que possa provocar oportunidade. A reação usa a
mesma resolução de ataque, sem gastar a ação normal nem exigir que seja o turno
de quem reage. Se o Jogador confirmar ou recusar uma oportunidade pendente,
somente a parte ainda não realizada do turno do NPC é retomada. Veja
[regras, escolha e limitações](../regras/reacoes.md).

## Movimento contextual e requisitos espaciais

Uma ação do Jogador pode pedir apenas seu objetivo. A própria implementação
publica um `SpatialRequirement`, consultável sem rolagens ou efeitos, com o tipo
de condição, alvo e posições válidas. O coordenador não conhece a lógica da
Cela 4, inventários ou classes para calcular a caminhada.

| Ação | Requisito |
| --- | --- |
| Investigar | Estar dentro da área referida |
| Pegar | Estar ao alcance do objeto conhecido |
| Atacar | Estar no alcance corpo a corpo e com linha de visão |
| Abrir/fechar, destrancar, escutar | Estar ao alcance da passagem |
| Acordar | Estar ao alcance do prisioneiro ou da sua grade |

`GameSession` publica requisitos de portas e ataques; `DungeonSession` publica os
das interações do cenário. `application/preparation.py` só calcula o percurso
sobre a grade de navegação e devolve `PreparedMovement`. A execução reutiliza
movimento, checkpoints, oportunidades e respostas do Mundo. Não há nova chamada
à IA para inserir uma microetapa. Um movimento explícito anterior não se duplica.

Antes de caminhar, `validate_preparation` verifica condições conhecidas: alvo,
visibilidade necessária, arma possuída, inspiração solicitada, chave e orçamento
de ação/interação. Não se gasta um recurso para validá-lo. Uma fechadura ainda
não examinada continua sendo descoberta na tentativa de interação; não se revela
um segredo apenas porque o motor conhece o estado completo.

Se uma aproximação contextual de ataque começa fora de combate, a aplicação
rola iniciativa antes de caminhar. Se um NPC agir primeiro, a tentativa para
sem movimento/ataque gratuito; o fluxo normal resolve os turnos de NPCs e o
Jogador volta a escolher sua ação quando tiver a vez. Se o Jogador agir primeiro,
a aproximação usa seu saldo de turno, sem Dash implícito. Se o saldo acabar,
conserva-se o percurso e a ação de ataque não é consumida. Pedidos de Surto de
Ação seguidos de ataque continuam ordenados: o poder concede o recurso antes da
validação do ataque; ele não concede movimento adicional automaticamente.

Depois do percurso, as condições são verificadas novamente e a primitiva valida
alcance/posição e executa a ação. Se o alvo mudou, a aproximação não vira uma
perseguição automática. O movimento já executado permanece registrado. A regra
primitiva `GameSession.execute` continua exigindo a posição correta; a
coordenação é de `Conversation.execute`, não do core de portas ou combate.

`allow_approach=false` em portas, ataques e interações de cenário proíbe movimento
contextual. A IA reconhece restrições como “sem sair do lugar” e publica o campo;
o Python o aplica sem analisar verbos. O campo controla aproximação implícita,
não cancela um movimento que o Jogador explicitamente pediu em outra etapa.

Uma operação já satisfeita não exige aproximação, gasto ou interrupção do plano.
Abrir uma grade já aberta e fechar uma já fechada são reconhecidos antes de
cobrar alcance. Destrancar uma já destrancada e acordar alguém já acordado também
são `already_satisfied`. No simulador isso não avança a rotina do banheiro nem
revela a fechadura à distância. Movimento protegido de crítico não é perdido por
essas operações sem alteração.

Os relatórios distinguem `completed`, `already_satisfied` e `blocked`. O último
pode coexistir com progresso parcial. `execution.player_movement` inclui a
aproximação; cada evento preparado aponta para a ação original com
`preparation_for`. A narração descreve somente os efeitos calculados.

O contexto do Mundo mantém os índices do plano original, publica
`spatial_requirement` e o percurso previsto em `preparation`.
`initiative_before_movement` sinaliza a preparação tática de um ataque. Os
checkpoints positivos contam casas da aproximação; `after_squares=null` ocorre
somente depois da ação. O percurso é recalculado quando a etapa é alcançada.
O motor não abre barreiras intermediárias, destranca, gasta poderes ou usa Dash
por conta própria. Alçapões novos não foram implementados neste incremento: os
checkpoints continuam disponíveis para impedimentos de Mundo já modelados.

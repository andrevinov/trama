# Acompanhamento das intenções dos NPCs

Tier 3 · [Aplicação](README.md) · [Estado da conversa](estado-da-conversa.md)

O Trama acompanha quem abordou o jogador, recebeu um gesto ou participou de uma
conversa estruturada realmente ouvida. Após uma ação significativa em exploração,
um interlocutor pode responder, ouvir, esclarecer, insistir, contrapropor ou
encerrar segundo seus objetivos e motivos. Essa política do Trama não é uma
regra adicional de D&D nem um temporizador de combate.

## Objetivos e iniciativa

Três registros têm funções distintas:

| Registro | Papel |
| --- | --- |
| `Persona.objective` | Objetivo central opcional, declarado no cenário. Sem ele, o diretor usa história e interesses da persona. |
| `IntentDecision.goal` e objetivo privado da conversa | O que o NPC deseja obter nesta conversa; a decisão executada atualiza sua própria perspectiva. |
| `IntentDecision.initiative` e `activity` | Iniciativa imediata escolhida e descrição privada do que pretende fazer agora. |

`IntentDecision.reason` explica como a iniciativa atende ao objetivo, considerando
os motivos e ressalvas das opções. `opinion_ids` referencia avaliações recebidas
pelo diretor. Um total favorável não obriga aceitar e a maior nota não escolhe
a ação automaticamente. O código valida dados, referências e efeitos; a adequação
semântica dos motivos continua sendo uma tarefa da IA e da avaliação manual.

Os registros existem somente na sessão e são limpos ao reiniciar. Não representam
planejamento geral de todos os habitantes, tarefas em segundo plano ou memória
persistente de campanha. As [relações iniciais](relacoes-iniciais.md) acrescentam
confiança e afeto privados do NPC, com
[evolução por episódios percebidos](evolucao-das-relacoes.md).

## Oportunidade após fatos executados

`AgencySystem.pending` parte das intenções anteriores e das falas executadas no
relatório. `event_id` e `sequence` ligam cada fala à contribuição correspondente
em `ConversationState`. Só interlocutores reais que ouviram a conversa são
incluídos; curiosos que apenas ouviram não se tornam participantes automaticamente.
Não é necessário inventar `parley` ou custódia para uma conversa pacífica.

A comunicação executada já registra a participação em `AgencySystem`, inclusive
na preparação compartilhada de situações. Isso estabelece o contexto para uma
ação seguinte, como aguardar, sem fazer chamada externa ou escolher a iniciativa.
A oferta de oportunidade e a agenda continuam no `GameFlow`.

Fala, espera e ações com progresso podem oferecer oportunidade a quem está
acompanhando, percebe a atividade e ainda não decidiu naquela interação. Consulta
off, plano vazio, olhar sem progresso e cliques da interface não avançam esse
acompanhamento. Uma fala ou espera do NPC já executada impede outra decisão na
mesma oportunidade comum. Um
[acontecimento novo percebido](acontecimentos-e-prioridades.md) pode abrir uma
reconsideração adicional, com orçamento próprio por interação. A primeira
abordagem preserva a chance do jogador responder.

Cada oportunidade gera no máximo uma etapa `npc_agency` pelo mesmo diretor,
configuração e SDK. Eventos recebidos, oportunidades oferecidas e decisões
iniciadas têm proteção contra repetição. `GameFlow.receive` também ignora respostas
antigas ou duplicadas. Antes de agendar outro participante da fila, o fluxo
confere se sua conversa ainda está ativa na perspectiva dele. Encerramento ou
suspensão percebidos podem retirar esse participante da fila sem outra consulta.

Em combate, iniciativa e turnos existentes organizam os NPCs. Não há polling,
chamadas por quadro, conversa entre agentes ou retry automático até obter decisão.
Uma falha conserva efeitos já executados e é apresentada pelo fluxo.

## Avaliar antes de decidir

No [conselho dos generais](../simulador/conselho-dos-generais.md), a sequência com
proposta e avaliação é:

1. O interpretador propõe a fala e os termos do jogador.
2. O Mundo propõe impactos em `reactions[].opinions`, sem ações desses mesmos NPCs.
3. Python executa a fala, resolve ouvintes e versões e calcula as notas.
4. `npc_agency` recebe objetivos, pendências e notas calculadas e escolhe a iniciativa.
5. Python valida e executa a decisão; só então a narração recebe os acontecimentos.

São quatro despachos no caso de um NPC, sem correção do interpretador: interpretação,
Mundo, agência e narração. Há uma decisão adicional por interlocutor elegível,
limitada àquela interação. Respostas factuais simples já executadas pelo Mundo
podem continuar com três despachos, sem uma segunda resposta obrigatória.
Avaliações não são repetidas em `npc_agency`.

Ofertas, revisões, aceitações e recusas estruturadas de NPCs passam por essa
segunda etapa de decisão. Não podem ser escolhidas no plano anterior ao cálculo.
Para aceitar ou recusar, o plano precisa citar avaliação atual da proposta e
versão correspondentes. Para contrapropor, cita uma `alternative` avaliada e
publica seus termos com o mesmo texto, tipo, responsável e ordem de execução.
Revisar a própria proposta também é `counteroffer`: o motor compara a versão
resultante, incluindo termos herdados e remoções, com a alternativa avaliada.
Uma opção apenas cogitada não se torna oferta por constar no contexto.

As [opiniões](opinioes-por-opcao.md) têm id, dono e `current`. Alteração relevante
nas crenças/perfil, revisão da versão de base, retirada percebida ou encerramento
da conversa tornam a nota antiga inadequada para fundamentar uma nova decisão.
Histórico e motivos permanecem disponíveis; `opinion_ids` desconhecidos, de outro
NPC/conversa ou desatualizados são rejeitados antes das ações. Na ausência de
avaliação pertinente, o NPC pode esclarecer ou contestar, sem simular uma nota.
A classificação semântica e uma razão livre incorreta não são certificadas por
essas validações estruturais.

## Contexto individual e pendências

`Conversation.agency_context` é construído depois da execução. Contém posição e
sentidos próprios, persona, memórias próprias selecionadas, conversas percebidas,
opiniões próprias, `relationships` do próprio dono e `observations.intent`. A posição do jogador só aparece quando
vista. Fala vista mas não compreendida tem `understood=false` e `text=null`.
Não inclui prompt, histórico global, fichas do jogador ou memórias de outros NPCs.
Adjudicações acústicas continuam validadas pelo motor.

Em conversa comum, o plano declara `initiative` e `reason`; gravações locais das
abordagens/gestos anteriores continuam legíveis sem esses campos. São iniciativas
suportadas `respond`, `listen`, `clarify`, `contest`, `insist`, `counteroffer`,
`accept`, `reject`, `close` e `start_conflict`. As operações continuam limitadas
a `say`, `wait`, `resume_activity` e `start_conflict` no acompanhamento comum.
O passo 8 acrescenta a saída validada por `leave`, descrita abaixo.

O passo 7 acrescenta `suspend`, `resume`, `investigate` e `protect` em oportunidade
por evento. A fase privada `npc_review` calcula antes da escolha e pode conservar
as notas quando nada foi afetado. Investigação/proteção admite uma operação
física suportada, com percepção e geometria validadas, sem ataques de agência.
O [contrato de acontecimentos](acontecimentos-e-prioridades.md) define seleção,
deduplicação, limites, suspensão e retomada.

A fala de acompanhamento fica vinculada à conversa daquela oportunidade.
Tentar atualizar outra conversa é rejeitado. O objetivo e a espera escolhidos
atualizam somente o registro privado do NPC, com origem própria de decisão;
não se inventa uma comunicação para registrar pensamento silencioso.

Mudar de assunto não resolve uma pergunta. O NPC pode insistir ou abandonar uma
pendência própria com motivo, usando seu id explícito em `resolves` na fala que
explica a retirada. O alias `latest` continua respondendo à pendência de outro
participante. Fechar ou suspender preserva o histórico e os assuntos pendentes.

## Espera e encerramento

`listen` usa `wait` isolado ou acolhimento `say` seguido de `wait`, com motivo
privado e condição concreta para continuar. Pode ser uma nova fala, se o jogador
quiser, sem pergunta ou negociação obrigatória. No passo 8, uma nova contribuição
dirigida ou continuação percebida da conversa a dois renova a escuta se não há
pergunta, pedido ou objeção explícita do NPC ainda ignorada. Responder/retirar
uma pendência continua renovando a permissão pelos metadados semânticos validados.
Fala inaudível, conversa com terceiros, off, só aguardar e reescrever o objetivo
não a renovam. Trocas audíveis respondidas pelo NPC também mantêm a renovação
anterior das abordagens.

Com a espera esgotada, o diretor precisa escolher uma iniciativa concreta.
Isso não impõe agressão: esclarecer, cobrar uma proposta, contestar ou encerrar
são alternativas. Uma recusa ou nota negativa não inicia conflito automaticamente.
`start_conflict` declara causa própria, sem usar `opinion_ids` como autorização
para violência; rola iniciativa nas posições atuais, antes de movimento e ataque.

`close` em conversa comum usa uma despedida `say` com `status=closed` e motivo
literal. O acompanhamento termina sem mover a criatura ou executar o acordo.
Em abordagem sem conversa estruturada, `resume_activity` conserva o encerramento
anterior e permite retomar a rotina existente. Na dungeon, o guarda pode sair do
alerta da abordagem. Não há entrega de chave, dinheiro, território ou liberdade
física por encerrar a conversa.

`leave` em conversa comum exige exatamente despedida `say` com `status=closed`
e depois `move`, com `waiting_for=null`. O destino deve ser um dos até oito
`observations.departure_targets`: um ponto livre visto em cada outra área, para
NPC com ficha. A lista é recalculada ao validar; alcance visual, ocupação e
geometria continuam no motor. Sob abordagem pendente, sem ficha ou sem destino
percebido, a saída é rejeitada antes da despedida. Não há teleporte ou remoção
do NPC do mapa. Impedimento posterior do percurso conserva somente efeitos já
executados, sem transformar a despedida em movimento concluído.

O foco e o objetivo podem surgir, mudar ou se esgotar sem proposta. `close`/`leave`
terminam a obrigação ativa de acompanhamento; os registros antigos permanecem
históricos. Nova conversa pode ter objetivo próprio. Os dados e critérios das
[cenas casuais](../simulador/conversas-casuais.md) demonstram esses usos. O passo 9
acrescenta [vínculos qualitativos](vinculos-afetivos.md) à perspectiva própria:
podem orientar prioridades, cuidado e recusas sem forçar aceitação. Atualizações
são calculadas antes da escolha, em `player_action`/`npc_review`; `npc_agency`
não altera sentimentos. Expressões amorosas tipadas exigem vínculo próprio e
respeito aos limites declarados conhecidos.

## Narração e verificação

Intenções, razões e referências privadas ficam nos contextos autorizados e nos
logs `agency.choice_validated` e `agency.intent_updated`. A narração recebe
comunicações e efeitos percebidos pelo jogador, sem números ou motivos privados.
Falha posterior da narração não desfaz decisões ou falas já executadas.

As regressões locais existentes verificam espera, audição, off, iniciativa antes
de ataques, falhas e reinício. `tools/context_contracts.py` inclui uma decisão de
contraproposta executada no conselho. A conferência offline pelo fluxo oficial,
com transporte fixo, cobre objetivos distintos, notas antes da escolha, pendência
ignorada, recusa sem violência, contraproposta, privacidade, duplicatas e falhas.
Esses resultados não medem a argumentação de um modelo real. As medições da
[bateria live anterior](../qualidade/agencia-live.md) continuam restritas aos casos
de abordagem originais; não são aprovação live deste incremento.

## Resposta pontual a gesto

Um destinatário que recebeu comunicação gestual também pode ser acompanhado,
mesmo sem abordagem ou ficha de combate. Se o Mundo já respondeu naquela etapa,
ninguém repete a decisão. Caso contrário, cria-se uma intenção `one_shot`, com
apenas o movimento observado e conhecimento próprio; após fala/espera fundamentada,
o acompanhamento pontual termina. Isso não concede ações físicas gratuitas.
Veja [comunicação gestual](comunicacao-gestual.md).

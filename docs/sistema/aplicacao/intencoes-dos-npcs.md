# Acompanhamento das intenções dos NPCs

Tier 3 · [Aplicação](README.md) · [Abordagem](conversa-antes-do-combate.md)

O incremento acompanha interlocutores que já abordaram o jogador. Após uma ação
significativa em exploração, um NPC com objetivo pendente pode retomar a conversa,
sem depender de ser novamente chamado pelo jogador. É uma regra geral do Trama;
não é um temporizador de combate nem uma regra adicional de D&D.

## Intenção e oportunidade de decisão

`AgencySystem` registra por NPC objetivo, atividade, resposta aguardada, número de
interações sem resposta e uso de espera. Uma abordagem inicia o acompanhamento;
Influence respondido e trocas audíveis respondidas pelo NPC atualizam a expectativa. O registro existe somente na sessão
em memória e é limpo ao reiniciar. Não representa planejamento geral de todos os
habitantes, tarefas em segundo plano ou passagem de tempo real.

O fluxo oficial captura os interlocutores antes de executar o plano do jogador.
Após os efeitos reais, oferece uma decisão aos que continuam envolvidos, percebem
a atividade e ainda não atuaram naquela interação. Fala, espera e ações com
progresso são oportunidades; consulta off, plano vazio, olhar sem progresso e
cliques da interface não avançam o acompanhamento. A primeira detecção preserva
a chance de responder: não cria uma segunda ação imediata do NPC. Um interlocutor
que já respondeu também não recebe ação duplicada.

Cada oportunidade gera uma única etapa `npc_agency`, pelo mesmo diretor do Mundo,
perfil/configuração e SDK. Não há loop de agentes nem repetição automática até
obter um plano. Um erro mantém os efeitos já executados e é apresentado pelo fluxo.
Em combate, a iniciativa e os turnos existentes continuam a organizar os NPCs.

## Contexto restrito ao NPC

`Conversation.agency_context` é construído depois da execução. Contém posição e
sentidos próprios, alinhamento/persona, memórias próprias selecionadas, objetivo
pendente, posição do jogador somente quando vista e comunicações percebidas.
Uma fala vista mas não compreendida tem `understood=false` e `text=null`. Não
inclui prompt, histórico global, fichas do jogador ou memórias de outros NPCs.
Adjudicações acústicas continuam validadas pelo motor; justificativas anteriores
de dificuldade não são transmitidas como conhecimento do NPC.

`IntentDecision` propõe objetivo, atividade e resposta concreta aguardada. Python
valida o ator e as ações antes de aplicar efeitos. Nesta primeira versão, o NPC
pode falar, aguardar brevemente com motivo, encerrar a conversa/retomar atividade
ou iniciar conflito. Deslocamento físico, busca de documentos, transferência de
itens e novas rotinas autônomas não são concedidos por esse contrato.

Uma espera isolada é permitida até uma resposta real ao NPC. Outra conversa com
terceiros não renova essa permissão; mudar o texto do objetivo também não a renova.
Esgotada a espera, o Mundo precisa escolher uma iniciativa concreta. Isso não
impõe agressão: cobrar uma proposta, fazer outra pergunta ou encerrar a abordagem
são alternativas. A adequação da escolha depende da persona e dos fatos percebidos.

`resume_activity` encerra a conversa e permite retomar a rotina já existente,
sem mover a criatura ou conceder liberdade física, chave ou dinheiro. Na dungeon,
o guarda deixa o estado de alerta da abordagem e sua rotina existente pode
continuar. `start_conflict` rola iniciativa nas posições atuais; deslocamentos e
ataques passam aos turnos normais. As duas operações encerram o acompanhamento
atual. NPCs mantêm suas capacidades e não recebem movimento ou ataque gratuitos.

## Narração e fatos auditivos

`KnowledgeSystem` mantém as 12 comunicações mais recentes com volume, ouvintes e
visibilidade reais. A narração recebe somente as percebidas pelo jogador, em
`perception.communications`; intenções privadas não são enviadas ao narrador.
Perguntas off consultam esse registro sem acrescentar acontecimentos ou decisões.
As instruções exigem distinguir observar uma conversa de compreender suas palavras,
respeitar o volume executado e não preencher intervalos com ações inventadas.

O registro e os validadores limitam dados e efeitos, mas não provam toda a prosa
livre gerada por IA. A [bateria live](../qualidade/agencia-live.md) confere o caso
real, privacidade, respostas efetivas, ausência de efeitos não executados e inclui
revisão semântica das narrações. Testes locais exercitam a espera limitada,
continuidade, consultas off, iniciativa antes de ataques, erro e reinício.

## Resposta pontual a gesto

Um destinatário que recebeu comunicação gestual também pode ser acompanhado,
mesmo sem abordagem ou ficha de combate. Se o Mundo já respondeu naquela etapa,
ninguém repete a decisão. Caso contrário, cria-se uma intenção `one_shot`, com
apenas o movimento observado e conhecimento próprio; após fala/espera fundamentada,
o acompanhamento pontual termina. Isso não concede ações físicas gratuitas.
Veja [comunicação gestual](comunicacao-gestual.md).

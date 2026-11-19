# Estado próprio da conversa

Tier 3 · [Aplicação](README.md) · [Conversa e histórico](sessoes-e-conversa.md)

## Objetivo e responsabilidade

`GameSession.conversations` mantém foco, participantes, assuntos pendentes e
propostas ao longo das falas. O estado é implementado por
[`ConversationState`](../../../src/trama/conversation_state.py); a coordenação
permanece em `Conversation` e `GameFlow`. É uma política do Trama, sem novas regras
de D&D, pontuação social ou decisões autônomas de NPCs.

O interpretador pode anotar `speak`/`challenge` com `ConversationUpdate`. O diretor
pode anotar `say` pelo mesmo contrato. Os metadados fazem parte dos pedidos já
existentes, sem chamada adicional de IA. O narrador não altera o estado.

## Contribuições executadas e percepção

[`KnowledgeSystem.communicate`](../../../src/trama/application/knowledge.py)
valida memórias, calcula ouvintes conscientes pelos sentidos reais e prepara a
atualização antes de emitir a fala. Referências inválidas são rejeitadas sem
registrar fala, conhecimento ou mudança de conversa. A contribuição é confirmada
com a comunicação executada, com autor, sequência lógica e `event_id` de origem.

Uma etapa de fala que não foi alcançada por um impedimento anterior não cria
estado. Off, histórico textual acrescentado, narração, planos sem etapas e pedidos
de esclarecimento não registram contribuições. Falha posterior da narração não
apaga a fala ou a atualização já realizada.

Os destinatários declarados devem existir; no plano do jogador, precisam ser
identidades conhecidas. Quem foi endereçado e ouviu passa a participar. Outros
ouvintes podem conhecer a troca sem se tornarem interlocutores. Ver a conversa
sem ouvir não ensina seus assuntos ou termos. O falante conserva o que ele próprio
disse; endereçar alguém que não ouviu não atualiza a perspectiva do destinatário.

A primeira contribuição estruturada identifica destinatários e cria a conversa.
Falas locais antigas, sem metadados, continuam válidas. Elas são anexadas como
comunicações sem classificação quando há uma conversa ativa correspondente;
sozinhas, não fabricam foco, termos ou objetivos. Gestos preservam o contrato
visual existente; este recorte estrutura as falas, sem presumir compreensão gestual.

## Conteúdo e perspectivas

| Campo | Significado |
| --- | --- |
| `id`, `participants`, `last_speaker` | Identificação e participantes conhecidos na projeção, com último falante percebido. |
| `focus` | Trecho literal da fala que identifica o foco atual. Alterar foco não resolve pendências. |
| `points` | Afirmações, perguntas, pedidos, ofertas, condições, objeções e assuntos laterais. |
| `resolves` na contribuição | Referências às pendências respondidas ou retiradas pela fala atual. |
| `proposals` | Ofertas e contrapropostas com autor, termos, versões e respostas. |
| `objective` | Objetivo e resposta aguardada privados do próprio NPC. |
| `status`, `reason` | `active`, `suspended` ou `closed`, com motivo da transição. |

Foco, pontos, termos novos/alterados e motivo de transição precisam ser trechos
literais da fala executada. No jogador, também devem pertencer ao on atual.
A classificação semântica e a interpretação de ordem continuam sendo propostas
da IA; o código não prova que uma pergunta foi realmente respondida pelo seu sentido.

Perguntas, pedidos, objeções e tópicos laterais podem continuar em aberto. Uma
resolução só é conhecida por quem percebeu sua fala de origem. O identificador
especial `latest` resolve a última pendência conhecida de outro participante;
um id explícito permite voltar a uma pendência anterior. Não há resolução por
simples mudança de assunto ou quantidade de mensagens.

Objetivos e respostas aguardadas só podem ser propostos para o próprio NPC em
`say`; a interpretação não atribui objetivos privados ao jogador. O
[acompanhamento](intencoes-dos-npcs.md) também atualiza o objetivo e a espera
privados após uma decisão, sem fabricar uma fala para pensamentos silenciosos.
Com `goal` e `waiting_for` nulos, a contribuição preserva o objetivo existente.
Para encerrar uma espera, o NPC informa seu objetivo atual e `waiting_for=null`.

## Propostas e versões

Uma contribuição pode registrar uma operação sobre proposta:

- `offer` cria oferta com termos novos. `in_reply_to` liga uma contraproposta a
  outra proposta conhecida, preservando o autor de cada uma.
- `revise` altera proposta do próprio autor, criando uma versão. Termos com id
  são substituídos; termos sem id são acrescentados; `remove_term_ids` remove.
  Os demais termos são herdados, sem reescrever a versão anterior.
- `accept` e `reject` registram a resposta de outro participante à versão que
  ele conhece, sem alterar seus termos.
- `withdraw` permite ao autor retirar sua versão atual.

Cada termo distingue pedido (`request`), contrapartida (`counterpart`) ou condição
(`condition`). `actor_id` informa o participante responsável, ou é nulo quando não
definido; `order` conserva uma ordem explícita de 1 a 8, sem calcular efeitos.
Pessoas e exércitos fora da cena podem ser mencionados no texto, sem inventar
participantes executáveis.

No exemplo da Bavária, devolução territorial, retirada do general e retirada
posterior do jogador são termos distintos. Alterar uma condição preserva as
demais. Uma alternativa apenas cogitada pelo NPC não entra como oferta: os termos
precisam aparecer em sua fala. Aceitar não transfere território, movimenta tropas,
gasta recurso nem registra cumprimento.

`proposal_id='latest'` referencia a proposta com versão conhecida mais recente
na conversa selecionada, inclusive após a fala anterior da mesma interação.
`version=null` usa a versão conhecida mais recente. Referências explícitas podem
responder a versões históricas conhecidas. Só o autor pode revisar a versão atual;
aceitar ou recusar exige conhecer todos os seus termos. Uma revisão ou aceitação
que não foi ouvida não atualiza a perspectiva de outro personagem.

## Ciclo de vida e limites

Uma contribuição com `status` exige motivo literal em `reason`. Fechar ou suspender
preserva assuntos e propostas. A retomada usa `conversation_id` conhecido e
`status=active`. Uma nova conversa pode começar com os mesmos participantes depois
de uma encerrada, com outro id. O estado não encerra a partida nem força saída
física da sala. Reação automática a acontecimentos é um incremento posterior.
Uma despedida pode ser registrada na conversa encerrada sem reabri-la; novos
assuntos exigem retomada. Encerrar o registro não remove custódia ou combate.

O registro completo das contribuições e versões fica em memória durante a sessão.
Reiniciar limpa esse registro e os identificadores. Não há save/load de campanha
ou consolidação automática de toda conversa em memórias de longo prazo.

As projeções contêm até três conversas, quatro referências recentes de contribuição,
doze pontos priorizando pendências recentes e três propostas com até duas versões
conhecidas. Há limite de 10.000 caracteres JSON por personagem: versões antigas,
propostas anteriores e pontos podem sair do contexto sem serem apagados do registro.
A ausência de uma referência na projeção não comprova que ela nunca existiu.

## Contextos e verificações

`conversations` na raiz contém a perspectiva do jogador em interpretação, Mundo e
narração. O Mundo recebe também `world.conversations`, por NPC. Em `npc_agency`,
a raiz contém somente a perspectiva do NPC solicitado. A narração remove o conjunto
do Mundo e não recebe objetivos privados. As verificações de contrato rejeitam
objetivos privados na projeção do jogador e o conjunto de NPCs na narração.

As amostras em `tools/context_contracts.py` exercitam as projeções com fala,
pergunta, objetivo privado e oferta reais pelo motor, sem modelo. A verificação é
`poetry run python tools/context_contracts.py --check`; mudanças intencionais seguem
a [revisão de contratos](../ia/contextos-e-contratos.md). Os eventos
`conversation.state_updated` relacionam conversa, autor, ouvintes e comunicação.
Validação local não mede a qualidade das anotações produzidas por um modelo real.

As [opiniões por opção e por termo](opinioes-por-opcao.md) consultam versões
percebidas por uma API do registro completo, validam todos os termos e conservam
notas privadas separadas das contribuições públicas. Uma alternativa cogitada
continua sem virar oferta até ser falada.

Contribuições percebidas podem iniciar o acompanhamento de conversas comuns.
A decisão privada de agência tem origem própria e atualiza somente o objetivo
do NPC; pendências continuam dependendo de resolução explícita na conversa.

O fechamento realmente comunicado também consolida compromissos e pendências
nas memórias dos participantes que os perceberam. Aceitação tem marco interno
de aquisição para distinguir promessa de evidência posterior de cumprimento.
Resumos verbais não são prova de execução. O registro completo e seus termos
continuam disponíveis para validar referências ao retomar outra conversa; veja
[episódios e memória entre encontros](evolucao-das-relacoes.md).

O início efetivo de combate suspende a perspectiva dos participantes da iniciativa
por evento físico, sem fabricar contribuição falada ou alterar o último locutor.
Perguntas e propostas permanecem. Um incidente percebido pode motivar suspensão
comunicada, investigação e retomada, usando a
[reconsideração por acontecimentos](acontecimentos-e-prioridades.md).

Conversas casuais podem ter foco e objetivo sem proposta, preço ou contrapartida.
A participação é registrada na comunicação executada, inclusive em preparações
reproduzíveis; só o coordenador agenda a iniciativa. Uma continuação dirigida
pode renovar a escuta sem pergunta formal, preservando pendências explícitas
ainda ignoradas. Encerrar conserva foco e objetivo como história e permite
novo encontro independente. Veja [intenções dos NPCs](intencoes-dos-npcs.md).

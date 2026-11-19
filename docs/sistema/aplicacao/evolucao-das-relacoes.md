# Episódios e memória entre conversas

Tier 3 · [Aplicação](README.md) · [Relações iniciais](relacoes-iniciais.md)

O passo 6 permite que um NPC atualize confiança e afeto por acontecimentos que
percebeu. `relationships.py` guarda níveis, fontes e história;
`application/relationship_history.py` valida a interpretação proposta pelo Mundo.
O mesmo `GameFlow` continua coordenando execução, cálculo e decisão individual.
A reconsideração por evento foi acrescentada no passo 7, sem temporizador ou
chamada por frame.

## Política de variação

São decisões de implementação do Trama, não fórmulas oficiais de D&D. A escala
−5 a +5, peso 2 e contribuição conjunta R limitada a ±12 escolhidos pelo usuário
no passo 5 permanecem. Neste passo, a IA indica categoria, motivo e evidência;
o código determina as dimensões e as variações nominais:

| Categoria | Confiança | Afeto | Evidência mínima |
| --- | ---: | ---: | --- |
| `promise_kept` | +1 | 0 | Ação do responsável observada após compromisso aceito e conhecido. |
| `costly_help` | +1 | +2 | Observação com custo explícito, identificada por `costly_help` nos tópicos. |
| `betrayal_discovered` | −2 | −1 | Ação observada que quebra compromisso ou evidência explícita de dano/traição. |
| `care_shown` | 0 | +1 | Cuidado efetivamente demonstrado e observado. |
| `suspicion` | −1 | 0 | Relato ou inferência próprios, sem comprovar a acusação. |
| `correction` | 0 | 0 | Observação contraditória do mesmo episódio, substituindo sua contribuição anterior. |

Confirmar uma suspeita substitui sua parcela pela categoria confirmada. Corrigi-la
retira a parcela daquele episódio, preservando o relato inicial, a interpretação
e sua correção na história. Não significa apagar um acontecimento real porque
o estado físico mudou depois; a pertinência dessa interpretação cabe ao diretor.

Cada nível é recalculado a partir do valor inicial e das parcelas atuais dos
episódios, com o limite aplicado ao resultado. Isso evita recuperação excessiva
ao corrigir um episódio quando a relação já estava no extremo da escala. O
registro guarda variação nominal, níveis antes/depois, motivo e origem. Uma
variação nominal pode resultar em diferença efetiva zero no limite.

## Contrato, percepção e repetição

`WorldReaction.episodes` admite até oito `RelationshipEpisode` em reação à ação
do jogador, em modo narrado, com `after_squares=null` e `check=null`. O lote é
validado antes de aplicar relações ou resumos. A atualização precede as opiniões;
a escolha continua em `npc_agency`, onde episódios e opiniões não são aceitos.
Fora do modo narrado, o acontecimento pode produzir memória, mas este mecanismo
não interpreta episódios durante o turno de combate. No passo 7,
`npc_review` também pode interpretá-los após
[acontecimentos próprios percebidos](acontecimentos-e-prioridades.md), antes da agência.

Cada item informa `owner_id`, `target_id`, `kind`, `evidence_id`, `reason` e
`interest_ids`. O dono precisa ser um NPC existente e o alvo outro personagem
da sessão. `evidence_id` referencia memória própria ativa vinculada ao alvo;
`latest_observation` e `latest_report` resolvem a mais recente pertinente após a
execução. Uma memória de outro dono ou resumo de conversa/relação não é prova.

Categorias confirmadas exigem `observation` e autor identificado como o alvo.
Suspeita aceita apenas `report`/`inference`. Correção exige observação contraditória
do mesmo fato, sem exigir que o alvo seja o autor da correção. O código valida
essas condições e as referências; decidir se a ação corresponde semanticamente
ao termo ou ao cuidado alegado continua sendo responsabilidade do diretor.

Para cumprimento, indique conversa, proposta, versão e termo (`at:1` a `at:8`
também são resolvidos). Deve existir aceitação percebida e responsável explícito.
A evidência precisa ter sido adquirida depois da promessa e da primeira aceitação
conhecida. Aceitar novamente não desloca esse marco. Uma promessa, uma crença na
promessa e sua execução são registros distintos.

A identidade é direcional por dono/alvo e, quando ligado a um compromisso, por
conversa/proposta/versão/termo. Nos demais casos, usa assunto e predicado da Claim.
Recontar, usar outro id de memória do mesmo fato ou trocar o rótulo de um episódio
confirmado não reaplica sua alteração. Valores contraditórios podem fundamentar
correção; suspeita pode ser confirmada. Renomear o mesmo fato como outro assunto
não é equivalência que o código consiga reconhecer: exige honestidade semântica
do diretor e continua sujeito à avaliação.

O lote também impede usar a mesma evidência/ocorrência para premiar vários
compromissos. Fontes já incorporadas na relação inicial não geram novamente a
mesma parcela. Não há pontos por falas, elogios, aceitação ou encerramento.

## Acontecimentos suportados e limites

Abrir/fechar uma passagem com mudança efetiva e ataques executados com dano
registram ação e autor para quem vê ambos, respeitando visão e condição dos
observadores. Apenas perceber o novo estado não identifica automaticamente seu
autor. O registro explícito abrange as operações de porta e ataque direto do
jogador/Mundo; não é inventário de todas as ações ou ataques de oportunidade.
Não observar a traição impede interpretar uma evidência que só outro conhece.
Uma ação nova pode renovar autoria e ocasião mesmo quando o resultado já era
conhecido; observações passivas repetidas continuam deduplicadas.

Ajuda com custo pode usar observação autoral do cenário que documente o episódio
e seu custo. Não foram acrescentadas operações de socorro, transferência de
moedas, tropas ou territórios. Falar que as executou não cria sua evidência.
A [reconsideração por novos acontecimentos](acontecimentos-e-prioridades.md)
foi acrescentada no passo 7, pela mesma coordenação da aplicação.

## Memória do encontro e privacidade

`ConversationState.closure_memories` seleciona, no fechamento efetivamente
comunicado, perguntas, pedidos, objeções, tópicos e termos de propostas percebidos
por cada participante. `KnowledgeSystem.consolidate` registra pendências
resolvidas/não resolvidas e compromissos oferecidos/aceitos/recusados/retirados,
com referências, ocasião e texto explícito de que registro verbal não comprova
cumprimento. Não copia o diálogo completo ou objetivos privados para todos.

Cada episódio interpretado também gera memória privada de inferência, com fonte
e evidência original, antes mesmo do encerramento. Resumos são `shareable=false`:
não podem ser divulgados automaticamente por `memory_ids`. Uma correção ou novo
estado substitui o resumo ativo correspondente, preservando os registros antigos
no histórico de conhecimento. Falha posterior de narração não desfaz os efeitos.

A seleção usa consulta, entidades e recência existentes, dando pertinência
também aos tópicos de compromisso, pendência e relação. Mantém os limites de
seis memórias e 3.500 caracteres por dono, além do limite agregado do Mundo.
Assim, continuidade não depende apenas das últimas mensagens, mas o contexto
continua sendo uma seleção, sem garantir que toda lembrança entre em cada chamada.

Os contextos privados exibem as últimas oito fontes de cada dimensão com sua
contagem total e os últimos quatro episódios do par. O estado, a base das opiniões
e `relationships.history(owner_id)` conservam a proveniência completa. Alterar a
relação invalida opiniões da base anterior. `relationship.episode_applied` registra
antes/depois, motivo e origem nos logs privados. Interpretação e narração não
recebem relações, notas ou resumos privados de outro personagem.

Os resumos derivados de episódios não pontuam em M. A evidência original ligada
a uma dimensão que contribui em R não volta a pontuar pelo mesmo aspecto em M.
`interest_ids=[]` cobre o fato inteiro; interesses explícitos restringem a
exclusão aos aspectos validados. Motivos e fontes continuam visíveis no diagnóstico.

Off não cria episódios ou consolida encontros; reiniciar restaura níveis e
memórias iniciais, limpa a história e permite repetir a situação do início.
Persistência de campanha fora da sessão continua fora deste recorte.

O passo 9 acrescenta [vínculos qualitativos](vinculos-afetivos.md) à mesma relação.
Episódios numéricos preservam esses estados: perder confiança não termina amor,
e afeto alto não forma amizade automaticamente. Cuidado validado pode servir de
evidência, sem acrescentar pontos por uma segunda interpretação qualitativa.

## Conferência

O runner oficial com transportes fixos foi exercitado para promessa, aceitação,
porta realmente fechada, aplicação única, fechamento e retomada em nova conversa,
privacidade, off e reinício. A auditoria `tools/context_contracts.py --check`
reproduz aceitação, cumprimento e arquivos nos contextos reais. As regressões em
`tests/integration/test_npc_agency.py` cobrem suspeita/confirmação/correção, limites,
história, dono da evidência e lote inválido sem efeitos parciais. São verificações
offline; não medem a qualidade semântica de um modelo real.

Para avaliação manual no [conselho](../simulador/conselho-dos-generais.md), comece
com um compromisso local executável, obtenha a aceitação, realize a operação e
consulte `relationship.episode_applied` em modo debug. Encerre e retome o encontro.
Compare execução, acusação sem observação e dez cumprimentos protocolares. O
diretor precisa propor uma interpretação pertinente; o código não atribui
significado narrativo automaticamente à ação física.

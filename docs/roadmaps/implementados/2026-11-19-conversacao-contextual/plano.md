# Motor de conversação contextual e cenário dos generais

[Roadmaps implementados](../README.md) · [Aplicação atual](../../../sistema/aplicacao/README.md)

Estado: **implementado**, com os nove passos entregues em **19/11/2026**.
Planejamento registrado na mesma data, a partir
da [conversa compartilhada sobre o Trama](https://chatgpt.com/share/6afe6c6c-7aa4-83e9-96a9-8a15e78dff74).

## Objetivo e experiência desejada

Permitir que um NPC mantenha objetivos, forme opiniões sobre o que percebe e
escolha sua próxima iniciativa de acordo com alinhamento, persona, memórias e
relação com o interlocutor. O primeiro cenário é uma reunião entre dois generais:
o jogador representa um deles; o outro é um NPC que pode negociar, desconfiar,
questionar, fazer contrapropostas ou encerrar a conversa.

O cenário fornece pessoas, interesses e acontecimentos anteriores. A opinião
sobre uma oferta deve surgir durante o jogo. Não haverá lista de frases certas,
árvore de diálogo ou condição roteirizada como “aceitar paz ao receber metade
da Bavária”. O jogador pode apresentar uma proposta que não foi escrita pelo
autor e continua dono de suas intenções e decisões.

O mesmo motor deverá sustentar uma conversa casual, um conselho entre amigos ou
uma oferta espontânea de ajuda. Nem toda conversa contém pedido, negociação,
impasse ou teste de Persuasão.

Os nove passos entregam cenário, estado da conversa, opiniões, agência após
os cálculos, relações com confiança/afeto e evolução por episódios percebidos
com memória entre encontros, reconsideração por acontecimentos percebidos e
conversas casuais e vínculos qualitativos de amizade, atração, paixão e amor.
A implementação avança por incrementos solicitados,
com avaliação manual no simulador como prioridade, conforme o pedido na conversa.

## Base anterior e lacunas do planejamento

| Elemento | Base atual | Incremento necessário |
| --- | --- | --- |
| Entrada e execução | `GameFlow`, janela e `game.runner` compartilham a coordenação. | Integrar o estado sem criar outro coordenador ou simulador. |
| Conversa | `Conversation` coordena planos, histórico on/off e relatórios; `parley` registra uma abordagem. | Estado semântico com foco, participantes, objetivos, pendências e propostas, independente de custódia ou abordagem. |
| Persona e alinhamento | `SocialProfile` contém alinhamento, identidade, história e interesses com pesos. | Explicitar objetivo central, objetivos secundários e temperamento quando necessários ao cenário. |
| Disposição | Há cálculo determinístico por pedido, referências de memória e reutilização de resultados. | Avaliar alternativas e termos específicos, além do pedido de escuta. |
| Memória | Conhecimento tem dono, origem, ocasião e seleção contextual. Relato não equivale à verdade. | Registrar propostas, compromissos, interpretações e episódios relevantes da relação. |
| Agência | Há objetivo, atividade e resposta aguardada por interlocutor, com espera limitada. | Sustentar objetivos numa conversa comum e agir a partir de opiniões e acontecimentos novos. |
| Relações | Não há estado geral de confiança, afeto ou vínculos entre personagens. | Relações direcionais que atravessem conversas na mesma sessão. |
| Acontecimentos | Percepção, efeitos e iniciativa já existem, com limites próprios. | Reconsideração da prioridade e suspensão ou retomada da conversa por evento percebido. |
| Cenários | O simulador carrega JSON por `--scenario` e situações por `--situation`. | Nova sala de negociação, preservando a dungeon e seus dados. |

Referências atuais: [sessão e conversa](../../../sistema/aplicacao/sessoes-e-conversa.md),
[fluxo](../../../sistema/aplicacao/fluxo-do-jogo.md),
[disposição social](../../../sistema/aplicacao/disposicao-social.md),
[conhecimento](../../../sistema/aplicacao/conhecimento-dos-npcs.md),
[intenções dos NPCs](../../../sistema/aplicacao/intencoes-dos-npcs.md) e
[carregamento de cenários](../../../sistema/simulador/carregamento-de-cenarios.md).

## Contratos que orientam todos os incrementos

- **Perspectiva individual:** cada NPC decide com aquilo que percebeu, lembra ou
  acredita. O contexto completo do mestre não se torna conhecimento individual.
  Indiretas e ironias podem ser interpretadas incorretamente; a inferência tem
  dono e fonte e não modifica a intenção declarada pelo jogador.
- **Estado público e privado:** termos falados pertencem aos participantes que
  os perceberam. Objetivos, alternativas imaginadas e avaliações privadas só
  entram no contexto do dono. A intenção de um gesto não se torna entendimento.
- **Papéis separados:** o interpretador identifica a contribuição do jogador;
  o diretor do Mundo propõe interpretações e decisões do NPC; o código valida,
  calcula e registra; o narrador apresenta fatos perceptíveis já executados.
- **Efeitos explícitos:** propor, aceitar e cumprir são estados distintos.
  Aceitar paz não movimenta exércitos, transfere territórios, cria itens ou muda
  o inventário. Cada consequência material exige operação implementada.
- **Continuidade:** off não avança objetivos, relação ou acontecimentos.
  Falha de narração preserva efeitos registrados. Reiniciar restaura o cenário,
  sem reaplicar ofertas, lembranças ou mudanças de relação antigas.
- **Escopo:** não introduzir arquitetura de agentes, planejamento ilimitado,
  banco vetorial, relógio geral ou simulação de reinos para sustentar a conversa.
  Preservar os limites do combate existente.

Alinhamento estável, pontuação, relações e critérios de vínculo são decisões do
Trama. Não são apresentados como fórmulas oficiais de D&D. Regras de Influence,
ações, percepção e combate permanecem vinculadas às referências da edição 2024
nos documentos respectivos.

## Ordem das entregas

| Passo | Entrega | Depende de |
| --- | --- | --- |
| 1 | **Entregue em 19/11/2026:** sala dos generais jogável com as capacidades atuais. | Base existente. |
| 2 | **Entregue em 19/11/2026:** estado da conversa e registro estruturado de falas e propostas. | 1. |
| 3 | Opinião por opção e por termo, com pontuação explicável. | 2. |
| 4 | Agência sustentada pelos objetivos e pelas opiniões. | 3. |
| 5 | Confiança e afeto iniciais incorporados às decisões. | 3 e 4. |
| 6 | **Entregue em 19/11/2026:** evolução da relação e memória entre conversas. | 5. |
| 7 | **Entregue em 19/11/2026:** reconsideração por segredos e acontecimentos, com suspensão e retomada. | 2 a 4; usar 5 e 6 quando a relação for pertinente. |
| 8 | **Entregue em 19/11/2026:** aplicação do mesmo motor em conversas casuais. | 4 a 7. |
| 9 | Amizade e vínculos amorosos, com critérios próprios. | 6 e 8. |

### Passo 1 Cenário dos generais

Criar um cenário próprio em `src/trama/scenarios/`, carregável pelo mesmo
`poetry run trama-simulator --scenario CAMINHO`. A dungeon continua sendo o padrão;
reabri-la inicia sua situação original. Alternar cenários não implica salvar
o progresso de uma partida.

Preparar uma sala, posições e sentidos, um NPC general e o personagem jogador.
O general precisa de identidade, alinhamento, interesses ponderados e memórias
com origem: por exemplo, trégua rompida, desgaste da guerra e campanhas recentes.
Esses exemplos são dados iniciais a definir para a aventura, não fatos já
implementados nem condições obrigatórias de uma resposta. Seu objetivo central
e o que deseja obter naquela audiência devem ser identificáveis e distintos.

Reutilizar fichas suportadas sem inventar uma classe “general”. A guerra e os
exércitos ficam fora de cena, representados por informações e compromissos.
Ajustar títulos ou textos fixos da interface que ainda pressupõem a dungeon.
Não forçar uma abordagem de custódia para iniciar a conversa.

**Aceite manual:** abrir a reunião, conversar com o NPC com os recursos atuais,
reiniciar e voltar à dungeon pelo comando padrão. O NPC não revela memórias
privadas ao jogador por descrição inicial. Este passo estabelece a base jogável;
a negociação completa chega nos passos seguintes.

### Passo 2 Estado próprio da conversa

Os passos 2 a 5 estão entregues; os passos 6 a 9 permanecem planejados.

Adicionar estado explícito à sessão, mantendo `Conversation` como coordenador
existente. O nome e a divisão final dos tipos devem seguir o código; não criar
uma segunda classe que também coordene o jogo.

O estado deve registrar participantes, último falante, foco atual, objetivos por
NPC, respostas aguardadas, assuntos laterais e perguntas em aberto. Deve também
acompanhar propostas versionadas, condições, contrapartidas, ordem de execução
e situação `active`, `suspended` ou `closed`, com motivo das transições.

Uma contribuição pode conter afirmação, pergunta, pedido, oferta, condição,
objeção ou retirada de proposta. Usar trechos e referências às comunicações
executadas para validar sua origem. Só aplicar o que foi efetivamente comunicado
e percebido; um plano interpretado que falhou não entra como fala realizada.
Uma contraproposta do NPC passa pelo mesmo registro, com o autor correto.

No exemplo da Bavária, preservar separadamente o pedido de devolução, a retirada
das tropas adversárias primeiro, a retirada posterior prometida pelo jogador e
a alegação de cansaço dos povos. Quem ouviu a alegação pode lembrar que ela foi
dita imediatamente; não precisa aguardar o fim da conversa. Ideias privadas
não se tornam propostas públicas por terem sido avaliadas.

**Aceite manual:** mudar de assunto e voltar a uma pergunta pendente; alterar
somente uma condição de uma oferta sem apagar sua versão anterior; encerrar
uma conversa sem pedido formal. Um observador que não ouviu não conhece os termos.

### Passo 3 Opinião por opção e por termo

Entregue em 19/11/2026, conforme o registro de implementação abaixo.

Estender o cálculo existente para identificar a opção avaliada, os termos que
produzem cada efeito e as memórias que sustentam a avaliação. Considerar uma
proposta recebida, contrapropostas plausíveis e a alternativa de não chegar a
acordo. A última é uma expectativa do NPC, não uma previsão verdadeira do futuro.

A base atual pode ser expressa como `S_base = A + P + M`:

| Parcela | Regra já implementada a preservar como base |
| --- | --- |
| `A` | Alinhamento entre −2 e +2. |
| `P` | Efeito −1, 0 ou +1 por interesse, multiplicado por peso de 1 a 4; soma limitada a ±6. |
| `M` | Contribuições de crenças próprias agrupadas por Claim; observação/hábito pesa 2 e relato/inferência pesa 1; soma limitada a ±3. |

Atualmente, total ≥3 indica disposto; ≤−3, indisposto; demais valores, hesitante.
Esses limiares descrevem disposição diante de um pedido. Não transformá-los em
obrigação de aceitar qualquer alternativa, nem em resultado de dado para toda
opinião. O diretor identifica impactos semânticos; Python confere referências,
pesos e limites e calcula os saldos. Uma avaliação deve conservar os motivos,
inclusive os de termos favoráveis e desfavoráveis que se compensaram.

A memória de uma trégua rompida pode pesar contra retirar-se primeiro. Trocar
essa condição por retirada simultânea exige reavaliar o fundamento afetado;
o interesse territorial continua existindo. Repetir a mesma promessa não cria
memória nova nem outra chance de rolagem. Formalizar a identificação de versões
e equivalência de termos antes de ampliar o cache atual de pedidos.

**Aceite manual:** o general pode desejar paz e rejeitar a ordem das retiradas;
uma oferta revisada muda essa objeção sem apagar as demais. Toda contribuição
numérica tem razão e origem inspecionáveis nos logs. Pensar em alternativas
não rola Influence; um pedido concreto segue as regras pertinentes.

### Passo 4 Agência a partir dos motivos

Entregue em 19/11/2026, conforme o registro de implementação abaixo.

Ampliar o acompanhamento existente para conversas comuns, sem exigir uma
abordagem ou gesto. Distinguir objetivo central da persona, objetivo daquela
conversa e iniciativa imediata. Uma pergunta ignorada continua pendente mesmo
quando o jogador prefere outro assunto; o NPC também pode abandoná-la com motivo.

Usar opiniões e motivos para escolher entre responder, ouvir, esclarecer,
contestar, insistir, sugerir outra opção, aceitar, recusar ou encerrar. A agência
não é apenas escolher o maior total. A avaliação precisa informar o que o NPC
quer obter agora e por que aquela iniciativa serve ao seu objetivo.

O fluxo precisa permitir que os cálculos determinem a resposta: propostas de
avaliação vêm antes dos saldos calculados; a decisão deve usar esses resultados
ou alternativas condicionais validadas pelo motor. Não escolher uma resposta
definitiva com um total inventado pelo modelo. Escolher a menor extensão viável
de `world`/`npc_agency`, sem duplicar avaliações nem criar conversas entre agentes.

Conservar a espera limitada e impedir decisões duplicadas na mesma oportunidade.
Não forçar falas a cada mensagem: ouvir ou encerrar também podem ser decisões
coerentes. Iniciativa de conflito continua precedendo movimento tático ou ataque.

**Aceite manual:** apresentar uma solução não prevista, ignorar uma pergunta
do general e oferecer um argumento irrelevante. O NPC deve conseguir escolher
uma iniciativa coerente em vez de apenas repetir a última fala ou esperar sempre.
Uma recusa social não causa violência automaticamente.

### Passo 5 Relações iniciais e peso contextual

Entregue em 19/11/2026, conforme o registro de implementação abaixo.

Introduzir confiança e afeto como dimensões independentes, com dono e destinatário.
`NPC → jogador` não implica `jogador → NPC`. Começar com valores declarados nos
dados do cenário, mantidos entre conversas na mesma sessão. Isso não inclui
save/load de campanha nem atribui sentimentos ao personagem do jogador.

Estender a proposta de cálculo para `S_opcao = A + P + M + R`, em que `R` reúne
contribuições de confiança e afeto aplicáveis àquela opção. Confiança incide,
por exemplo, sobre uma promessa; afeto, sobre consequências para o interlocutor.
Vínculos extremos devem poder produzir a maior contribuição quando pertinentes,
sem converter afeição em aceitação automática de qualquer pedido.

**Decisão numérica tomada pelo usuário em 19/11/2026:** escala -5 a +5 por
dimensão, peso 2, impacto contextual -1/0/+1 e R conjunto limitado a ±12.
Compensar impactos por destinatário/dimensão antes de aplicar o peso; preservar
os limiares ±3 de orientação. Com relação neutra, conservar a base. A conversa
de origem não fixara esses números; a escolha foi feita na implementação deste passo.

Evitar pontuar duas vezes a mesma justificativa como memória e relação. O vínculo
pode resumir uma história; citar novamente o episódio que o formou não concede
outro bônus pelo mesmo motivo. Registrar fontes e distinguir consequências novas.

**Aceite manual:** comparar inimigo confiável e amigo pouco confiável. Relações
diferentes devem mudar decisões pertinentes; confiança alta pode levar a uma
explicação franca da recusa, sem obrigar o general a abandonar seu povo.

### Passo 6 Evolução da relação e memória dos encontros

**Entregue em 19/11/2026.** Contrato, política e limites em
[episódios e memória](../../../sistema/aplicacao/evolucao-das-relacoes.md).

Atualizar a relação por episódios significativos percebidos: compromisso cumprido,
ajuda com custo, traição descoberta ou cuidado demonstrado. O diretor propõe a
interpretação e sua evidência; o código valida o evento, o dono, a dimensão e
a variação conforme a política definida. Registrar antes/depois e motivo.

Separar promessa, crença na promessa e cumprimento efetivo. Uma traição oculta
não reduz confiança por conhecimento onisciente. Uma acusação pode gerar suspeita
sem comprovar a traição; uma correção posterior preserva a história da crença.
Repetir o mesmo episódio ou renarrá-lo não reaplica sua alteração.

Ao encerrar uma conversa, preservar compromissos, pendências e episódios relevantes
nas memórias dos participantes adequados. Não copiar todo o diálogo para todos
nem depender exclusivamente do histórico recente do prompt. Definir a política
de variação e seleção dessas memórias sem acumular pontos por quantidade de falas.

**Aceite manual:** duas conversas com o mesmo NPC retomam uma promessa; cumprimento
e quebra descoberta têm consequências distintas. Dez cumprimentos protocolares
não equivalem automaticamente a um sacrifício. Reiniciar restaura a relação inicial.

### Passo 7 Segredos e acontecimentos que mudam a prioridade

**Entregue em 19/11/2026.** Contrato, critérios de percepção e limites em
[acontecimentos e prioridades](../../../sistema/aplicacao/acontecimentos-e-prioridades.md).

Permitir que um fato novo percebido reabra avaliações afetadas e altere a prioridade
do NPC sem aguardar outra fala do jogador. Integrar essa oportunidade ao `GameFlow`
e aos registros existentes de percepção e conhecimento, com identificação de evento
e proteção contra repetição. Não criar polling, temporizador ou chamadas por frame.

Uma revelação falada começa como relato. Apresentar um documento não prova sua
autenticidade: mostrar, perceber e reconhecer devem ter suporte real antes de
constarem como evidência. Começar pelo segredo transmitido em fala; acrescentar
evidência material somente com a interação mínima que o incremento exigir.

Um incidente pode suspender a conversa e preservar suas pendências. Distinguir
ouvir um ruído, ver um soldado ferido e identificar o agressor. A decisão pode
ser investigar, proteger alguém, encerrar o encontro ou iniciar conflito, mas
só operações suportadas produzem efeitos físicos.

O exemplo do soldado atingido por um disparo exige resolução implementada ou
incidente autoral explícito com efeitos validados. O combate atual não cobre
ataques à distância em geral. A primeira avaliação pode usar agressão já suportada;
o narrador não pode inventar tiro, ferimento, socorro ou ataque para simular agência.
Identificar também limites de participantes e lados do conflito antes de prometer
um confronto com terceiros.

**Aceite manual:** um segredo relevante muda a objeção correspondente, enquanto
uma revelação irrelevante não reinicia toda a negociação. Comparar incidente
ouvido, visto e não percebido. Retomar a conversa preserva a pergunta anterior
ou registra por que deixou de importar. Se houver combate, respeitar iniciativa,
alcance, ações e recursos existentes.

### Passo 8 Conversas casuais com o mesmo motor

**Entregue em 19/11/2026.** Dados, comandos, simplificações e critérios em
[conversas casuais](../../../sistema/simulador/conversas-casuais.md).

Exercitar o motor fora da negociação militar: uma amiga que pode ouvir ou aconselhar
e um garoto de rua que pode agradecer e oferecer orientação. Usar dados e situações
próprios, pelo mesmo carregador, sem módulos de decisão específicos para cada cena.
Uma moeda entregue só é fato consumado se existir operação que valide a transferência;
caso contrário, usar uma memória inicial declarada do episódio.

Permitir que foco e objetivos surjam, mudem ou se esgotem. Amizade pode estar
declarada inicialmente para avaliar esse uso sem antecipar os gatilhos do passo 9.
Não exigir formulário de proposta, aceitação, contraprestação ou Influence para
acolhimento, gratidão e ajuda espontânea.

**Aceite manual:** “só precisava contar isso a alguém” pode levar a amiga a escutar
em vez de aconselhar. O garoto pode agradecer e sair, ou oferecer direção quando
perceber necessidade. A cena não depende de o jogador pedir cada iniciativa.

### Passo 9 Amizade e vínculos amorosos

Depois de avaliar confiança e afeto, definir gatilhos de amizade ligados à história
e ao cuidado recíproco. Ampliar para atração, paixão e amor com critérios próprios;
confiança alta não vira amizade automaticamente, e amizade não vira romance por
acúmulo de pontos. Cada personagem pode corresponder ou não.

Documentar formação, manutenção e ruptura dos vínculos. O alinhamento permanece
estável no recorte; uma transformação de persona exige acontecimento significativo,
sem alteração silenciosa para justificar uma resposta. Não criar progressão ou
decaimento por tempo sem uma regra de tempo e um caso concreto que os exijam.

**Aceite manual:** sustentar amizade sem atração, afeto sem confiança e interesse
não correspondido sem impor escolhas ou sentimentos ao jogador. O vínculo pode
modificar prioridades e a forma de recusar, além de favorecer uma aceitação.

## Avaliação e consolidação

O primeiro recorte é **a sala jogável, seguida de estado, opiniões e agência**
(passos 1 a 4). Confiança/afeto, sua evolução, interrupções e outros vínculos são
entregas posteriores, não requisitos para iniciar a primeira conversa manual.

Não criar uma bateria nova como substituto da experiência pedida pelo usuário.
Durante os incrementos, executar as regressões locais existentes pertinentes e
conferir contratos alterados com `poetry run python tools/context_contracts.py --check`.
Uma mudança intencional segue a revisão de diff e justificativa dos
[contratos de IA](../../../sistema/ia/contextos-e-contratos.md), sem atualizar
a referência apenas para fazer a verificação passar.

Cada avaliação manual registra a proposta, fatos percebidos, decisão, efeitos
e ressalvas observadas. Julgar separadamente fidelidade mecânica e coerência da
prosa. Uma resposta convincente ou uma conversa bem-sucedida não mede repetibilidade.
Usar situações reproduzíveis quando houver preparação específica; as escolhas
e respostas reais da IA continuam sendo observações, não resultados determinísticos.

Na consolidação dos comportamentos aprovados, converter os casos relevantes em
regressões e usar contrapartes que possam reprovar uma abstração incorreta:
informação ouvida/não ouvida, promessa nova/repetida, incidente visto/oculto.
Uma avaliação live dedicada exige escopo, orçamento e autorização próprios,
conforme a [política de live tests](../../../sistema/qualidade/politica-live-tests.md).

As explicações e projeções para o jogador permanecem linguagem de jogo; pontuações,
memórias privadas e critérios internos ficam nos logs e contextos autorizados.
Não criar painel de diagnóstico como parte obrigatória da conversa.

## Encerramento e documentação

O passo 1 está entregue e documentado no
[conselho dos generais](../../../sistema/simulador/conselho-dos-generais.md).
O cenário usa `generals_council.json`, sessão comum e respostas `say` após fala
dirigida ao interlocutor, sem abordagem de custódia. O título do cenário e a guia
NPCs identificam a cena corretamente. As verificações são locais, sem nova bateria
de testes ou chamadas pagas; a conversa com modelo real fica para avaliação manual.

Verificações em 19/11/2026: **259 testes locais existentes aprovados** nas seleções
de carregamento/CLI/contratos/fronteiras (108), interface/fluxo/painel de combate
(49) e dungeon/conhecimento/execução do Mundo (102). Os ajustes nos testes existentes
acompanham a troca do rótulo Inimigos por NPCs; não foi criada uma bateria nova.
A amostra do conselho foi acrescentada ao fim da auditoria, preservando a abertura
da dungeon usada pelos critérios antigos. Contratos revisados com justificativa,
metadados, links e integridade das evidências históricas conferem.

Uma verificação offline adicional pelo `game.runner`, com respostas fixas, cobriu
abertura, fala com memória pública, ausência da memória reservada na narração,
off, movimento, porta e reinício. A janela real foi desenhada nas três guias com
driver SDL sem tela; a CLI abriu e encerrou conselho e dungeon padrão sem provedor.
Esses resultados não avaliam interpretação ou argumentação de um modelo real.

O passo 2 entrega [`GameSession.conversations`](../../../sistema/aplicacao/estado-da-conversa.md),
com contribuições ligadas a falas executadas e ouvintes reais. O mesmo contrato
anota falas do jogador e de NPCs, sem nova consulta ao provedor. Foco, pendências,
propostas com versões e transições de ciclo de vida ficam no estado; objetivos
privados têm dono e não chegam ao narrador. Aceitar verbalmente não executa
efeitos materiais. O registro é local à sessão e limpo no reinício.

Uma verificação offline pelo runner e adaptadores reais, com transporte fixo,
cobriu mudança e retomada de assunto, resolução de pendências, contraproposta,
revisão com termos herdados, aceitação, suspensão, retomada, encerramento,
privacidade, audição, referência inválida sem efeitos, reinício e fala não alcançada.
Controles adicionais verificaram que revisão não revela termos antes inaudíveis,
que uma oferta incompletamente conhecida não pode ser aceita, que a despedida
não reabre o encontro e que falha de narração conserva a contribuição executada.
A suíte padrão completa terminou com **1.246 testes aprovados em 655,39 s**.
A seleção focada anterior teve 203 aprovações e está contida nessa suíte.
Contratos de IA, metadados, links locais, diff e evidências históricas conferem.
Nenhuma chamada paga foi realizada; a interpretação e a conversa com modelo real
continuam destinadas à avaliação manual.

O passo 3 entrega [opiniões por opção e por termo](../../../sistema/aplicacao/opinioes-por-opcao.md),
com `OptionAssessment`, `TermAssessment` e base compartilhada com a disposição.
Reações após fala realmente ouvida avaliam propostas/versões percebidas,
alternativas privadas e a expectativa sem acordo. O código valida termos e
memórias, compensa sinais e aplica limites por opção, conservando motivos e
origens nos logs `social.option_evaluated`. Cogitar não registra oferta pública,
cria memória ou resolve Influence. O cache separado reconhece equivalência
literal/estrutural e mudanças da base própria, sem ampliar o cache de pedidos.

A conferência pelo runner com transporte fixo aprovou oferta unilateral em -4,
alternativa simultânea em +4 com objeção territorial preservada, expectativa sem
acordo, revisão, repetição sem dado, rejeição atômica de referências inválidas,
privacidade, falha de narração e reinício. Controles isolados verificaram sinais
opostos preservados, limites, memória não multiplicada entre termos/interesses,
versão parcialmente ouvida, destinatário surdo, retomada de conversa antiga e
reavaliação por informação relevante sem multiplicar o mesmo relato.
A suíte padrão completa teve **1.246 aprovações em 659,70 s**. A seleção
existente de disposição, Mundo, agência e fronteiras teve 153 aprovações. Após
ajustar o teto padrão do diretor de 2.000 para 6.000 tokens para comportar as
avaliações, os 20 testes de composição passaram e a conferência pelo runner
confirmou o limite enviado. Limites explícitos do chamador são preservados.
Contratos de IA foram revisados com justificativa e conferidos sem
rede; metadados, diff e evidências históricas também conferem. Nenhuma chamada
paga ou nova suíte live foi realizada. A qualidade semântica do modelo continua
sendo avaliada manualmente no simulador. Nessa entrega, a escolha da iniciativa pelas notas
foi reservada ao passo 4, registrado a seguir.

O passo 4 entrega [agência em conversas comuns](../../../sistema/aplicacao/intencoes-dos-npcs.md)
pelo acompanhamento existente. Persona distingue objetivo central opcional;
`IntentDecision` distingue objetivo da conversa, iniciativa imediata, motivo
privado e avaliações utilizadas. A fala real engaja interlocutores sem parley,
sem incluir curiosos por simples audição. Python calcula antes de `npc_agency`
escolher; não há decisão definitiva no plano de avaliação nem escolha automática
pela maior nota. Aceitar/recusar exige avaliação atual da versão; contrapropor
ou revisar a própria proposta confere os termos finais da alternativa avaliada.

Oportunidades, contribuições recebidas e decisões iniciadas têm proteção contra
repetição. Ouvir pode ser silencioso, com espera limitada; mudar assunto não
resolve perguntas nem renova a espera. Despedida encerra a conversa preservando
pendências. A fila confere o estado percebido antes de consultar outro NPC.
Objetivo e motivo ficam privados; recusas não iniciam conflito automaticamente.
A integração acrescenta uma decisão limitada por NPC elegível, sem loop,
coordenador alternativo ou alterações de confiança/afeto.

A conferência offline pelo runner e adaptadores com transporte fixo verificou
conversa comum, objetivo central distinto, notas antes da decisão, pergunta
ignorada, argumento irrelevante, recusa sem violência, contraproposta com estrutura
preservada, espera silenciosa limitada, resposta real renovando a espera, off,
fechamento, reinício, privacidade e rejeição de referências/termos indevidos.
Controles adicionais verificaram opinião desatualizada durante resposta pendente,
segundo participante retirado da fila após fechamento percebido e conservação
dos efeitos quando a narração falha. Também foram conferidas a aceitação de
uma solução com outros termos, a revisão da própria oferta conservando herdados
e a rejeição de uma resposta proposta antes do cálculo.

A suíte padrão completa terminou com **1.246 aprovações em 645,12 s**. A seleção
inicial teve 175 aprovações; após ligar o objetivo privado ao id do evento de
decisão nos logs, as 100 regressões pertinentes de agência/Mundo/fronteiras
também passaram. O fluxo com transporte fixo confirmou essa ligação. Contratos
de IA, metadados, 330 links locais, diff e integridade das evidências históricas
conferem. Não houve nova bateria ou chamada paga. A qualidade semântica da
iniciativa de um modelo real permanece para avaliação manual no simulador.

O passo 5 entrega [relações iniciais direcionais](../../../sistema/aplicacao/relacoes-iniciais.md),
com confiança e afeto independentes declarados pelo cenário, privados por dono e
mantidos entre conversas. A escala escolhida é -5..+5, peso 2, R limitado a ±12,
com limiares anteriores preservados. O diretor propõe pertinência por termo;
Python agrupa sinais, calcula a parcela e mantém motivos/fontes. Relações entram
na identidade e validade das opiniões. Não há reciprocidade implícita nem
sentimentos atribuídos ao jogador, atualização por episódios ou save/load.

Fontes ligam memória própria e interesse resumido. Quando uma dimensão contribui
para R, esse mesmo par Claim/interesse não pontua novamente em M; o motivo é
preservado com `counted=false`. Consequência independente em outro interesse
pertinente continua possível, com fundamento próprio. No conselho, confiança
inicial -1 e afeto 0 expressam cautela sem provar autoria dos ataques da trégua.

A conferência pelo runner/adaptadores com transporte fixo aprovou inimigo
confiável, amigo pouco confiável, neutralidade, recusa franca com confiança alta,
privacidade, persistência entre conversas, off e reinício. Controles isolados
conferiram extremos, limite conjunto, compensação, origem, memória com outro id,
consequências independentes e referências inválidas. Também foram conferidos
cache/frescor sensíveis à relação e rejeição de cenários com pares duplicados,
fontes/atores desconhecidos ou sentimentos atribuídos ao jogador.

A seleção inicial teve **114 aprovações**. A execução da suíte padrão aprovou
os primeiros 929 casos e revelou uma incompatibilidade na projeção social do
NPC auxiliar criado depois da sessão pelo teste de orçamento de movimento.
A projeção foi corrigida para selecionar somente perfis registrados, como o
comportamento anterior. Após a correção, **125 regressões pertinentes passaram**,
e os **317 casos restantes da coleção, incluindo a regressão corrigida, passaram
em 142,11 s**. Os 1.246 casos da coleção foram percorridos nesses lotes, sem
repetir a primeira parte da suíte. Contratos de IA, 348 links locais, metadados,
diff e evidências históricas conferem. Não houve nova bateria live ou chamada
paga. A qualidade da pertinência e da resposta de um modelo real continua para
avaliação manual no simulador.

O passo 6 entrega [episódios percebidos e memória entre encontros](../../../sistema/aplicacao/evolucao-das-relacoes.md).
O diretor propõe categoria e evidência própria; código valida dono, autoria,
compromisso aceito e ordem temporal, aplica a política fixa e registra antes/depois.
A implementação escolheu variações pequenas por categoria, mantendo a escala e
os pesos aprovados no passo 5. Suspeita não vira fato confirmado; confirmação e
correção substituem a parcela anterior sem apagar sua história. Repetir evidência
ou renarrar um episódio não reaplica pontos. A recomposição considera a base
inicial e todos os episódios ativos antes do limite.

Fechar o encontro arquiva termos/compromissos e pendências efetivamente percebidos,
sem transcrever toda a conversa ou distribuir objetivos privados. Episódios têm
resumos próprios de inferência, com origem, não compartilháveis automaticamente.
Seleção de conhecimento favorece esses tópicos dentro dos limites existentes.
Resumos não pontuam novamente em M nem comprovam execução. Níveis e memória
persistem na sessão; off não os altera, e reiniciar restaura a base.

A conferência offline pelo runner oficial e adaptadores com transporte fixo
aprovou promessa/aceitação sem pontos, fechamento real de porta observado depois,
cumprimento aplicado uma vez, registro antes/depois, encerramento, retomada em
outra conversa, privacidade, off e reinício. Controles independentes verificaram
suspeita/confirmação/correção, limites, lote inválido, evidência não percebida e
dez cumprimentos sem pontos. As três regressões acrescentadas ao arquivo local
de agência preservam história/correção, recomposição nos extremos e validação
atômica de evidências; as amostras dos contratos preservam cumprimento e arquivos.
Uma regressão de conhecimento distingue ação nova com autoria de observação
passiva repetida, evitando reutilizar a ocasião antiga como prova de cumprimento.
Não houve chamadas externas ou medição de qualidade semântica do modelo.

O recorte observa operações de porta e ataques diretos com dano. Ajuda com custo
exige observação autoral com custo explícito; não foram implementados socorro,
tropas, terras ou transferências. Interpretar o significado da ação ainda cabe
ao diretor. Novos acontecimentos não criam oportunidades automáticas de agência
neste passo; essa coordenação continua no passo 7.

Verificações finais em 19/11/2026: **1.250 testes da suíte local completa aprovados
em 381,18 s**. A seleção complementar de contratos teve **33 aprovações**, e a
auditoria final conferiu a referência revisada. `poetry check`, `git diff --check`,
**369 links locais** e a integridade das evidências históricas, incluindo os logs
locais inventariados, conferem. Nenhuma chamada paga ou nova execução live.

O passo 7 entrega a [reconsideração por acontecimentos percebidos](../../../sistema/aplicacao/acontecimentos-e-prioridades.md).
Aquisições pertinentes aos interesses declarados, ferimentos observados e ruídos
fortes efetivamente ouvidos notificam o dono. `GameFlow` agenda `npc_review`
com perspectiva individual; cálculos precedem nova escolha em `npc_agency`.
Uma notícia feita por outro NPC pode recolocar na fila quem já agiu, sem outra
fala do jogador. Um cálculo já realizado sobre a informação atual dispensa
revisão redundante. Cada NPC tem no máximo uma reconsideração por interação;
recontagens não criam cascata ilimitada de despachos.

Suspender e retomar exige comunicação efetiva; perguntas e propostas permanecem.
Investigar/proteger permite uma operação física suportada, sem deslocamento por
texto, cura inventada ou ataque gratuito. Ruído não identifica agressor ou
ferimento; ver um ferido sem ver a ação conserva observação sem autor atribuído.
Combate interrompe a perspectiva dos participantes sem fabricar fala ou resolver
pendências. Iniciativa e recursos continuam nas regras existentes; confrontos
arbitrários entre terceiros e ataques à distância gerais permanecem fora do recorte.

A composição/runner também expõe `react_to_events()` para continuar após incidente
já executado, sem mensagem falsa do jogador. Sem evento elegível, não despacha.
As regressões locais com transportes fixos cobrem notícia pertinente, irrelevante
e não ouvida, reação depois de já agir, repetição, pausa/retomada, investigação
com deslocamento real, privacidade, off e reinício. Controles parciais executam
ataque real e comparam testemunha, ferido visto sem autor e ruído sem causa
identificada; conferem também interrupção por combate e rejeição fora do turno.
As amostras dos contratos incluem a fase privada nova, fonte verbal, ruído e
estado suspenso. A qualidade da prioridade escolhida por um modelo real não foi
medida e continua para avaliação manual.

Na regressão completa, a preparação de uma situação antiga revelou um ruído
inicial pendente. A conclusão da preparação agora reconhece esses estímulos sem
reapresentá-los, mantendo memórias, percepções e logs. Outra verificação encontrou
falas roteirizadas da dungeon sem marcador verbal; elas passaram a conservar
`speech=True`, sem duplicação como incidente não verbal. O transporte fixo da
regressão offline de agência reconhece a nova fase, sem trocar os critérios do
oráculo ou executar chamadas live.

Verificações finais do passo 7 em 19/11/2026: **1.259 testes da suíte local
completa aprovados em 378,70 s**. A seleção de contratos/agência teve
**61 aprovações** e os cenários com decisões locais fixas tiveram **86 aprovações**,
sem execução live. Auditoria de contextos reproduzível, metadados, diff,
**397 links locais** e integridade das evidências históricas conferem. A declaração
final de `world` na revisão identifica adjudicações vazias e seu produtor próprio;
essa fase não prepara solicitações físicas antes da decisão de agência.

O passo 8 entrega [duas situações casuais](../../../sistema/simulador/conversas-casuais.md),
`conversa-com-amiga` e `encontro-com-garoto`. São dados próprios no pacote, com
preparação e reinício pelo catálogo comum. Um cumprimento real estabelece
participação sem escolher resposta do NPC ou sentimentos do jogador; aguardar
ou conversar permite iniciativa sem pedir cada ação. Nenhum módulo de decisão
é específico para Lia ou Davi.

Escuta aceita acolhimento seguido de espera. Nova fala dirigida ou continuação
da conversa a dois pode renovar a escuta quando não ignora pendência explícita.
Não há renovação por silêncio, off ou conversa a terceiros. Objetivo e foco podem
mudar sem proposta; encerramento conserva história e permite outro encontro.
A seleção de memória própria considera local e comunicações compreendidas,
além do objetivo, preservando os limites anteriores e a privacidade.

O garoto pode oferecer caminho conhecido ou escolher `leave`: despedida e
deslocamento real para destino livre visto em outra área. Sem ficha, destino
percebido ou encerramento comunicado, e sob abordagem pendente, a saída é
rejeitada. A moeda recebida é memória autoral anterior, já incorporada nos níveis;
não foi acrescentada economia ou transferência de valor por fala. A amizade de
Lia é declaração inicial; progressão de amizade/romance continua no passo 9.

Regressões pela composição/runner com decisões fixas conferem escuta em várias
falas, conselho com abertura, pergunta ignorada sem renovação, mudança de foco e
objetivo, fechamento e novo encontro. Também conferem gratidão sem pedido,
orientação após necessidade mencionada, deslocamento efetivo, rejeição antes de
despedida inválida, off, privacidade, reinício e ausência de dados/propostas/bônus
por falas. CLI e agenda sem janela carregam as mesmas situações. A auditoria de
contextos inclui essas operações. Não houve chamada paga ou avaliação semântica
nova de um modelo real.

Verificações finais do passo 8 em 19/11/2026: **1.270 testes da suíte local
completa aprovados em 385,17 s**. Contratos de IA revisados e reproduzíveis,
`poetry check`, `git diff --check`, **413 links locais** e integridade das
evidências históricas, incluindo os logs locais inventariados, conferem.
Nenhum teste live ou chamada paga foi executado.

Ao concluir o passo 8, restava o passo 9, entregue a seguir.

Ao implementar os próximos passos,
registrar o recorte concluído e atualizar as referências canônicas de aplicação,
IA e simulador afetadas. Dados permanecem em `src/trama/scenarios/`, fatos de
avaliação em fixtures ou evidências apropriadas, sem cópias do motor ou de prompts.

Guardar resultados datados em `docs/evidencias/`, incluindo falhas e limites.
O escopo foi concluído e arquivado em
`implementados/2026-11-19-conversacao-contextual`, preservando abaixo os limites
de verificação e os recortes adiados.

## Entrega do passo 9 e conclusão

O passo 9 entrega [vínculos qualitativos](../../../sistema/aplicacao/vinculos-afetivos.md)
direcionais de NPC: amizade, atração, paixão e amor, com estado, motivo, fontes
próprias e história antes/depois. Amizade exige cuidado observado nas duas
direções; os estágios amorosos têm critérios distintos e evidência nova, sem
conversão por pontuação. Manutenção/ruptura preservam a história, sem relógio,
decaimento ou mudanças silenciosas de alinhamento/persona.

Declarações antigas não podem ser reapresentadas por `memory_ids` para contornar
um limite posterior. Memórias autorais com sequência inicial de aquisição também
não contam como acontecimentos posteriores a um vínculo inicial.

Declarações próprias de disponibilidade só existem depois de falas literais
executadas e são aprendidas por quem as compreendeu. Recusa conhecida bloqueia
expressões amorosas tipadas sem apagar sentimentos privados automaticamente.
Romance exige adultos explicitamente declarados. O jogador escolhe suas falas,
sem receber estado afetivo inferido ou reciprocidade imposta.

As [quatro situações](../../../sistema/simulador/vinculos-afetivos.md) usam o mesmo
mapa de Marina, catálogo, preparação, composição e runner. Demonstram amizade
sem atração, história para formação, amor com confiança reduzida e atração própria
de Marina. Neste último caso, a eventual recusa deve ser escolhida e dita pelo
jogador durante o jogo; a situação não a atribui previamente a ele. Lia passa a
ter amizade qualitativa inicial com fontes; o garoto permanece sem romance.

Regressões offline conferem formação, ruptura, cuidado próprio nas duas direções,
recusa mesmo com avaliação favorável, limites não ouvidos, fontes inválidas,
repetição, sequência de novos episódios, privacidade, off e reinício. Os contratos
de IA incluem projeções reais do vínculo e da declaração ouvida; as instruções
e o esquema foram revisados com justificativa explícita.

**Nenhum passo restante neste roadmap.** Julgamento semântico e qualidade do
texto de um modelo real continuam sujeitos a avaliação manual: escolhas fixas
não provam que toda fala será classificada ou respondida adequadamente.
Não houve chamada paga ou nova medição live. Persistência de campanha, relógio
de relações, transformação de persona e novas operações materiais permanecem
fora do escopo entregue, conforme os recortes registrados.

Verificações finais do passo 9 em 19/11/2026: **1.300 testes da suíte local
completa aprovados em 388,29 s**. Dois controles foram acrescentados após o
início dessa execução (memória de declaração antiga e sequência inicial de
aquisição). As seleções finais de vínculos/disposição/agência (84), conhecimento
(39 e 60) e contratos/carregamento/fronteiras (134) passaram; há sobreposição
entre elas, sem somar esses resultados como casos distintos. A coleta atual
contém **1.302 testes locais**. Os ajustes finais foram verificados nas seleções
pertinentes, sem segunda execução da suíte completa.

`tools/context_contracts.py --check`, `poetry check`, `git diff --check`,
**870 links locais** das referências e roadmaps e integridade das evidências
históricas (`--require-local`, 3 arquivos versionados e 40 logs locais) conferem.
Nenhum teste live foi executado ou alterado, e nenhuma chamada paga foi realizada.

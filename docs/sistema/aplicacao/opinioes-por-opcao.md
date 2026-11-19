# Opiniões por opção e por termo

Tier 3 · [Aplicação](README.md) · [Disposição social](disposicao-social.md)

O NPC pode avaliar uma proposta percebida, uma contraproposta ainda cogitada e
a expectativa de não chegar a acordo. Cada nota conserva os termos, motivos,
interesses e memórias que a produziram. O cálculo é determinístico sobre impactos
semânticos propostos pelo diretor. A correção desses impactos continua dependendo
da interpretação da IA.

Este incremento corresponde ao passo 3 do
[roadmap](../../roadmaps/implementados/2026-11-19-conversacao-contextual/plano.md).
Formar opinião não exige teste de Carisma nem determina aceitação, recusa ou
execução dos termos. O [acompanhamento dos NPCs](intencoes-dos-npcs.md) escolhe
a iniciativa depois das notas na mesma interação, como entregue no passo 4.
As [relações iniciais](relacoes-iniciais.md) acrescentam confiança e afeto
pertinentes à opção; o passo 6 permite sua
[evolução por episódios percebidos](evolucao-das-relacoes.md). O passo 9 acrescenta
[vínculos qualitativos](vinculos-afetivos.md) à base privada, sem bônus numérico
ou obrigação de corresponder.

## Opções e referências percebidas

`opinions.OptionAssessment` contém dono, conversa, descrição, tipo e avaliações
dos termos. Há três tipos:

| Tipo | Origem e significado |
| --- | --- |
| `proposal` | Uma proposta e versão inteiramente conhecidas pelo NPC, com todos os termos avaliados uma vez. |
| `alternative` | Contraproposta hipotética privada, vinculada a uma proposta e versão conhecidas. Só vira oferta quando os termos forem falados e registrados. |
| `no_agreement` | Consequências esperadas pelo NPC, com rótulo privado `option_id`; não são fatos novos nem previsão verdadeira do futuro. |

`ConversationState.opinion_basis` consulta o registro completo, independentemente
do recorte enviado à IA, e rejeita conversas, propostas, versões ou termos não
percebidos. `conversation_id='latest'` seleciona a última conversa percebida;
`proposal_id='latest'` seleciona a proposta cuja versão percebida é mais recente
nessa conversa. `version=null` usa a última versão conhecida dessa proposta.
Versões históricas continuam avaliáveis, com seus próprios números.

Para `proposal`, cada `TermAssessment` referencia o id e o texto literal de um
termo da versão. `at:1` até `at:8` são referências posicionais à lista completa
de termos, úteis quando a fala ainda será executada. Após resolver os aliases,
o conjunto deve conter todos os ids exatamente uma vez. O registro conserva
também tipo, responsável e ordem explícita dos termos em `proposal_terms`.
Alternativas e expectativas usam ids locais e descrições privadas. Para
materializar uma alternativa como contraproposta, cada termo informa também
`kind`, `actor_id` e `execution_order`. O código confere esses campos e o texto
contra a oferta executada; `order` continua representando o impacto no alinhamento.
Na avaliação de proposta real, a estrutura é preenchida a partir da versão conhecida.
Registros locais antigos sem estrutura hipotética continuam legíveis, mas não
autorizam publicar uma alternativa incompletamente descrita.

## Base e compensação dos efeitos

A fórmula base `S_base = A + P + M`, pesos e limites são **política do Trama**, não uma
regra oficial de D&D. As referências de edição e o tratamento dos pedidos reais
de Influence permanecem em [disposição social](disposicao-social.md).

Cada termo recebe impactos de ordem e moralidade de -1 a +1, justificativa de
alinhamento, uma avaliação por interesse da persona e até seis vínculos
`Claim/interest_id` com memórias próprias. Impactos neutros também têm motivo.
Referências e âncoras são validadas antes de registrar o lote de opiniões.

Na base da opção, o código calcula:

1. **A:** soma os impactos dos termos em cada eixo, limita cada soma a ±1 e
   multiplica pelos eixos do alinhamento. O total fica entre -2 e +2.
2. **P:** soma os impactos dos termos por interesse, limita cada resultado a ±1
   e multiplica pelo peso do interesse, de 1 a 4. A soma final fica entre -6 e +6.
3. **M:** agrupa por `Claim` exata entre todos os termos e interesses. Soma os
   sinais, limita a ±1 e aplica peso 2 para observação/hábito ou 1 para
   relato/inferência. Usa a memória ativa de aquisição mais recente dessa Claim,
   como o cálculo anterior. A soma final fica entre -3 e +3.

A opção completa soma também R, calculada a partir das
[relações direcionais](relacoes-iniciais.md): escala -5..+5, peso 2 e limite
conjunto ±12. `relationship_effects` por termo descreve pertinência por destinatário
e dimensão; níveis e fontes vêm do cenário. Aspectos de memória já resumidos por
uma relação efetivamente usada são conservados com `counted=false` e não
pontuam novamente em M. A base relacional entra no cache e na validade da nota.

Assim, uma memória citada em vários termos não multiplica a força do mesmo fato.
Efeitos opostos se compensam; todos os motivos favoráveis, contrários e neutros
permanecem inspecionáveis. As avaliações isoladas dos termos são diagnósticos:
seus totais não devem ser somados, pois os limites e a compensação valem para
a opção inteira. `raw` registra valores anteriores aos limites globais.

`inclination` é `favorable` a partir de 3, `unfavorable` até -3 e `mixed` entre
esses limites. São orientações sobre a opção, sem registrar uma decisão pública.
Um resultado favorável não cria concessão nem determina sucesso de Influence.

Por exemplo, com impactos fixos para o conselho, o interesse na população pode
contribuir +4, a devolução territorial -3 e a falta de garantia -3. A memória da
trégua rompida acrescenta -2: a oferta fica em -4. Trocar a retirada unilateral
por simultânea pode mudar a garantia para +3 e o efeito da memória para zero,
resultando em +4. O motivo territorial de -3 permanece. Esses valores ilustram
classificações explícitas, sem fixar respostas do general ou provar a validade
histórica das suas crenças.

## Execução e privacidade

`WorldReaction.opinions` aceita até quatro avaliações após `speak`/`challenge`
executado no modo narrado, com `after_squares=null` e `check=null`. O NPC precisa
estar consciente e ter ouvido a fala atual. A avaliação usa somente suas
memórias ativas e as versões que conhece. Etapa não alcançada, fala inválida ou
mensagem exclusivamente off não cria opinião. `npc_turn` e `npc_agency` não
recebem novas avaliações neste recorte.

Uma reação pode ter `actions=[]` se contiver opiniões. O lote é validado antes
da gravação de qualquer opinião; falha na validação preserva a fala que já foi
executada e impede as ações seguintes dessa reação. Não há chamada adicional
ao provedor, dado, comunicação, memória, movimentação de tropas ou transferência
territorial. Ações `say` continuam obedecendo ao contrato da conversa.

O teto padrão da resposta do Mundo passa de 2.000 para 6.000 tokens para comportar
as avaliações estruturadas e seus motivos na mesma resposta. Continua sendo um
limite de saída, sem reservar esse consumo em toda interação; configurações
explícitas de `ResponseOptions` mantêm o limite escolhido pelo chamador. Respostas
mais longas podem consumir mais tokens. Veja a [configuração da integração](../ia/integracao-openai.md).

`DispositionSystem` guarda o histórico na sessão e publica as avaliações em
`world.social.opinions`. O diretor deve usar somente as avaliações do dono que
está decidindo. Cada avaliação recebe um `id` próprio, inclusive ao reutilizar
cache. `current` distingue bases ainda aplicáveis de histórico: perfil/crenças
relevantes alterados, versão de base revisada, retirada percebida ou conversa
inativa impedem uma nova decisão apoiada naquela avaliação. `basis_key` identifica
a base de perfil/crenças. `proposer_id` identifica o autor da proposta de base.
A fase individual `npc_agency` recebe `opinions` do próprio ator, com validação
de dono e uma oportunidade limitada de acompanhamento.
Interpretação e narração não recebem essas avaliações. Os números e motivos
ficam nos contextos autorizados e nos logs, sem painel novo no simulador.

O contexto leva as últimas quatro avaliações por NPC, removendo as agregações
que duplicam os motivos por termo. Ao exceder 24.000 caracteres JSON, descarta
as avaliações mais antigas até restar uma ou caber nesse alvo. Uma avaliação
individual maior permanece inteira. O histórico completo fica em processo e
nos eventos `social.option_evaluated`; reiniciar apaga estado e cache em memória.

## Equivalência e reavaliação

O cache de opiniões é separado do cache de pedidos Influence, que permanece
com seu contrato anterior. Para propostas, equivalência exige mesma conversa,
dono, autor da proposta, sequência de textos com espaços normalizados, tipos,
responsáveis e ordem, além do mesmo perfil e base relevante de crenças ativas. Os ids de termos e o
número da versão não tornam conteúdo idêntico uma opção nova. Na reutilização,
as referências são ligadas aos ids da proposta atual e os motivos anteriores
são preservados. `fingerprint` e `reused` identificam esse caminho nos logs.

A assinatura das crenças mantém Claim exata, tipo/dono da fonte e âncoras de
assunto; registra também qual origem é a mais recente por Claim. Repetir o mesmo
relato da mesma fonte não acrescenta peso. Nova evidência relevante, alteração
de perfil ou mudança dos termos permite recalcular. Não há reconhecimento
automático de sinônimos, paráfrases ou equivalência entre promessas diferentes.
Alternativas e expectativas mantêm seus rótulos/termos privados; alternativas
incluem ainda a proposta de base na identidade.

Uma revisão é avaliada como nova opção completa, preservando no histórico a
avaliação anterior. Termos herdados precisam continuar explicitamente avaliados;
o código não adivinha quais impactos semânticos de outra cláusula mudaram.
Notas antigas conservam a versão e a origem usadas, sem serem reescritas como
avaliações atuais após um fato novo.

## Verificação local

As regressões existentes de disposição, Mundo, agência e contratos continuam
independentes de rede. `tools/context_contracts.py` constrói ofertas e avaliações
reais pelo motor para auditar esquema, contextos e privacidade com
`poetry run python tools/context_contracts.py --check`.

A conferência offline pelo `game.runner`, com transporte fixo, verifica oferta
unilateral, alternativa simultânea, expectativa sem acordo, revisão mantendo
território, repetição sem dado, referências inválidas, compensação, privacidade,
falha de narração e reinício. Ela verifica a execução dos impactos fornecidos;
a qualidade da conversa com modelo real fica para a avaliação manual no
[conselho dos generais](../simulador/conselho-dos-generais.md).

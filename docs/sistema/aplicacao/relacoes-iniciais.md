# Relações iniciais e peso nas opções

Tier 3 · [Aplicação](README.md) · [Opiniões por opção](opinioes-por-opcao.md)

Confiança e afeto são dimensões independentes de uma relação direcional entre
um NPC e outro personagem da cena. General → jogador não implica jogador →
general. Os valores são declarados pelo autor do cenário e persistem entre
conversas da mesma sessão. Reiniciar restaura os valores iniciais.

O passo 5 acrescenta `R` em `S_opcao = A + P + M + R`. A escala e os pesos abaixo
foram escolhidos pelo usuário em 19/11/2026; são política do Trama, sem fórmula
oficial de D&D. A [evolução por episódios](evolucao-das-relacoes.md) foi acrescentada
no passo 6. O passo 9 acrescenta [vínculos qualitativos](vinculos-afetivos.md)
com critérios próprios, sem pontos novos. Save/load de campanha permanece fora
do recorte.

## Dados e direção

`relationships.py` contém `RelationshipDimension`, `Relationship`,
`RelationshipEvidence`, `RelationshipEffect` e `RelationshipState`. Os cenários
declaram a lista `relationships` dentro de cada NPC em `creatures` ou `observers`.
Cada item dessa lista tem o formato:

```json
{
  "target_id": "player",
  "trust": {
    "value": -1,
    "reason": "Cautela perante um interlocutor sem histórico pessoal verificável.",
    "sources": []
  },
  "affection": {
    "value": 0,
    "reason": "Nenhum vínculo afetivo pessoal estabelecido.",
    "sources": []
  }
}
```

Cada par tem confiança (`trust`) e afeto (`affection`), com valor inteiro de -5
a +5, motivo obrigatório e até oito fontes iniciais opcionais por dimensão. O dono vem do
NPC que declara o registro; destinatário deve ser outro personagem da cena.
Pares duplicados, referências desconhecidas, autorreferência, valores booleanos
ou fora da escala são rejeitados. O carregador geral e a dungeon usam o mesmo
contrato. Não se declaram sentimentos em `player.relationships`.

Ausência de registro é neutralidade, com as duas dimensões em zero e
`declared=false` ao consultar o par. Não se cria a relação inversa. A base fica
na sessão em `GameSession.relationships`, com registros individuais imutáveis e
projeções próprias por dono. O passo 6 substitui registros ao validar episódios;
a base inicial continua disponível para reinício e recomposição dos níveis.

No conselho, o general começa com confiança -1 e afeto 0 para o jogador. Auren
reconheceu que suas tropas violaram a trégua; o jogador assumiu depois e não
participou do ataque. A cautela diante do representante desse reino distingue
responsabilidade institucional de participação pessoal. Não há vínculo afetivo
pessoal declarado. Esses valores iniciais não transformam alinhamento ou atitude de
Influence e não atribuem sentimentos ao personagem do jogador.

## Pertinência por termo e cálculo

`TermAssessment.relationship_effects` contém destinatário, dimensão, impacto
de -1 a +1 e motivo contextual. A IA propõe pertinência, sem informar níveis ou
pesos. Cada par destinatário/dimensão aparece no máximo uma vez por termo,
com até oito impactos por termo. Registros locais anteriores podem omitir a
lista; uma lista vazia não acrescenta R.

| Dimensão | Impacto +1 | Impacto -1 | Impacto 0 |
| --- | --- | --- | --- |
| Confiança | O termo depende da confiabilidade/promessa do destinatário. | Há benefício explícito em evitar essa dependência. | O termo independe desse vínculo. |
| Afeto | O termo beneficia o destinatário. | O termo prejudica o destinatário. | Não há consequência afetiva pertinente. |

Assim, inimigo confiável pode ter promessa bem avaliada e proposta em seu
benefício mal avaliada. Amigo pouco confiável pode receber cuidado e ainda
precisar de garantias. A interpretação dessas consequências continua semântica;
o código verifica referências, níveis, sinais, agrupamento e limites.

O cálculo agrupa impactos por destinatário/dimensão entre todos os termos. Soma
os sinais, limita o resultado a ±1 e multiplica pelo nível da dimensão e por
**peso 2**. Cada dimensão pode contribuir até ±10. Soma todas as contribuições e
limita a parcela conjunta **R a ±12 uma única vez por opção**. Repetir a mesma
promessa em vários termos não multiplica sua força. Sinais contrários podem se
compensar, preservando os motivos individuais nos registros.

`components.relationships` contém R; `raw.relationships` conserva o valor antes
do limite conjunto. `relationship_effects` no resultado registra dono,
destinatário, dimensão, nível, peso, origem, fontes, impactos por termo e saldo.
Os demais componentes conservam seus limites: A ±2, P ±6 e M ±3. O total pode
ficar entre -23 e +23; os limiares de orientação permanecem ±3. Com níveis
neutros ou sem pertinência relacional, o comportamento da base é preservado.

A maior contribuição pode vir de vínculos extremos, sem forçar aceitação.
O [acompanhamento](intencoes-dos-npcs.md) decide após o cálculo, usando objetivo,
riscos e motivos. Confiança alta pode justificar uma recusa franca. Este recorte
não altera CDs, dados, concessões ou o cache de pedidos Influence.

## Fontes e memória sem pontuação duplicada

Uma fonte opcional declara `memory_id` completo e `interest_id` do aspecto que
a dimensão resume. O carregador resolve Claim e origem da memória real do dono,
valida o interesse e suas âncoras e guarda esses dados em `RelationshipEvidence`.
Uma relação pode ter origem apenas na configuração inicial do autor, com motivo
e lista de fontes vazia; isso não fabrica memória ou prova sobre o destinatário.

Quando uma dimensão contribui para R com nível e impacto agregado não zero,
o mesmo par **Claim exata/interesse** de suas fontes deixa de pontuar em M.
O impacto da memória continua no relatório, com motivo, origem, `counted=false`
e `relationship_sources`. Outro id de memória com a mesma Claim não contorna
a deduplicação. A memória não é apagada, alterada ou transformada em verdade.

Uma consequência independente pode pontuar outro interesse pertinente, com
motivo próprio. A soma de memória ainda é limitada por Claim e pelos limites
anteriores. Se o nível é zero ou impactos da dimensão se compensam, ela não
contribui e suas fontes não suprimem M: neutralidade preserva a base.
O código não identifica equivalência linguística entre episódios; o autor e o
diretor precisam declarar fontes e consequências sem reclassificar o mesmo
aspecto apenas para acumular bônus. Novas consequências precisam de fundamento.

## Privacidade e validade das avaliações

`world.social.relationships` fornece registros por dono ao diretor do Mundo.
Na fase individual, `relationships` contém somente as relações do NPC solicitado,
com validação de dono. Interpretação e narração não recebem níveis, fontes ou
motivos privados. A narração apresenta somente falas e efeitos executados.

Relações também integram `basis_key`, a identidade do cache e a verificação de
`current` das opiniões. Uma base relacional diferente invalida uma referência
antiga, sem escolher ou reavaliar automaticamente. Repetir a proposta com a mesma
base reutiliza a avaliação e seus motivos. O modelo não pode alterar a relação
propondo outro impacto semântico para obter uma nota diferente em repetição.

Promessas, elogios, aceitação e encerramento não dão pontos. O passo 6 permite
que uma acusação conhecida gere suspeita, sem comprovar traição. A relação muda
somente pela [política de episódios validados](evolucao-das-relacoes.md), sem
pontos por quantidade de falas, reciprocidade inferida ou sentimentos impostos
ao jogador. Fontes dinâmicas podem resumir o episódio inteiro, sem interesse
específico; o contrato e a deduplicação desse caso estão nessa referência.

## Verificação e avaliação manual

As amostras de `tools/context_contracts.py` incluem pertinência de confiança,
neutralidade afetiva e exclusão de memória já resumida na relação. A conferência
offline pelo runner e adaptadores com transporte fixo cobre inimigo confiável,
amigo pouco confiável, neutralidade, recusa franca, privacidade, novas conversas,
off e reinício. Controles isolados verificam extremos, limites, compensação,
origens, aliases de memória e consequências independentes. Não há medição nova
da qualidade semântica de um modelo real.

No [conselho](../simulador/conselho-dos-generais.md), compare uma promessa que
depende do interlocutor com retirada verificável independentemente dele. Confira
nos logs `social.option_evaluated` R, fontes, motivos e eventuais impactos de
memória marcados como já contabilizados. Para comparar outros vínculos, declare
os valores na cópia do cenário antes de carregá-la; não há controle de edição
dos sentimentos ou painel de pontuações na conversa do jogador.

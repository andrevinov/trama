# Live tests de disposição social

Tier 3 · [Qualidade](README.md)

## Escopo e critérios

`tests/live/test_social_disposition_live.py` usa `open_situation`, a composição
padrão e `game.runner.submit`: interpretação, Mundo, regras e narração reais.
A preparação compartilhada `social_challenge` oferece a abordagem sem IA. O
corredor genérico mantém jogador em [3,3] e guarda em [11,3], a 12 m audíveis.
Não é uma partida inteira desde a dungeon nem valida a interpretação da preparação.

As sete situações `disposicao-*` são jogáveis por `--situation ID`. Perfis e
memórias passam pelo carregador; mensagens e expectativas ficam em
`tests/fixtures/social/cases.json`. Nenhuma resposta ou contexto da IA é fabricado.

| Caso | Expectativa independente |
| --- | --- |
| Persuasão corrigida | O pedido original concede somente escuta, sem liberdade, movimento, itens ou combate. Disposto dispensa dado; hesitante resolve Persuasão. |
| Compassivo | Disposto a ouvir sem violência, sem rolagem. |
| Sádico | Indisposto a conceder a pausa pedida, sem dado nem ataque automático. Sadismo pertence à persona explícita, não decorre obrigatoriamente do alinhamento. |
| Corrupto | Hesita sem incentivo e falha com d20=1; recompensa nova torna-o disposto a ouvir; repetir a recompensa reutiliza a decisão. Não existe transferência de dinheiro. |
| Ordeiro / caótico | Mesmo pedido formal, mesma persona: contribuição de alinhamento +1 / -1; disposto / hesitante. |
| Memória | Reformular e falar da roupa azul reutilizam decisão. Nova alegação de nobreza conta como relato não confirmado relevante e permite reavaliação. |

Verificações observam estado, eventos, decomposição dos fatores, dado quando
hesitante, fontes reais das memórias, resposta condicional escolhida pelo código
e ausência de iniciativa, dano, deslocamento, portas abertas ou itens concedidos.
Não calculam o esperado chamando novamente a implementação avaliada. Revisão
humana da prosa salva confere fidelidade à concessão, limites e fontes; narração
não vazia não certifica coerência semântica.

## Orçamento e execução autorizada

Uma tentativa por caso: **sete casos, 12 mensagens, 36 chamadas normais e teto
de 48 chamadas lógicas ao SDK** (até uma correção por mensagem). O teto é de
chamadas, não monetário; configuração efetiva e consumo ficam nos artefatos.
Não repetir até passar. Falhas e casos não concluídos permanecem registrados.
O jogador autorizou executar apenas estes testes novos neste incremento.

Revisão de 17/11: a primeira bateria consumiu 21 chamadas e interrompeu os sete
casos por exigir `target_id=player` em pedidos de escuta. O contrato dizia apenas
“alvo conhecido”; indicar `guard_1`, o destinatário, também é válido. A correção
aceita as duas referências e unifica a chave de reutilização de `listen`. Os
registros originais são preservados. Uma única execução corretiva dos dois casos
multimensagem usa teto de 26 chamadas (11 corrupto + 15 memória), com
`TRAMA_SOCIAL_CALLS_RESERVED=1`; total das duas baterias limitado a 47. Os cinco
casos de uma mensagem são reavaliados offline, sem novas chamadas. Isso corrige
um critério indevido; não converte o resultado original do pytest em aprovação.

A revisão multimensagem consumiu 15 chamadas: corrupto interrompido após oferta
porque a promessa não entrou em Claims; memória interrompida na informação
irrelevante porque o critério exigia evento de avaliação mesmo sem mudança.
O contrato passou a registrar promessas declaradas e exigir vínculo da Claim
nova no julgamento. O critério permite manter a decisão sem uma nova avaliação.
Após essas correções, a última execução somente de corrupto usou teto de nove
chamadas (`TRAMA_SOCIAL_CALLS_RESERVED=3`), total acumulado máximo de **45**.
Não foram feitas outras repetições. A sequência completa de nobreza continua
sem medição live concluída; testes locais cobrem a reavaliação.

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_social_disposition_live.py -m live -v
```

Exige `OPENAI_API_KEY`, usa modelo padrão ou `TRAMA_OPENAI_MODEL` conforme a
composição. `logs/live/social/<data-id>/<caso>/` guarda `trace.jsonl` e `result.json`,
incluindo falhas, configuração, entradas, contexto/resposta, relatório, estados,
rolagens e tokens. `TRAMA_SOCIAL_ARTIFACTS` altera a raiz. Resultados recebem
registro datado próprio; evidências anteriores não são atualizadas.

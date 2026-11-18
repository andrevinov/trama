# Inspeção de passagens: live tests

Tier 3 · [Qualidade](README.md) · [Visão geral](../../../README.md)

## Objetivo e fluxo

Quatro casos novos de `tests/live/test_passage_inspection_live.py`, pelo fluxo
oficial `open_situation` → `game.runner.submit`. Usam configuração, interpretador,
Mundo, narração e contratos da aplicação, sem janela ou resposta substituta.
Preparação determinística não avalia a interpretação do percurso anterior.
As situações também são abertas na janela por `--situation ID`.

| Situação | Entrada e critério |
| --- | --- |
| `inspecao-cela4-silenciosa` | Frase exata da regressão, junto da grade fechada/destrancada. Furtividade 17 permanece; aprende `locked=false`, não abre, não entra nem coleta. |
| `inspecao-porta-trancada` | Porta genérica fechada/trancada, conferência cuidadosa e silenciosa. Aprende `locked=true`, sem abrir/destrancar nem perder Furtividade 17. |
| `inspecao-visual-distante` | Apenas olhar de longe, sem aproximação/toque. Estado físico e conhecimento permanecem iguais; `locked=null`. |
| `inspecao-alvo-indefinido` | Ainda não decidiu qual das várias grades conferir. Esclarecimento, somente interpretador/narrador; nenhum Mundo, som, teste, descoberta ou alteração de estado. |

A preparação de Hide usa d20 natural 16 + Furtividade 1 = 17. Todos os dados da
preparação devem ser consumidos; a interação medida não pode consumir novos.
A dungeon usa guarda atrás da porta fechada; o segundo caso usa o mapa genérico
de percepção. Não se atribui estado privado durante o live.

Frases, oráculos e tetos estão em
[`cases.json`](../../../tests/fixtures/passage_inspection/cases.json).
[`regression_source.json`](../../../tests/fixtures/passage_inspection/regression_source.json)
preserva cinco eventos selecionados da sessão original, com caminho, linhas e
hashes dos bytes de origem. O histórico dessa sessão não é injetado no modelo.

## Critérios e revisão narrativa

Cada caso verifica estado antes/depois, posição, passagens, inventário, recursos,
iniciativa, furtividade, eventos, plano executado e fatos enviados à narração.
Não pode haver teste, abertura, destrancamento, combate ou resposta de NPC nas
condições isoladas desses casos. Olhar não revela o trancamento secreto; uma
conferência física não vira investigação ou tentativa de abrir. O pedido de
esclarecimento não pode consultar o Mundo.

Os testes offline de preparação/oráculos têm controles negativos: movimento,
abertura, trancamento informado errado e chamada ao Mundo no esclarecimento
reprovam. Os critérios de estado não certificam toda prosa: a evidência guarda
a resposta para revisão humana de revelação de segredo, alegação incorreta de
ação não suportada, movimento, abertura ou teste inventados. Texto não vazio não
é evidência de coerência narrativa.

## Execução e orçamento

**Quatro casos aprovados na execução autorizada de 17/11/2026, com 11 chamadas.**
Veja o [relatório e os limites](../../evidencias/2026-11-17-inspecao-passagens/relatorio.md).
Criar os testes não autoriza executá-los. Uma bateria autorizada tem uma tentativa
por caso: 11 chamadas normais, teto de **15 chamadas do SDK**, incluindo correções
do interpretador (4 + 4 + 4 + 3). Não inclui narração de abertura nem outras suítes.
O limite de chamadas é imposto antes do SDK; não é teto monetário.

Após autorização explícita, com `OPENAI_API_KEY` configurada:

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_passage_inspection_live.py -m live -v
```

Coleta sem rede:

```bash
poetry run pytest tests/live/test_passage_inspection_live.py --collect-only -q
```

Respeita `TRAMA_OPENAI_MODEL` e a composição normal. Artefatos persistem em
`logs/live/passage_inspection/<execução>/<caso>/trace.jsonl` e `result.json`;
`TRAMA_INSPECTION_ARTIFACTS` altera apenas a pasta. Configuração efetiva, cenário,
mensagem, IDs, contextos/pedidos/respostas, relatório, antes/depois, dados,
orçamento, tokens e erros são preservados, inclusive em falhas, sem repetir até
passar. Limitações de serviço, teto ou decisão pendente reprovam a execução.

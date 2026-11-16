# Análise parcial de interpretação

Tier 3 · [Qualidade](README.md) · [Visão geral](../../../README.md)

A criação do cliente e dos adaptadores usa a
[composição compartilhada](../ia/integracao-openai.md). Cada variante
registra `configuration`, incluindo timeout/retries, parâmetros por fase e
diferenças do padrão, identificada como `interpretation_comparison`.
As instruções, os critérios e os 15 casos foram preservados na migração.
O código reutilizável está em [analysis/interpretation.py](../../../src/trama/analysis/interpretation.py);
a [ferramenta auxiliar](../../../tools/analyze_interpretation.py) apenas fornece
os caminhos padrão do cenário e dos casos. Os testes importam o módulo
diretamente, sem executar scripts em `pocs/`.

## Objetivo e escopo

Medir se a IA preserva a intenção do Jogador, comparando contexto mínimo e
completo e a ordem das propriedades do esquema. [`cases.json`](../../../tests/fixtures/interpretation/cases.json) contém 15 casos: cinco pedidos reais que falharam,
observação, poder explícito, negação, pergunta, citação, discurso relatado,
condição, movimento com porta, fala off e distância métrica.

O experimento chama somente o interpretador. Não executa planos, não rola dados,
não consome recursos e não consulta o Mundo nem o narrador. Cada caso parte do
mesmo contexto inicial de Cela/Sala dos Guardas, sem depender dos anteriores.
O campo `scope=interpreter_contract` identifica esse limite nas prévias,
resultados e metadados. O único simulador jogável continua sendo `trama-simulator`.

## Entradas e dependências

`scenario_context(caminho)` usa `application.scenarios.load_session` e a projeção
`session.interpreter_context`. Esta é a entrada parcial do experimento anterior:
não inclui a preparação e a coordenação completa de `Conversation`/`GameFlow`.
Os testes de partida seguem usando `open_situation` e `game.runner`.

`run_case` chama o adaptador por `open_services`, preservando as variantes
explicitamente nomeadas de contexto, esquema e correção. `evaluate_plan` compara
o retorno com expectativas externas; planos de referência das fixtures não são
enviados ao modelo nem usados como substitutos de uma falha.

O módulo não conhece caminhos do repositório. A ferramenta em `tools/` fornece
como padrão os casos de `tests/fixtures/interpretation/` e o mapa legado em
`tests/fixtures/scenarios/`. `--cases` e `--scenario` permitem dados explícitos,
sempre pelos mesmos validadores. A saída padrão é `logs/interpretacao/` no
diretório de trabalho. Nenhuma regra depende desse módulo de análise.

## Preparação e prévia offline

Na raiz, com o ambiente Poetry instalado:

```bash
poetry run python tools/analyze_interpretation.py
poetry run python tools/analyze_interpretation.py --case real_4
```

Sem `--live`, apenas lista os casos e o limite de chamadas caso fossem executados.
Não cria cliente OpenAI, mesmo com chave e autorização no ambiente.

## Execução real opcional

Exporte `OPENAI_API_KEY`. Chamadas reais exigem também `RUN_OPENAI_LIVE_TESTS=1`
e `--live` e são potencialmente pagas:

```bash
# Dois casos, dois contextos: quatro chamadas, sem correções.
RUN_OPENAI_LIVE_TESTS=1 poetry run python tools/analyze_interpretation.py --live --case real_4 --case negated_power

# Todos os casos, três repetições: 15 × 2 × 3 = 90 chamadas.
RUN_OPENAI_LIVE_TESTS=1 poetry run python tools/analyze_interpretation.py --live --repeat 3

# Avaliar a recuperação usada no jogo: no máximo quatro chamadas.
RUN_OPENAI_LIVE_TESTS=1 poetry run python tools/analyze_interpretation.py --live --case real_4 --max-corrections 1

# Isolar a ordem das chaves: três pedidos × dois esquemas = seis chamadas.
RUN_OPENAI_LIVE_TESTS=1 poetry run python tools/analyze_interpretation.py --live --case real_5_terra --case look --case second_wind --context minimal --schema-order both
```

O padrão mede a primeira resposta, com `--max-corrections 0`. Outras opções:
`--context minimal|full|both`, `--schema-order operation-first|legacy|both`, `--model NOME`, `--case ID` repetível,
`--repeat 1..20` e `--output CAMINHO_NOVO`. O modelo padrão vem de
`TRAMA_OPENAI_MODEL`, com fallback para `gpt-5.6-terra`.

## Comparação e resultados

As variantes usam o mesmo pedido, modelo, instruções, raciocínio `low` e limite
de 1000 tokens. Para comparar contexto, mantenha uma única ordem de esquema.
Para comparar a ordem, use `--context minimal --schema-order both`: só a ordem
das propriedades difere, sem mudar tipos, campos obrigatórios, enums ou limites.
A ordem das variantes é alternada nas repetições. O contexto mínimo preserva posição, unidades,
referências aos lugares/passagens, criaturas visíveis, modo, catálogo resumido
e histórico on recente; o completo inclui fichas, NPCs ocultos e geometria.

Os arquivos são gravados numa pasta nova em `logs/interpretacao/`:

- `results.jsonl`: contexto, `schema_order`, pedido, expectativa, respostas originais, candidatos, plano
  retornado, acerto inicial/final, rejeição, erro, chamadas, duração e tamanho de entrada.
- `summary.json`: contagens de acertos, chamadas e tokens, agrupadas por contexto
  e depois por ordem do esquema.
- `metadata.json`: modelo solicitado, versão do SDK, host, ordens comparadas e parâmetros. O host
  não inclui credenciais, caminho nem query da URL.
- `trace.jsonl`: prompts, respostas e correções correlacionadas. `response_model`
  registra o modelo reportado pelo provedor, quando disponível.

Tokens ausentes ficam `null`; não são estimados como zero. Não há estimativa de
preço. `lnav CAMINHO/trace.jsonl` usa o formato do Trama já instalado. A leitura
das evidências considera os arquivos rotacionados; o resultado individual
conserva respostas originais e consumo informado por chamada.

## Ordem das propriedades

A aplicação usa `operation-first`; `legacy` é controle experimental.
Veja a [interpretação atual](../ia/interpretacao-do-jogador.md)
e o [registro histórico de 15/11/2026](../../evidencias/2026-11-15-ordem-esquema/relatorio.md),
medido com contrato anterior. Não se infere sucesso do contrato atual dessa comparação.

## Critérios de sucesso e simplificações

O avaliador compara operações e, quando indicado, destino, alvo, Dash e distância
com expectativas escritas nos casos. Não usa outra IA nem usa a autorização
como oráculo de acerto. JSON válido que converta caminhada em `look` ou
`second_wind` é erro de interpretação. Com correção habilitada, acertos inicial
e final são registrados separadamente.

Uma resposta pode ser semanticamente incorreta mesmo com metadados coerentes.
Aprovar estes casos não garante qualquer frase ou atualização do modelo.
A IA interpreta a linguagem e retorna request_parts com trechos e classificações.
A validação é declarativa, sem lista de verbos: verifica origens, cobertura das
etapas e referências. A equivalência semântica é avaliada pelas expectativas dos
casos, não pelo validador. Veja [o contrato e suas limitações](../aplicacao/planos-e-validacao.md).
Uma pergunta pode produzir zero etapas; posturas são detalhes narrativos sem custo.
As regressões locais das frases de combate ficam em tests/integration/test_semantic_interpretation.py;
os casos reais opcionais estão em tests/live/test_semantic_interpretation.py.

## Testes

```bash
# Sem rede, com respostas simuladas.
poetry run pytest tests/unit/test_authorization.py tests/integration/test_interpretation_authorization.py tests/integration/test_interpretation_experiment.py

# Opcional e pago: seis chamadas, três casos × dois contextos, sem correções.
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_interpretation_experiment.py -m live -v

# Opcional e pago: seis chamadas de comparação das ordens, sem efeitos no jogo.
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_schema_order.py -m live -v
```

Os testes live salvam `result.json` e `trace.jsonl` no diretório temporário do
pytest, inclusive quando a interpretação falha. A suíte padrão não executa esses testes.

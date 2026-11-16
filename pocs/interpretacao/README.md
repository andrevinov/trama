# Interpretação de pedidos e autorização

## Objetivo e escopo

Medir se a IA preserva a intenção do Jogador, comparando contexto mínimo e
completo e a ordem das propriedades do esquema. `cases.json` contém 15 casos: cinco pedidos reais que falharam,
observação, poder explícito, negação, pergunta, citação, discurso relatado,
condição, movimento com porta, fala off e distância métrica.

O experimento chama somente o interpretador. Não executa planos, não rola dados,
não consome recursos e não consulta o Mundo nem o narrador. Cada caso parte do
mesmo contexto inicial de Cela/Sala dos Guardas, sem depender dos anteriores.

## Preparação e prévia offline

Na raiz, com o ambiente Poetry instalado:

```bash
poetry run python pocs/interpretacao/run.py
poetry run python pocs/interpretacao/run.py --case real_4
```

Sem `--live`, apenas lista os casos e o limite de chamadas caso fossem executados.
Não cria cliente OpenAI, mesmo com chave e autorização no ambiente.

## Execução real opcional

Exporte `OPENAI_API_KEY`. Chamadas reais exigem também `RUN_OPENAI_LIVE_TESTS=1`
e `--live` e são potencialmente pagas:

```bash
# Dois casos, dois contextos: quatro chamadas, sem correções.
RUN_OPENAI_LIVE_TESTS=1 poetry run python pocs/interpretacao/run.py --live --case real_4 --case negated_power

# Todos os casos, três repetições: 15 × 2 × 3 = 90 chamadas.
RUN_OPENAI_LIVE_TESTS=1 poetry run python pocs/interpretacao/run.py --live --repeat 3

# Avaliar a recuperação usada no jogo: no máximo quatro chamadas.
RUN_OPENAI_LIVE_TESTS=1 poetry run python pocs/interpretacao/run.py --live --case real_4 --max-corrections 1

# Isolar a ordem das chaves: três pedidos × dois esquemas = seis chamadas.
RUN_OPENAI_LIVE_TESTS=1 poetry run python pocs/interpretacao/run.py --live --case real_5_terra --case look --case second_wind --context minimal --schema-order both
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

O jogo usa `operation-first`: todas as variantes de ação começam por `operation`.
O formato antigo de movimento/portas começava por `segments`; os demais, por
`operation`. A documentação de [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs#key-ordering)
informa que a saída segue a ordem das chaves do esquema. O formato `legacy` é
mantido somente para controle no experimento; o jogo não alterna entre eles.

Na comparação local real de 15/11/2026, com Terra, seis chamadas e sem correções:

| Pedido | `legacy` | `operation-first` |
| --- | --- | --- |
| Olhar para a porta | `look`, correto | `look`, correto |
| Usar Retomar o Fôlego | `second_wind`, correto | `second_wind`, correto |
| “Vou avança até a porta da sala dos guardas e ficar diante dela.” | `challenge`, incorreto | `move` para `guard_door`, correto |

As requisições de cada par diferiram somente na ordem de `properties`. As
evidências locais estão em `logs/interpretacao/schema-order-terra-20261115/`.
O replay determinístico da resposta corrigida chegou à coluna 13, linha 6,
percorrendo 13,5 m e mantendo a porta fechada. Esse resultado é uma amostra de
três pedidos; não prova confiabilidade para toda linguagem natural. A checagem
descrita acima foi feita com o contrato anterior. O contrato atual também exige
request_parts; esses resultados históricos não são uma medição do novo contrato.

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
casos, não pelo validador. Veja [o contrato e suas limitações](../../docs/action-authorization.md).
Uma pergunta pode produzir zero etapas; posturas são detalhes narrativos sem custo.
As regressões locais das frases de combate ficam em tests/integration/test_semantic_interpretation.py;
os cinco casos reais opcionais estão em tests/live/test_semantic_interpretation.py.

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

# Testes live

## Suíte focada: movimento contextual no simulador

[test_contextual_movement.py](test_contextual_movement.py) contém oito testes
live novos, sem incluir a bateria anterior de poderes, turnos ou interpretação.
Todos usam a dungeon de `pocs/simulador/dungeon.json`, `Conversation` e os três
adaptadores reais: interpretação, decisão do Mundo e narração. Instruções,
esquemas e contextos são os de produção, construídos durante a execução.

| Caso | O que verifica |
| --- | --- |
| `investigar-cela-do-log` | Reproduz “Eu checo a cela, procurando por algo útil.” e o histórico real da falha. Entra na Cela 4, investiga e descobre os itens, sem coletá-los. |
| `pegar-espada-distante` | Aproxima-se da espada já descoberta e a coloca no inventário/equipamento real. |
| `atacar-com-aproximacao` | Declara apenas ataque, resolve iniciativa antes da caminhada, aproxima 4,5 m e consome a ação para golpear com a espada longa. |
| `ataque-com-movimento-insuficiente` | Tem só 1,5 m disponível: percorre esse trecho, para antes do alcance e preserva a ação. Não usa Dash ou Surto de Ação automaticamente. |
| `ataque-guarda-vence-iniciativa` | O guarda vence: não há aproximação nem golpe antes do turno do jogador. O teste para nesse limite, sem jogar as próximas rodadas/NPCs. |
| `investigar-grade-fechada` | A grade barra a investigação. Não atravessa nem abre/destranca por conta própria. |
| `investigar-sem-sair-do-lugar` | A restrição impede a aproximação; não há movimento nem investigação remota. |
| `investigar-com-ataque-de-oportunidade` | Sair do alcance para investigar o banheiro provoca a reação: aplica 5 de dano, gasta a reação do guarda e continua a caminhada/investigação. O evento deve chegar ao relatório do narrador. |

As condições e os dados ficam em
[tests/fixtures/contextual_movement](../fixtures/contextual_movement/README.md).
As preparações usam o motor real; não enviamos um texto de regras alternativo
para facilitar as respostas. As frases dos casos ficam congeladas como entradas
do jogador. Mudanças no contexto e nas instruções da aplicação chegam aos testes.

Os critérios avaliam efeitos, posição, custos, iniciativa e recursos, sem exigir
frases ou microetapas idênticas. Também reprovam poderes não pedidos, coleta de
outros itens, mudanças indevidas de portas ou troca de alvo. A narração precisa
ser não vazia e descrever em on ações concluídas. O texto completo fica disponível
para auditoria; não há um segundo modelo julgando o texto nem comparação literal
de respostas. Passar os casos não garante todos os possíveis pedidos em produção.

### Executar somente estes oito testes

Exige `OPENAI_API_KEY`; respeita `TRAMA_OPENAI_MODEL` e o padrão da aplicação.
São **24 chamadas normalmente, até 32** contando uma correção por interpretação.
Não há chamadas de IA durante a preparação dos cenários.

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_contextual_movement.py -m live -v
```

Para selecionar um caso:

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_contextual_movement.py -m live -k pegar-espada-distante -v
```

Coletar os testes não usa a API:

```bash
poetry run pytest tests/live/test_contextual_movement.py --collect-only -q
```

Cada execução salva os resultados de forma persistente, inclusive falhas, em:

```text
logs/live/contextual_movement/<execução>/<caso>/trace.jsonl
logs/live/contextual_movement/<execução>/<caso>/result.json
```

`trace.jsonl` usa os logs DEBUG da aplicação: prompts, esquemas, respostas,
consumo de tokens, operações e rolagens. `result.json` inclui o modelo, os
contextos efetivos, plano, estado antes/depois, resultado, dados usados e
critérios que falharam. Os identificadores correlacionam as chamadas da troca.
`TRAMA_CONTEXTUAL_ARTIFACTS` pode escolher outro diretório de saída.

A suíte padrão continua offline. A checagem local dos cenários e dos critérios é:

```bash
poetry run pytest tests/integration/test_contextual_live_scenarios.py
```


`test_semantic_interpretation.py` contém onze casos: Surto de Ação seguido de
ataque, dois retornos por coordenadas com postura, pergunta, negação e seis casos
de passagem de turno por inatividade, postura durante poder e negação de encerrar.
Faz uma
chamada de interpretação por caso, sem correção e sem executar o plano retornado.
Usa contexto local de combate com último ataque real e salva trace e avaliação.
Para executá-lo, autorize explicitamente as onze chamadas com
`RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_semantic_interpretation.py -m live`.

Esta pasta contém testes com serviços externos, credenciais ou chamadas reais de IA.

O cenário atual é `test_openai_movement.py`: oito chamadas à OpenAI (cinco de
interpretação básica, uma de narração inicial e duas para a troca mista on/off), usando
`OPENAI_API_KEY` e o modelo `gpt-5.6-terra` (ou `TRAMA_OPENAI_MODEL`). Só executa
quando `RUN_OPENAI_LIVE_TESTS=1`; sem essa autorização, fica ignorado.
Veja [a POC de movimento](../../pocs/movimento/README.md) para critérios e comando.

Cada módulo de testes deve usar `@pytest.mark.live` nos testes ou `pytestmark = pytest.mark.live` no módulo. Documente as variáveis de ambiente exigidas, os serviços utilizados e os critérios de avaliação. As credenciais ficam no ambiente local e nunca devem ser versionadas.

Execute explicitamente, após configurar os requisitos do cenário:

```bash
poetry run pytest tests/live -m live
```

O comando padrão `poetry run pytest` descobre apenas `tests/unit/` e `tests/integration/`.

Ao transformar uma prova de conceito em teste live, reutilize o código do sistema e os cenários pertinentes. Verifique resultados estruturados e invariantes do jogo; avalie a narração com critérios definidos pelo experimento, sem exigir frases idênticas do modelo.


## Dungeon: abrir, sair e observar

`test_dungeon_interactions.py` repete a mensagem da sessão que revelou a falha:
“Eu abro a grade da cela devagar e saio para olhar o corredor.” Há dois casos:
grade já aberta e grade fechada após uma sequência executada pelo motor.
Ambos carregam `pocs/simulador/dungeon.json` e usam `Conversation`, contextos,
instruções, esquemas, intérprete, diretor e narrador da aplicação, sem versões
alternativas do prompt de sistema.

Os critérios são estado/percurso e fatos: alcançar o corredor, abrir a grade
quando necessário, observar, não gastar poderes/inventar itens/criar combate e
receber narração. Não se exige texto idêntico entre respostas. O trace JSON é
salvo no diretório temporário do pytest. `trace.jsonl` captura o log DEBUG da
chamada, inclusive se houver falha, com as instruções, esquemas e respostas
registrados pelos módulos da aplicação.

São três chamadas por caso (interpretação, Mundo, narração), mais até uma
correção de interpretação por caso. Autorização explícita, até oito chamadas:

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_dungeon_interactions.py::test_real_open_leave_and_observe_corridor -m live
```

Exige `OPENAI_API_KEY`; respeita `TRAMA_OPENAI_MODEL`. A criação desses testes
não executa chamadas pagas. As regressões locais estão em
`tests/integration/test_interaction_preparation.py`.


### Investigação com entrada contextual

`test_real_investigation_enters_cell_contextually` congela a situação da sessão:
Jogador no corredor, coluna 8/linha 10, diante da grade aberta da Cela 4. A
preparação desse estado usa as operações reais do motor. Uma narração real dessa
preparação compõe o histórico; os prompts e as estruturas não possuem versões
alternativas para teste. O pedido é “Eu checo a cela, procurando por algo útil.”

São quatro chamadas (narração de preparação, interpretação, Mundo, narração de
resultado), mais até uma correção: máximo de cinco chamadas pagas. As rolagens
são controladas para fixar ruído e Investigação. Critérios: entrar na Cela 4,
registrar deslocamento, descobrir espada/uniforme com o teste fixado, não coletar
itens ou iniciar combate sem pedido e receber narração. `trace.jsonl` é salvo
mesmo em falha; `investigation.json` guarda os contextos e resultados.

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_dungeon_interactions.py::test_real_investigation_enters_cell_contextually -m live
```

Executar o arquivo inteiro autoriza os três casos: dez chamadas normalmente,
até treze considerando correções. Apenas coletar testes não chama a API.

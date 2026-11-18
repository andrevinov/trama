# Testes live

A [bateria de vínculos de memória](../../docs/sistema/qualidade/vinculos-memoria-live.md)
contém três casos focados na rejeição de uma alegação ligada a vários interesses.
Usa a dungeon, a abordagem preparada e o runner real, sem resposta congelada no live.

A [bateria de disposição social](../../docs/sistema/qualidade/disposicao-live.md)
usa sete situações `disposicao-*` no fluxo compartilhado: persona, alinhamento,
recompensa, informação relevante e escuta com custódia. Sua medição e seus limites
estão no [relatório datado](../../docs/evidencias/2026-11-17-disposicao-social/relatorio.md).

Antes de criar, alterar ou executar um caso, leia a
[política obrigatória dos live tests](../../docs/sistema/qualidade/politica-live-tests.md).
O [plano de adoção](../../docs/roadmaps/implementados/2026-11-16-live-tests-compartilhados/plano.md) descreve como compartilhar
carregamento, contextos e coordenação com o simulador. O carregamento já foi
compartilhado em `application/scenarios.py`. `GameFlow` já coordena a janela real
e tem regressões offline; os oito casos contextuais já usam essa entrada pela
agenda sem janela. As outras suítes mantêm os limites descritos em cada cenário.

A [cobertura atual](../../docs/sistema/qualidade/cobertura-atual.md) classifica os
arquivos e distingue fluxo completo, contratos parciais e experimentos.
A [execução sem janela](../../docs/sistema/interfaces/execucao-sem-janela.md) usa
o mesmo coordenador. Escolhas ausentes não equivalem a recusa automática.
O [experimento contextual](../../docs/evidencias/2026-11-16-movimento-contextual/relatorio.md)
registra a amostra real já executada, com ressalvas de narração.

`load_session(path)` lê os arquivos pelo caminho da aplicação;
`build_session(data)` aceita as variações de dados antes de construir/validar.
Os testes não constroem `Grid`, `Scene`, fichas ou sessões por conta própria.
As duas suítes de experimento importam `trama.analysis.interpretation` diretamente;
casos e expectativas estão em `tests/fixtures/interpretation/`. Não carregam
scripts ou dados de POCs. O [escopo parcial](../../docs/sistema/qualidade/analise-de-interpretacao.md)
continua identificado como `interpreter_contract`, sem executar efeitos do jogo.
Simulador e todas as suítes usam a [composição compartilhada dos serviços](../../docs/sistema/ia/integracao-openai.md)
para resolver modelo, timeout/retries, parâmetros por fase e política de correção.
Não constroem clientes/adaptadores por conta própria. `configurations.json`, no
diretório temporário de cada caso, registra a configuração emitida inclusive em
falhas de inicialização; os artefatos persistentes também incluem os parâmetros
efetivos. Variantes de modelo/correção/contexto/esquema são marcadas como
experimentos, com diferenças em relação ao padrão. A suíte semântica agora
respeita `TRAMA_OPENAI_MODEL`, mantendo zero correções como experimento explícito.
Os oito arranjos contextuais vêm do catálogo da aplicação e usam `open_situation`,
com a mesma preparação, pré-condições, histórico e reinício disponíveis na CLI
por `--situation ID`. Frases, escolhas, limites e critérios continuam nas fixtures.
A sequência avaliada é conduzida pelo runner real.
Consulte a [preparação reproduzível](../../docs/sistema/qualidade/preparacao-de-cenarios.md).

As projeções reais de `Conversation` agora usam os
[contratos de contexto por fase](../../docs/sistema/ia/contextos-e-contratos.md). Antes de alterar
contextos, instruções ou esquemas, confira a referência com
`poetry run python tools/context_contracts.py --check`. Esse comando e o teste
offline correspondente reconstroem os contratos atuais, sem chamadas externas.
Não use `docs/contracts/ai-contexts.json` para fabricar payloads dos testes live;
o arquivo é somente evidência de revisão.

## Suíte focada: conhecimento dos NPCs

`test_npc_knowledge_live.py` tem quatro casos pelo runner real: conhecimento
inicial, desconhecimento, lembrança desatualizada e relato retomado com fonte.
Uma tentativa por caso: 18 chamadas normais, teto de 24 com correções.
Veja [preparação, critérios e evidências](../../docs/sistema/qualidade/conhecimento-live.md).

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_npc_knowledge_live.py -m live -v
```

## Suíte focada: conclusão de turnos de NPCs

`test_npc_turn_completion.py` tem dois casos: aproximação com inimigo distante e
aproximação seguida de ataque ao alcançar. Ambos exigem devolver o controle e
responder a pergunta off sem alterar o estado. Consulte
[critérios, limites e evidências](../../docs/sistema/qualidade/turnos-npc-live.md).
Uma tentativa por caso: 10 chamadas normais, teto de 12 com correções,
a partir do combate preparado e sem narração de abertura.

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_npc_turn_completion.py -m live -v
```

## Suíte focada: percepção dos NPCs

`test_npc_perception.py` usa 13 situações genéricas, sem regras de dungeon:
visão/alcance, portas, escuridão/visão no escuro, som, passiva, Hide, Search e sono.
Consulte [casos, critérios, autorização e evidências](../../docs/sistema/qualidade/percepcao-live.md).
Uma bateria prevê 64 chamadas normais e teto de 81, uma repetição por caso.
Criar/coletar os testes não executa chamadas pagas.

```bash
poetry run pytest tests/live/test_npc_perception.py --collect-only -q
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_npc_perception.py -m live -v
```

## Suíte focada: conversa antes do combate

Os quatro casos em `test_parley.py` usam situações jogáveis, abertura e mensagens
pelo runner real: abordagem distante, sucesso/falha de Persuasão e ataque escolhido
pelo jogador. Consulte [critérios, limites e artefatos](../../docs/sistema/qualidade/conversa-live.md).
Uma bateria tem 27 chamadas normais e teto de 34, sem repetir até passar.
A criação e a coleta são offline; chamadas pagas requerem autorização explícita.

```bash
poetry run pytest tests/live/test_parley.py --collect-only -q
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_parley.py -m live -v
```

## Suíte focada: movimento contextual no simulador

Os oito casos usam o fluxo completo da interação a partir de condições preparadas.
Consulte [casos, orçamento, critérios e artefatos](../../docs/sistema/qualidade/movimento-contextual-live.md).
Exige `OPENAI_API_KEY` e autorização do experimento:

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_contextual_movement.py -m live -v
```

Uma execução prevê 33 chamadas normais, até 41 com correções nos padrões atuais.
O teto é imposto antes do SDK; não é limite monetário. Coleta sem chamadas:

```bash
poetry run pytest tests/live/test_contextual_movement.py --collect-only -q
```

As condições estão nas [fixtures](../fixtures/contextual_movement/README.md).
Os logs persistem em `logs/live/contextual_movement/`; configuração alternativa
de saída usa `TRAMA_CONTEXTUAL_ARTIFACTS`. Falhas e inconclusivos reprovam e são
preservados, sem repetir até passar.

`test_semantic_interpretation.py` contém onze casos: Surto de Ação seguido de
ataque, dois retornos por coordenadas com postura, pergunta, negação e seis casos
de passagem de turno por inatividade, postura durante poder e negação de encerrar.
Faz uma
chamada de interpretação por caso, sem correção e sem executar o plano retornado.
Usa contexto local de combate com último ataque real e salva trace e avaliação.
Para executá-lo, autorize explicitamente as onze chamadas com
`RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_semantic_interpretation.py -m live`.

Esta pasta contém testes com serviços externos, credenciais ou chamadas reais de IA.

`test_openai_movement.py` preserva sete casos anteriores: oito chamadas à OpenAI
sem correções (cinco de interpretação básica, uma de narração inicial e duas
para a troca mista on/off), usando
`OPENAI_API_KEY` e o modelo `gpt-5.6-terra` (ou `TRAMA_OPENAI_MODEL`). Só executa
quando `RUN_OPENAI_LIVE_TESTS=1`; sem essa autorização, fica ignorado.
Veja os [mapas e critérios preservados](../fixtures/scenarios/README.md).
Para executar somente esses sete casos, com autorização explícita:

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_openai_movement.py -m live -v
```

Cada módulo de testes deve usar `@pytest.mark.live` nos testes ou `pytestmark = pytest.mark.live` no módulo. Documente as variáveis de ambiente exigidas, os serviços utilizados e os critérios de avaliação. As credenciais ficam no ambiente local e nunca devem ser versionadas.

Execute explicitamente, após configurar os requisitos do cenário:

```bash
poetry run pytest tests/live -m live
```

O comando padrão `poetry run pytest` descobre apenas `tests/unit/` e `tests/integration/`.

Ao derivar um teste live do simulador, use o carregador, as situações e o fluxo compartilhados. Verifique resultados estruturados e invariantes do jogo; avalie a narração com critérios definidos pelo experimento, sem exigir frases idênticas do modelo. Identifique explicitamente as análises parciais.


## Dungeon: abrir, sair e observar

`test_dungeon_interactions.py` repete a mensagem da sessão que revelou a falha:
“Eu abro a grade da cela devagar e saio para olhar o corredor.” Há dois casos:
grade já aberta e grade fechada após uma sequência executada pelo motor.
Ambos carregam `src/trama/scenarios/dungeon_escape.json` e usam `Conversation`, contextos,
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

A bateria nova de [dificuldades contextuais e referências de memória](../../docs/sistema/qualidade/dificuldade-live.md) roda isoladamente em `test_contextual_difficulty_live.py`; dez casos, até 40 chamadas agregadas no experimento autorizado.

[Agência e fidelidade da narração](../../docs/sistema/qualidade/agencia-live.md): três casos novos em `test_npc_agency_live.py`, com orçamento e autorização separados.

A bateria de [inspeção de passagens](../../docs/sistema/qualidade/inspecao-live.md)
tem quatro casos novos em `test_passage_inspection_live.py`, com preparação e
critérios verificados offline e quatro aprovações na medição de 17/11/2026.
Autorização separada para uma tentativa por caso,
teto de 15 chamadas; criar/coletar não executa IA real.

[Comunicação por gestos](../../docs/sistema/qualidade/gestos-live.md): quatro
casos novos em `test_gestural_communication_live.py`, teto separado de 18 chamadas
e uma tentativa por caso. Preparação e critérios verificados sem rede.

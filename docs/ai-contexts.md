# Contratos de contexto da IA

## Onde os dados são construídos

Os contratos executáveis estão em
[`application/context_contracts.py`](../src/trama/application/context_contracts.py).
Eles declaram tipos, campos obrigatórios/opcionais, origem e finalidade. As
projeções continuam sendo calculadas pelo estado atual da aplicação:

1. `context.build_context` produz posição, grade, arquitetura e criaturas vistas.
2. `GameSession.interpreter_context` agrega ficha, combate e estado do Mundo.
   `DungeonSession` agrega o roteiro e mascara fechaduras ainda não examinadas
   na projeção do jogador, preservando a verdade em `world`.
3. `Conversation` publica contextos por fase, construídos dessas informações,
   histórico e relatórios reais. Cada saída é um `AIContext` validado.
4. `GameFlow` agenda a fase e envia o contexto aos adaptadores. A janela não
   cria nem completa esses dados.

`AIContext` é compatível com `dict` e JSON. Seu atributo Python `kind` identifica
o contrato; esse atributo não é um campo do payload nem altera o esquema de
resposta do modelo. `deepcopy`, usado no agendamento de workers, preserva o tipo.
O campo JSON `phase` já existente continua usando `player_action`/`npc_turn` no
Mundo e `initial`/`reply` na narração.

O interpretador usa a projeção validada diretamente, evitando uma segunda
compactação que pudesse descartar um campo novo. Os três adaptadores verificam
o tipo de fase quando recebem `AIContext`. O suporte anterior a `dict` permanece
para experimentos/contratos isolados dos adaptadores; esse caminho não deve ser
usado para montar à mão contextos dos testes de fluxo completo.

## Fases e limites de informação

| `ContextKind` | Entrada canônica | Conteúdo e limite |
| --- | --- | --- |
| `interpretation` | `Conversation.interpretation_context()` | Projeção mínima da intenção: capacidades, posição, alvos vistos, itens conhecidos e histórico on. Não inclui `world`, ficha completa ou histórico off. |
| `world_action` | `Conversation.world_context(plan)` | Mestre recebe o estado completo e a proposta do jogador, incluindo requisitos espaciais, preparação prevista e fontes declaradas. Proposta não é efeito executado. |
| `npc_turn` | `Conversation.world_context()` | Estado completo para decidir o NPC ativo; `player_plan` e `player_request_parts` ficam vazios. O `GameFlow` só agenda essa decisão quando há NPC ativo e jogador com PV. A projeção também pode ser consultada sem disparar execução. |
| `narration_initial` | `Conversation.narration_context(initial=True)` | Descrição do lugar/estado inicial usando percepção. O Mundo completo serve à coerência, sem autorizar revelar seus segredos. |
| `narration_result` | `Conversation.narration_context(speech, report)` | Estado atual, fatos executados, impedimentos, reações, percepção e memória anterior. Atende também mensagens mistas on/off. |
| `narration_off` | `Conversation.narration_context(Speech(off=...))` | Pergunta exclusivamente off: não contém ação/reação nova em `execution`, não autoriza fala on e pode consultar `previous_execution`. |

A arquitetura nomeada não equivale ao campo de visão: o interpretador já recebe
ids/posições dos cômodos e passagens para resolver destinos. Na dungeon, uma
fechadura fechada ainda não examinada usa `locked=null` nessa projeção. Objetos
estáticos entram no mapa mínimo somente quando vistos; itens do inventário
incluem também os conhecidos/carregados. Uma lembrança de objeto não significa
visão atual dele. `visible_creatures` é filtrado pela visão, com o prisioneiro
como extensão de cenário quando visível.

O narrador recebe `world` completo, inclusive segredos e NPCs ocultos. A sua
projeção `perception` contém apenas fatos vistos/conhecidos permitidos. Não se
deve descrever um item carregado como ainda disponível no chão. As instruções
reais do narrador exigem não revelar a identidade do ilusionista ou os itens
escondidos antes dos fatos registrados. Contratos de dados e filtros não provam
que todo texto de um modelo obedecerá a essas instruções; isso continua exigindo
critérios de avaliação da narração.

## Campos obrigatórios e opcionais

Os nomes abaixo são campos de raiz. O registro executável detalha a origem e o
significado de cada um; a referência revisada inclui os caminhos internos
observados por fase.

| Fase | Obrigatórios | Opcionais |
| --- | --- | --- |
| Interpretação | `mode`, `map`, `character`, `combat`, `visible_creatures`, `equipped_weapons`, `last_attack`, `recent_messages`, `available_actions`, `turn_resources` | `scenario`, `visible_objects` |
| Mundo e NPC | `mode`, `map`, `character`, `combat`, `visible_creatures`, `equipped_weapons`, `last_attack`, `recent_messages`, `player_sheet`, `visible_enemies`, `world`, `player_plan`, `player_request_parts`, `phase` | `scenario`, `visible_objects`, extensões já reconhecidas `available_actions` e `turn_resources` |
| Três tipos de narração | `mode`, `character`, `combat`, `phase`, `allow_on`, `player`, `execution`, `previous_execution`, `perception`, `player_sheet`, `world`, `history`, `verified_rules` | Nenhum campo de raiz |

Obrigatório não significa não nulo: `combat` é `null` fora de combate;
`last_attack` e `previous_execution` podem ser `null`. Em modo narrado,
`character.remaining_meters` é `null`. `character.current_area` pode faltar numa
grade sem cena nomeada e pode ser `null` numa passagem. `map.scene` é opcional
nas grades simples. Estruturas completas de ficha e cenário são extensões
internas com campos variáveis; os tipos críticos e suas nulabilidades estão em
`INTERNAL`/`OPTIONAL_INTERNAL`, e suas mudanças estruturais entram na revisão.

Na interpretação, o histórico contém até seis mensagens on; Mundo usa até doze
on, e narração até doze mensagens com on/off. `verified_rules` vem da aplicação,
não de uma regra inventada pelo teste. `execution.player_movement` é calculado
dos eventos reais. `previous_execution` guarda identidade, ator, execução e
situação anteriores; uma pergunta off pode explicá-los sem executá-los novamente.

Campos de raiz desconhecidos, tipos críticos errados, fase incompatível, off
na projeção mínima, elementos marcados como ocultos dentro da percepção e dados
não serializáveis/infinitos geram `ContextError`. Booleanos não são aceitos como
números. A validação não filtra campos para esconder uma incompatibilidade.
Um campo de raiz novo precisa ser declarado; campos internos novos continuam
no payload e são apontados pela revisão offline. Uma falha na projeção de
abertura também é reportada pelo fluxo, sem derrubar a janela ou chamar a IA.

## Referência e verificação offline

[`docs/contracts/ai-contexts.json`](contracts/ai-contexts.json) é evidência de uma
revisão, não um cenário nem um payload de teste. Nenhum código de execução do
jogo o lê para enviar dados ao modelo. O comando de verificação reconstrói tudo:

```bash
poetry run python tools/context_contracts.py --check
```

O utilitário observa as projeções reais com o carregador e as operações públicas
da aplicação: dungeon, descoberta de itens, combate/último ataque no mapa legado,
decisão de NPC, execução impedida, memória off e grade simples. Não chama um
modelo. A preparação é determinística e não pretende testar a interpretação
dessas mensagens ou substituir os live tests.

A referência registra:

- As declarações de contrato, origem, tipos e nulabilidade.
- Caminhos/tipos observados e textos que chegam aos contextos, incluindo catálogo
  de ações, orientação de cenário e `verified_rules`.
- Instruções e esquemas de resposta dos adaptadores atuais. A ordem de cada
  `properties` é registrada separadamente: uma comparação sem ordem não detectaria
  aquela regressão de geração estruturada.

Ids de execução/correlação e `timestamp` não entram na comparação de textos;
seus campos/tipos continuam sendo verificados. Ids de domínio, como `guard_1`,
são preservados. Não há baseline de cada valor numérico do estado: asserções de
movimento, recursos e efeitos pertencem aos testes comportamentais. A cobertura
do registro é a das amostras e das declarações; um ramo de dados novo precisa
também de amostra e de critérios quando fizer parte do incremento.

O comando aponta caminhos adicionados, removidos ou alterados e retorna código
1 quando diverge. O pytest padrão também executa essa comparação, sem rede.
`--check` não altera arquivos. O hash registrado detecta uma edição manual da
referência sem o registro correspondente de revisão.

## Como revisar uma mudança

1. Altere os produtores/contratos reais e preserve os critérios comportamentais.
   Um campo obrigatório ausente ou novo campo de raiz ainda não declarado precisa
   ser corrigido no contrato antes de gerar a referência.
2. Execute `--check` e examine os caminhos e o diff de código. Revise fonte,
   finalidade e limite de informação de cada campo, instrução ou esquema alterado.
   Uma regressão não deve ser “corrigida” aceitando o novo registro.
3. Se a alteração for intencional e revisada, registre o motivo:

   ```bash
   poetry run python tools/context_contracts.py --update --reason "Explique os campos e o motivo da alteração revisada."
   ```

4. Confira o diff da referência e execute `--check` e os testes pertinentes.
   Atualização não exige nem executa chamadas pagas. Avaliação com modelo real
   continua sujeita à autorização e ao escopo de cada cenário.

`--update` exige justificativa não vazia e registra o hash anterior e o atual.
Não deve ser executado automaticamente durante testes, startup ou CI para fazer
a comparação passar. O campo `review` não é enviado aos adaptadores.

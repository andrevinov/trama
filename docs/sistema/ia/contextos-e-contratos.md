# Contratos de contexto da IA

Tier 3 · [IA](README.md) · [Visão geral](../../../README.md)

## Onde os dados são construídos

Os contratos executáveis estão em
[`application/context_contracts.py`](../../../src/trama/application/context_contracts.py).
Eles declaram tipos, campos obrigatórios/opcionais, origem e finalidade. As
projeções continuam sendo calculadas pelo estado atual da aplicação:

1. `context.build_context` produz posição, grade, arquitetura e criaturas vistas.
2. `GameSession.interpreter_context` agrega ficha, combate e estado do Mundo.
   A sessão geral mascara fechaduras ainda não examinadas na projeção do jogador,
   preservando a verdade em `world`; `DungeonSession` agrega o roteiro.
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
ids/posições dos cômodos e passagens para resolver destinos. Em qualquer cenário, uma
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
| Interpretação | `mode`, `sensing`, `knowledge`, `parley`, `map`, `character`, `combat`, `visible_creatures`, `communication_targets`, `equipped_weapons`, `last_attack`, `recent_messages`, `available_actions`, `turn_resources` | `scenario`, `visible_objects` |
| Mundo e NPC | `mode`, `sensing`, `knowledge`, `parley`, `map`, `character`, `combat`, `visible_creatures`, `communication_targets`, `equipped_weapons`, `last_attack`, `recent_messages`, `player_sheet`, `visible_enemies`, `world`, `player_plan`, `player_request_parts`, `phase` | `scenario`, `visible_objects`, extensões já reconhecidas `available_actions` e `turn_resources` |
| Três tipos de narração | `mode`, `sensing`, `knowledge`, `parley`, `character`, `combat`, `phase`, `allow_on`, `player`, `execution`, `previous_execution`, `perception`, `player_sheet`, `world`, `history`, `verified_rules` | Nenhum campo de raiz |

`knowledge` contém somente a seleção de memórias do jogador, com afirmação,
fonte, ocasião, contexto e sequência de aquisição. `world.knowledge.actors`
contém as seleções por NPC na decisão do Mundo; esse campo é removido da
narração, que recebe as memórias compartilhadas nos eventos executados. O
interpretador pode propor `claims` em falas afirmativas do jogador, como relatos
não confirmados. O Mundo cita `memory_ids` do próprio NPC em `say`; o executor
valida posse/divulgação e registra quem ouviu. Não transforma relato em verdade
nem atualiza uma crença por uma mudança oculta do mapa. Veja os
[contratos e limites de seleção](../aplicacao/conhecimento-dos-npcs.md).

`sensing` é comum às seis fases: `hidden` e `can_hide` descrevem apenas o
jogador, sem revelar perfis de NPCs ocultos. `world.perception` contém a visão de
mestre: perfis, sono, conhecimento por fonte, total real de furtividade e última
busca. `world.lighting` contém casas de luz fraca/escuridão. NPCs sem ficha de
classe aparecem entre os observadores, sem turno ou poderes fictícios. O Mundo
propõe Search; dados, alcance, ação e resultado são calculados pelo motor.
Veja [percepção por NPC](../mundo/visao-e-percepcao.md).

`parley` é comum às seis fases: `null` sem abordagem, ou interlocutor, exigência,
posições em base 1, concessão e status `pending`/`listening`/`peaceful`/`combat`.
`listening` mantém a abordagem ativa; `peaceful` pode resultar de trégua explícita.
O registro preserva o
ponto de detecção; posições atuais continuam no mapa. O Mundo propõe `parley`
ou `influence` e o narrador recebe o resultado validado, sem escolher dados.
Veja [conversa antes do combate](../aplicacao/conversa-antes-do-combate.md).

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

Na conclusão de NPCs, movimento limitado mantém percurso/custo e motivo em
`movement_limit_reason`, com `status=movement_limited` e sem `stop_reason` de
interrupção. Falhas posteriores permanecem em `failures`; o evento de término
pode registrar `fallback=end_turn` e a causa. O narrador recebe a iniciativa já
avançada; uma falha recuperada não significa que o NPC ainda está agindo.

Campos de raiz desconhecidos, tipos críticos errados, fase incompatível, off
na projeção mínima, elementos marcados como ocultos dentro da percepção e dados
não serializáveis/infinitos geram `ContextError`. Booleanos não são aceitos como
números. A validação não filtra campos para esconder uma incompatibilidade.
Um campo de raiz novo precisa ser declarado; campos internos novos continuam
no payload e são apontados pela revisão offline. Uma falha na projeção de
abertura também é reportada pelo fluxo, sem derrubar a janela ou chamar a IA.

## Referência e verificação offline

[`docs/contracts/ai-contexts.json`](../../contracts/ai-contexts.json) é evidência de uma
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

Ids de execução/correlação/aquisição (`event_id`) e `timestamp` não entram na comparação de textos;
seus campos/tipos continuam sendo verificados. Ids de domínio, como `guard_1`,
são preservados. Não há baseline de cada valor numérico do estado: asserções de
movimento, recursos e efeitos pertencem aos testes comportamentais. A cobertura
do registro é a das amostras e das declarações; um ramo de dados novo precisa
também de amostra e de critérios quando fizer parte do incremento.

O comando aponta caminhos adicionados, removidos ou alterados e retorna código
1 quando diverge. O pytest padrão também executa essa comparação, sem rede.
`--check` não altera arquivos. O hash registrado detecta uma edição manual da
referência sem o registro correspondente de revisão.

## Avaliação de dificuldades e ações do Mundo

`world.adjudication` é privado do Mundo: pedidos com fatos identificados e
decisões reutilizadas. A resposta inclui `adjudications`, com resultado, categoria
típica, vantagem/desvantagem, fatos e razão. Python exige completude antes dos
efeitos; CDs fixas não podem ser sobrescritas. O narrador recebe somente
resultados públicos validados, sem o cache ou as justificativas privadas.
O esquema de ações separa `say`, `influence` e demais operações: referências
públicas só em `say`; o alvo externo de Influence é nulo. Referências privadas
de gravações antigas são validadas e omitidas da narração. Perguntas dirigidas
a NPCs são falas executadas; dúvidas de regras permanecem em off.

## Como revisar uma mudança

Disposição social: `world.social` contém perfis e decisões para o Mundo;
`influence.assessment` descreve impactos sem fornecer pesos ou resultado final.
O código calcula a disposição, vincula Claims a memórias reais e emite apenas a
resposta condicional escolhida. O narrador não recebe `world.social` nem a
decomposição privada em relatórios atuais/anteriores. A avaliação pública e a
concessão continuam disponíveis para explicar o resultado. Promessas em Claims
representam compromissos declarados, não pagamento ou verdade confirmada.

Vínculos de memória: a entrada `assessment.memory_effects` permite a mesma Claim
com interesses distintos, sem repetir o par Claim/interesse. Na decisão calculada
em `world.social.decisions[].disposition.memory_effects`, cada fato aparece uma
vez com `impacts` preservando seus vínculos e razões. O peso da fonte se aplica
ao saldo de efeitos limitado a -1/0/+1, e não a cada justificativa. O narrador
continua sem receber esses fundamentos privados. A amostra offline cobre uma
alegação de nobreza relevante simultaneamente para segurança e emprego.

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

## Acompanhamento de intenções

`npc_agency` é uma fase adicional de decisão do Mundo após a execução do jogador.
Seu contrato é deliberadamente menor: `mode`, `phase`, `actor`, `profile`,
`knowledge` do próprio NPC, `observations`, `parley` e `world.adjudication`. Não
recebe histórico global ou prompt privado; comunicações não compreendidas têm
texto nulo. O plano do Mundo inclui `intent` somente nessa fase; nas outras,
o campo é nulo. A execução valida ator, espera limitada e operações permitidas.

A narração recebe `perception.communications`, com volume e ouvintes das falas
percebidas pelo jogador. Essa memória permanece disponível em perguntas off sem
ações novas. Objetivos e razões privadas do acompanhamento não são narráveis.
Veja [intenções dos NPCs](../aplicacao/intencoes-dos-npcs.md).

## Comunicação gestual

`communication_targets` contém somente identidade e visibilidade de NPCs conhecidos
para interpretação e Mundo, sem posições ocultas. `gesture` separa descrição
observável e intenção privada. A narração recebe o resultado executado; o
contexto individual do NPC recebe somente o movimento visto, com `medium=gesture`,
`understood=null` e sem a intenção privada. `seen_by` substitui audição nessa
comunicação. Destinatário sem abordagem pode receber uma decisão pontual
`one_shot`, encerrada após responder. Veja [comunicação gestual](../aplicacao/comunicacao-gestual.md).

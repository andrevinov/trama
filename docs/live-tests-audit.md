# Inventário dos fluxos e das suítes live

Auditoria do passo 2 do [plano de adoção](live-tests-plan.md), seguindo a
[política dos live tests](live-tests-policy.md). As seções numeradas preservam o
retrato registrado no passo 2. A atualização abaixo identifica o que já mudou
nos passos 3 a 12; os oito casos contextuais já foram migrados para o coordenador.

Foram lidos os seis arquivos em `tests/live/`, seus helpers/fixtures, o runner
do experimento de interpretação, a composição do simulador e a coordenação da
janela. A coleta offline encontrou **38 casos parametrizados**. O inventário
original não executou chamadas à IA. A seção do passo 12 acrescenta resultados
reais apenas dos oito casos contextuais, distinguindo execução de implementação.

## Atualização após o passo 3

O [carregador compartilhado](../src/trama/application/scenarios.py) agora contém
`load_session(path)` e `build_session(data)`. Simulador, runner antigo, live tests
e POC de interpretação usam essas entradas. O módulo delega aos construtores
existentes, sem Pygame, CLI ou SDK. `simulator.load_session` e `load_dungeon`
continuam reexportados por compatibilidade.

Foram eliminadas as construções paralelas de `Grid`, `Scene`, fichas e sessões
nos testes live/POC. A grade simples é fornecida como dados; a porta do banheiro
e a posição/porta da suíte semântica são variações anteriores à construção real.
Os testes antigos também passaram a ler as fichas do JSON pelo carregador, como
o simulador já fazia. Os 38 casos e seus critérios foram preservados.

Continuam pendentes a coordenação compartilhada, as atribuições diretas de
estado/histórico, as diferenças de configuração dos adaptadores, os turnos e
escolhas de reação e a avaliação de apenas `steps[0]` em cinco casos antigos.
Portanto, a classificação de cobertura da matriz permanece a mesma. As
descrições seguintes de carregamento direto são o histórico anterior ao passo 3.

## Atualização após o passo 4

`application/game_flow.py` disponibiliza o coordenador e seu protocolo de pedidos
externos/resultados, com testes locais de mensagens, NPCs, reações, falhas e
thread dona. A janela e os live tests ainda não o usam. Portanto, as lacunas da
matriz continuam válidas para as suítes live existentes; a extração não equivale
à adoção. Essa era a situação ao concluir o passo 4; a conexão da janela foi
realizada no passo 5, descrito abaixo.

## Atualização após o passo 5

`MovementWindow` já usa `GameFlow` e removeu sua coordenação paralela de mensagens,
NPCs e reações. Abertura, envio, escolha e reinício usam as entradas públicas do
coordenador. A UI agenda pedidos uma vez por id e devolve resultados na thread
principal; regressões verificam inclusive respostas antigas e duplicadas.

Os testes locais da janela agora passam por mensagens e adaptadores explícitos,
em vez de injetar planos sem pedido na fila. Há comparação offline de relatórios
e contextos da janela com o fluxo direto, além de expectativas independentes.
Os live tests ainda fazem sua sequência manual e mantêm a classificação da matriz.
A tabela histórica seguinte descreve a coordenação da UI antes dessa extração.

## Atualização após o passo 6

`Conversation` agora publica `AIContext` validado em seis fases. Os adaptadores
verificam o tipo quando recebem essa projeção e o interpretador não a compacta
novamente. O contrato tem uma referência de revisão offline para campos,
textos, instruções e esquemas atuais, incluindo ordem de propriedades. A
referência não entra nos pedidos; a alteração intencional exige justificativa.
Isso já beneficia as suítes que usam as projeções reais, mas não substitui a
sequência manual dos live tests nem resolve suas preparações diretas. A matriz
histórica continua descrevendo esses limites de cobertura.

## Atualização após o passo 7

Os oito arranjos contextuais agora declaram preparação e pré-condições nos JSONs.
A caminhada real produz o saldo de 1,5 m. Largar/recolher a espada diante do
guarda provoca Percepção e iniciativa reais, sem atribuir alerta/disfarce.
Esse caso ganhou um d20 de preparação; os dados da interação avaliada e seus
critérios foram preservados. Não restam as atribuições diretas de estado listadas
na seção histórica abaixo.

O histórico registrado passa por `DialogueMessage.from_data` e
`Conversation.extend_history`, também usada pelas mensagens normais. A validação
preserva papéis/on/off e rejeita o lote inteiro se houver erro, sem alterar a
memória mecânica. A frase de narrador fabricada para preparar a grade fechada na
suíte de interações foi removida; permanecem os fatos reais do relatório.

As regressões offline conferem todos os arranjos e falhas de preparação antes de
qualquer chamada externa. A [documentação da preparação](live-test-preparation.md)
descreve o helper e seus limites. As suítes continuam com fluxo parcial; a matriz
histórica não é uma declaração de que já usam `GameFlow`.

## Atualização após o passo 8

Simulador, POC e seis suítes live compartilham `OpenAIConfig`/`open_services`,
com parâmetros por fase, timeout, retries e política de correção explícitos.
`bootstrap.py` compõe sessão, serviços e fluxo; a janela recebe o fluxo da CLI.
A suíte contextual também usa essa composição ao preparar sua conversa com os
serviços reais, mas ainda encadeia as chamadas manualmente.

O modelo da suíte semântica agora respeita `TRAMA_OPENAI_MODEL`; zero correções
continua sendo uma variante identificada. As comparações de contexto/esquema são
experimentos explícitos. Os padrões não mudaram. Configurações efetivas são
registradas nos logs e artefatos, inclusive tentativas de inicialização que
falham. A [composição dos serviços](service-composition.md) descreve a API e os
testes offline. As divergências históricas de composição/configuração abaixo
foram resolvidas; a matriz de execução parcial continua válida.

## Atualização após o passo 9

`GameRunner` agenda sincronamente os pedidos públicos do mesmo `GameFlow`, sem
chamar adaptadores por etapa, avançar NPCs ou resolver regras em uma coordenação
paralela. `game.runner` é a entrada da composição para abertura, mensagens,
retomadas de oportunidade e reinício. O resultado observa os pedidos, relatórios,
falhas e pontos de parada; não escolhe reações nem considera um limite de
despachos como conclusão. Regressões offline comparam janela/runner e efeitos.

A [API sem janela](headless-runner.md) está pronta para adoção live. Os oito casos
contextuais ainda mantêm a sequência anterior; sua migração, orçamento e revisão
do critério do guarda que vence iniciativa continuam no passo 10. Portanto, a
matriz histórica de cobertura live continua parcial. Não houve chamadas pagas.

## Atualização após o passo 10: cobertura atual

Os oito casos contextuais foram migrados para `open_game`/`game.runner`. A
preparação pública e suas pré-condições ocorrem na conversa do fluxo antes de
consultar IA. Abertura e mensagem usam o coordenador; ele resolve os NPCs e
eventuais pausas. O caso em que o guarda vence não termina mais na iniciativa:
exige resolução do turno e devolução do controle. Orçamento ou escolha ausente
produzem inconclusivo, sem pular fases ou recusar uma reação automaticamente.

| Suíte | Casos | Classificação após revisão do passo 10 | Limite que permanece |
| --- | ---: | --- | --- |
| Contextual | 8 | Fluxo completo para a interação avaliada, com preparação determinística e histórico registrado quando indicado | Não é uma partida inteira desde o início; oito fixtures sem escolhas de reação predefinidas; coerência narrativa completa ainda depende de revisão. |
| Dungeon | 3 | Adaptadores/motor, fluxo parcial | Mantém sequência manual; não conduz NPCs/retomadas pelo runner. |
| Movimento anterior | 7 | Adaptadores/primitivas, fluxo parcial | Cinco casos ainda executam apenas `steps[0]`; sem decisão do Mundo. |
| Semântica | 11 | Contrato do interpretador | Não executa o plano avaliado; zero correções é variante explícita. |
| Experimento de interpretação | 6 | Experimento de provedor | Compara contexto/primeira resposta; não executa efeitos. |
| Experimento de esquema | 3 | Experimento de provedor | Compara ordens; variante antiga é controle. |

A suíte contextual passa a prever **33 chamadas normais e no máximo 41** aos
métodos do SDK, uma vez por caso nos padrões atuais, contra 24/32 anteriormente.
Isso inclui abertura, NPC e correção. O teto é imposto na infraestrutura antes
de cada chamada lógica, compartilhado entre adaptadores. Com retries zero ele
não permite tentativas HTTP adicionais; configurações diferentes registram o
limite superior de tentativas. Não é orçamento monetário ou autorização paga.

As demais suítes preservam suas estimativas anteriores: o conjunto dos 38 casos
passa a estimar 74/91 chamadas normais/máximas, sem teto global implementado nas
outras suítes. Nenhuma bateria real foi executada nesta migração.

As evidências agora incluem abertura, ações/retomadas e seus ids, planos/contextos
observados do runner, estados, dados obrigatórios/opcionais, orçamento e desfecho.
Os critérios mecânicos foram preservados e ampliados para o NPC; testes locais
reprovam resposta incompleta, limite esgotado e escolha ausente. Veja os detalhes
na [migração contextual](contextual-live-flow.md). As tabelas numeradas seguintes
continuam sendo o retrato histórico do passo 2, não a classificação atual.

## Atualização após o passo 11: prova offline dos critérios

Foram acrescentadas 17 verificações locais de composição real com transporte
simulado. Controles positivos comparam pedidos/contextos e efeitos de janela e
runner, mas a igualdade sozinha não aprova: ambos precisam satisfazer critérios
independentes. Controles negativos reprovam aproximação omitida, Surto sem ataque,
NPC sem conclusão, oportunidade perdida e descrição de deslocamento inexistente.

Os critérios de movimento/NPC/oportunidade vêm do avaliador live atual. Surto é
uma prova local com recursos e PV esperados literalmente, sem novo teste pago.
As cópias negativas de observações não alteram o estado da aplicação. `proof.json`
e logs locais distinguem o que foi executado do que foi retirado para avaliação.
Veja a [demonstração e seus limites](regression-detection.md).

A cobertura live continua com os mesmos oito casos migrados e outras cinco
suítes parciais/experimentais. Não houve execução paga no passo 11; os controles
não medem acerto de modelo real nem certificam a verdade de toda narração.

## Atualização após o passo 12: experimento real

O [relatório de 16/11/2026](experiments/step12-20261116T205209Z.md) registra a
bateria autorizada e seu plano prévio: oito casos, uma execução por caso, padrão
`gpt-5.6-terra`/`low`, retries zero, até 41 chamadas. Resultado: **8 passed em
82,83 s**, 33 chamadas, sem correção de interpretação, rerun, falha de serviço
ou inconclusivo. Uso informado: 331.806 tokens de entrada e 2.801 de saída.

| Suíte | Cobertura implementada atual | Execução real nesta etapa |
| --- | --- | --- |
| Movimento contextual: 8 casos | Fluxo compartilhado desde situação preparada, incluindo abertura, interpretação, Mundo, NPC e narração | 8/8 aprovações mecânicas, uma vez cada; textos revisados com ressalvas |
| Outras 5 suítes: 30 casos | Contratos parciais/experimentos, conforme inventário e atualizações anteriores | Não executadas; não recebem aprovação por esta bateria |

A revisão das 16 narrações confirmou os efeitos centrais, mas encontrou regras
em `on`, origem do deslocamento descrita de modo impreciso e a palavra
“vulnerável” após um erro do guarda sem efeito mecânico correspondente. Os
critérios automáticos não certificam esses aspectos. Detalhes por caso,
configuração, hashes de fontes/evidências e localização dos logs constam no
relatório. Não houve alteração de código ou critérios durante o experimento.

Essa amostra não mede repetibilidade ou sucesso em uma partida completa. Os
testes locais da UI e os controles negativos continuam sendo evidências
distintas; o experimento real usa o runner, sem renderização do Pygame.

## 1. Fluxo de referência: o que o simulador faz

Fontes: [composição](../src/trama/simulator.py),
[janela](../src/trama/ui/movement_window.py),
[conversa](../src/trama/application/conversation.py) e
[transporte dos adaptadores](../src/trama/infrastructure/openai_json.py).

| Entrada ou transição | Responsável no passo 2 | Caminho e condições à época |
| --- | --- | --- |
| Construir a partida | `simulator.load_session` / `main` | Carrega JSON, escolhe `DungeonSession` ou `GameSession`, constrói mapa/fichas, resolve modelo e compõe adaptadores. |
| Abertura | `MovementWindow.start` / `_start` | Cria correlação e pede `narration_context(initial=True)`. Sem narrador, registra indisponibilidade. |
| Receber mensagem | `submit` / `_submit` | Ignora envio vazio ou durante pedido pendente; usa `Conversation.prepare`, valida entrada e registra histórico. Bloqueia nova ação on se houver oportunidade pendente ou interpretador ausente. |
| Pergunta exclusivamente off | `_submit` | Pede narração diretamente, sem interpretação, Mundo ou execução física. |
| NPC já ativo antes do pedido | `_submit` / `_request_npc_turn` | Marca retomada do pedido do jogador, resolve NPCs primeiro e só então pede interpretação. |
| Interpretar | `_request_interpretation` | Consulta o contexto atual e chama o interpretador no worker. A correção declarativa permitida fica dentro do adaptador. |
| Receber plano | `poll` / `_poll` | Faz `validate_player_plan(..., stage="pre_world")`. Plano sem etapas passa por `Conversation.execute` e segue diretamente à narração; plano com etapas consulta o Mundo. Sem diretor configurado, usa `WorldPlan()` vazio. |
| Executar ação e resposta do Mundo | `_poll` / `Conversation.execute` | Revalida o plano na execução, calcula aproximação e efeitos, aplica checkpoints/respostas, acumula relatório e solicita continuação de NPCs. |
| Avançar NPCs | `_request_npc_turn` / `_poll` | Chama `world_context()` sem plano do jogador, decide e executa `execute_npc_turn`. Acumula relatórios e repete enquanto houver NPC ativo, jogador com PV e nenhum impedimento. Limita a sequência ao número de criaturas. |
| Pausar turno de NPC | `_poll` | Impedimento ou oportunidade pendente conduz à narração; não repete automaticamente ações já executadas. |
| Escolher oportunidade do jogador | `_choose_opportunity` | Recebe aceitar/recusar, usa `TravelExecutor.resolve`, registra a escolha, retoma `pending_npc_turn` e continua os NPCs ou narra a interrupção. |
| Narrar e entregar | `_request_narration` / `_finish` | Constrói contexto com os fatos atuais; chama o narrador e `Conversation.finish`, atualizando histórico e estado da interface. |
| Falha externa ou plano rejeitado | `_worker` / `_poll` | Encaminha exceção, registra falha na conversa e libera a interface. Falha na narração ou decisão de NPC preserva efeitos já executados e informa resumo/impedimento. |
| Reiniciar | `_reset` | Restaura a sessão, substitui conversa/relatório e estado da ficha, depois solicita abertura novamente. |

As chamadas externas são agendadas em workers e os resultados consumidos no
`poll`; a execução determinística é coordenada pela thread da janela. Essa
distinção deve ser preservada na extração, sem transportar decisões do jogo
para um runner exclusivo dos testes.

## 2. Classificação e matriz de cobertura

“Real” abaixo significa que o corpo do teste chama o componente da aplicação
com serviço real quando autorizado. Não significa que houve aprovação nesta
auditoria. Preparações com planos fixos não contam como interpretação live.

| Suíte | Casos | Classificação atual | Abertura | Interpretação | Mundo | Execução do pedido | Turnos de NPCs | Reações | Narração | Falhas avaliadas |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [contextual_movement](../tests/live/test_contextual_movement.py) | 8 | Contratos de adaptadores e motor, com fluxo parcial | Não | Real | Real | Real, via `Conversation` | Não | Uma oportunidade automática do guarda; sem escolha do jogador | Real, resultado | Impedimentos de movimento, grade e iniciativa; sem recuperação de falha externa |
| [dungeon_interactions](../tests/live/test_dungeon_interactions.py) | 3 | Contratos de adaptadores e motor, com fluxo parcial | Não | Real | Real | Real, via `Conversation` | Não | Respostas do Mundo possíveis; sem cenário dedicado de oportunidade | Real, resultado; uma narração extra de preparação | Sucessos esperados; grade já aberta; sem recuperação de falha externa |
| [openai_movement](../tests/live/test_openai_movement.py) | 7 | Contratos de adaptadores e primitivas, com fluxo parcial | Uma narração inicial isolada | Real em 6 casos | Não | 5 casos executam apenas a primeira etapa; 1 executa plano pela conversa | Não | Não | Inicial isolada e resultado da mensagem mista | Resto de 0,5 m no pedido misto; sem recuperação de falha externa |
| [semantic_interpretation](../tests/live/test_semantic_interpretation.py) | 11 | Contrato do interpretador | Não | Real, sem correção | Não | Não; somente a preparação executa ações | Não | Não | Não | Negações/perguntas não autorizam ação; não exercita tratamento de falha no jogo |
| [interpretation_experiment](../tests/live/test_interpretation_experiment.py) | 6 | Experimento de provedor: contexto mínimo/completo | Não | Real, sem correção | Não | Não | Não | Não | Não | Registra rejeição de interpretação; não exercita recuperação do jogo |
| [schema_order](../tests/live/test_schema_order.py) | 3 | Experimento de provedor: ordem de propriedades do esquema | Não | Duas variantes reais por caso, sem correção | Não | Não | Não | Não | Não | Variante antiga é controle, não precisa acertar; sem recuperação do jogo |

**No passo 2, nenhuma suíte era de fluxo completo conforme a política.** Em particular,
nenhuma usa `MovementWindow` ou uma entrada de aplicação compartilhada que
implemente suas transições; nenhuma chama `Conversation.execute_npc_turn` nem
conduz a confirmação/recusa de uma oportunidade do jogador. Os casos de inatividade
da suíte semântica verificam a intenção `end_turn`, sem executar o encerramento
ou conferir a ação seguinte do guarda.

Também não há caso live que conduza pela coordenação da janela uma mensagem
exclusivamente off, um plano sem etapas ou um pedido recebido com NPC já ativo.
Há perguntas on em suítes de interpretação e uma mensagem mista on/off na suíte
anterior, mas esses casos não exercitam os desvios correspondentes da UI.

A validação não está totalmente ausente dos fluxos parciais: o interpretador
valida sua saída e `Conversation.execute` revalida quando há mensagem atual do
jogador. O que falta é compartilhar também a validação anterior ao Mundo feita
em `_poll`, a seleção das etapas e os demais desvios da janela.

## 3. Cenários, preparação e histórico por suíte

### Movimento contextual

`build_case` lê `pocs/simulador/dungeon.json` e usa `DungeonSession.from_data`,
com o `Scene.from_data` real por baixo. Não usa `simulator.load_session` nem um
map builder alternativo. `FrozenRoller` implementa o contrato de rolagem e fixa
tipo, ordem e valor dos dados, incluindo a preparação.

Grande parte da preparação usa `Conversation.execute` com intenções reais para
caminhar, abrir, investigar, coletar, vestir e ocultar a espada. Os desvios são:

- No caso de oportunidade, abre a porta do banheiro nos dados antes da construção.
  É uma variação explícita submetida ao construtor real, não uma regra substituta.
- Nesse mesmo caso, atribui diretamente `guard_alert=True` e `disguise='failed'`
  antes de iniciar combate por uma operação real.
- No caso de pouco movimento, substitui `session.state` para fabricar o gasto
  anterior de 7,5 m, em vez de percorrer esse movimento no turno.
- No caso do log, substitui `conversation.messages` por
  `tests/fixtures/contextual_movement/investigation_history.json`, histórico real
  congelado. Não há uma entrada compartilhada de restauração de histórico.

O corpo live faz sua própria sequência de `prepare → interpret → decide →
execute → narrate → finish`. Não inclui a abertura nem executa os turnos que
ficarem pendentes. O critério de `ataque-guarda-vence-iniciativa` exige que a
iniciativa termine no guarda e encerra aí a observação: não prova que o guarda
agirá nem que o controle voltará ao jogador.

O caso de oportunidade verifica a reação automática do guarda à caminhada do
jogador, com dano e consumo de reação reais. Isso não cobre o caminho inverso,
que pausa um NPC para o jogador escolher sua própria reação.

### Interações da dungeon

Os três casos carregam o JSON atual por `DungeonSession.from_data` e constroem
`Conversation` diretamente, com a mesma sequência manual dos três adaptadores.

- Grade inicialmente aberta: usa a situação inicial real.
- Grade fechada: prepara aproximação, fechamento e retorno com ações reais,
  mas acrescenta uma frase de narrador escrita no teste por `Conversation.finish`.
  Esse histórico não foi gerado pela IA nem extraído de uma sessão registrada.
- Investigação: prepara deslocamento/abertura pelo motor e usa uma narração real
  dessa preparação para formar o histórico. Essa chamada adicional não equivale
  à abertura da partida. Usa dois d20 fixados em 20; os casos da grade deixam a
  aleatoriedade padrão da sessão.

As asserções verificam efeitos e recursos, mas não exercitam erros de serviço,
retomada de NPC, escolha de reação ou reinício. A consulta `session._passage`
é um acesso privado usado para observação, não um construtor alternativo de estado.

### Movimento e portas anteriores

`test_openai_movement.py` tem três tipos de arranjo:

- Grade 10×10 e estado construídos com `Grid`, `MovementState` e `GameSession`
  reais para movimento simples, narração inicial e mensagem mista.
- Mapa legado `pocs/movimento/cela_guardas.json`, carregado por `Scene.from_data`,
  para destinos nomeados e portas. Monta `GameSession` e criaturas diretamente,
  sem o carregador/composição do simulador e sem carregar explicitamente as
  fichas do JSON por `sheet_from_data`; usa os padrões da sessão.
- Preparação das portas por `session.execute`; para o fechamento chama também
  `session.next_turn`, sem passar pela narração para produzir essa transição.

Nos cinco casos de movimento/destino/porta, pega `plan.steps[0]` e executa só
essa etapa. Um plano que acrescente etapas indevidas pode passar nesses testes,
pois elas são descartadas antes da avaliação. A mensagem mista executa o plano
inteiro por `Conversation`, mas não consulta o Mundo. A narração inicial chama
somente o adaptador e verifica `reply.on`; não usa o fluxo de abertura nem
`Conversation.finish` para registrar a resposta no histórico.

### Interpretação semântica

Usa o mapa legado via `Scene.from_data(...).with_passage(...)` e cria a sessão
diretamente numa posição avançada. O estado inicial passa pelos validadores
reais, mas não reproduz o percurso até essa posição. Inicia combate e faz um
ataque com as primitivas reais para fornecer `last_attack`, com dados controlados.

Obtém `Conversation(session).interpretation_context()` e avalia apenas o plano
devolvido. Confere que interpretar não alterou estado/recursos. Não usa
`Conversation.prepare` para registrar a mensagem no histórico como a UI faz.
`evaluate_plan` exige a quantidade/ordem de etapas esperada e os campos declarados,
portanto é um critério de interpretação específico, não equivalência geral de
efeitos de combate ou movimento.

### Experimentos de interpretação e de esquema

Ambas as suítes carregam `pocs/interpretacao/run.py` por `runpy.run_path` e
usam `scenario_context` / `run_case` desse experimento. O cenário é o mapa legado,
construído com `Scene.from_data`, fichas e criaturas reais. A composição é própria
da POC, sem passar pelo carregador/compositor do simulador.

`run_case` usa o adaptador real e seus parâmetros de experimento, separa on/off
com `split_speech`, copia o contexto e chama interpretação diretamente. Não há
registro da mensagem via `Conversation.prepare`, execução física ou narração.
As expectativas vêm de `pocs/interpretacao/cases.json` e usam `evaluate_plan`.

Não há cópia paralela das regras de mapa nesses helpers. O que varia
deliberadamente é a configuração do pedido: contexto `minimal`/`full`, esquema
`legacy`/`operation-first` e ausência de correção. As instruções vêm do mesmo
adaptador. Esses resultados são evidência dos experimentos, não do fluxo padrão.

## 4. Comparação de configuração e chamadas

Na composição atual do simulador:

- Modelo: `TRAMA_OPENAI_MODEL` ou `DEFAULT_MODEL`, hoje `gpt-5.6-terra`.
- SDK: `OpenAI(timeout=30, max_retries=0)`.
- Interpretador: `context_mode='minimal'`, `max_corrections=1`,
  `schema_order='operation-first'`.
- Transporte compartilhado: Responses API, esforço `low`, JSON Schema estrito,
  `store=False`; saída máxima de 1.000 tokens para interpretação/narração e
  2.000 para decisão do Mundo.

| Suíte | Modelo | Correção de interpretação | Contexto/esquema | SDK e limites de saída |
| --- | --- | --- | --- | --- |
| Contextual | Mesmo processo de resolução, repetido no teste | Padrão: até 1 | Padrões | Mesmos valores atuais, instanciados separadamente |
| Dungeon | Mesmo processo de resolução, repetido no teste | Padrão: até 1 | Padrões | Mesmos valores atuais, instanciados separadamente |
| Movimento anterior | Mesmo processo de resolução, repetido no teste | Padrão: até 1 | Padrões | Mesmos valores atuais, instanciados separadamente |
| Semântica | Usa o default do construtor; **não lê `TRAMA_OPENAI_MODEL`** | **0** | Padrões | Mesmo timeout/retries e transporte |
| Experimento de interpretação | Mesmo processo de resolução, repetido no teste | **0** | **`minimal` e `full`**; `operation-first` | Mesmo timeout/retries e transporte |
| Experimento de esquema | Mesmo processo de resolução, repetido no teste | **0** | `minimal`; **`legacy` e `operation-first`** | Mesmo timeout/retries e transporte |

Igualdade dos valores atuais não significa composição compartilhada. Uma mudança
futura no `main` pode não alcançar as instanciações independentes dos testes.
Nenhuma suíte altera os limites de saída do transporte; as diferenças conhecidas
estão na resolução do modelo semântico e nas opções experimentais/de correção.

Contagem estática das chamadas, supondo que todos os casos alcancem suas etapas:

| Suíte | Casos coletados | Chamadas sem correção | Máximo com correções previstas no código |
| --- | ---: | ---: | ---: |
| Contextual | 8 | 24 | 32 |
| Dungeon | 3 | 10 | 13 |
| Movimento anterior | 7 | 8 | 14 |
| Semântica | 11 | 11 | 11 |
| Experimento de interpretação | 6 | 6 | 6 |
| Experimento de esquema | 3 | 6 | 6 |
| **Total** | **38** | **65** | **82** |

São estimativas por leitura dos caminhos, não medições, autorização de execução
ou um orçamento global implementado. Uma falha pode terminar o caso antes.
O `max_retries=0` é do transporte SDK; a correção declarativa do interpretador
é outro mecanismo e pode produzir uma segunda chamada nos casos indicados.

## 5. Evidências, falhas e limites da avaliação

| Suíte | Evidências implementadas | Limite importante |
| --- | --- | --- |
| Contextual | `logs/live/contextual_movement/<execução>/<caso>/trace.jsonl` e `result.json`; IDs explícitos, fases, contextos, planos, estado, rolagens e erro; gravação em `finally` | Artefatos persistentes também em falha, mas não incluem turnos/retomadas nunca executados. Narração é verificada por presença de texto/on conforme o resultado, sem avaliação automática completa dos fatos narrados. |
| Dungeon | `trace.jsonl` em `tmp_path`, salvo em `finally`; JSON da interação/investigação após a sequência | Se houver exceção antes de concluir a sequência, o trace é salvo, mas o JSON de resultado não chega a ser escrito. Sem snapshot completo antes/depois no artefato dedicado. |
| Movimento anterior | Asserções e logs emitidos pelos módulos | Não configura captura persistente própria, não salva planos/contextos/estado em artefatos dedicados. Narração é verificada de forma limitada. |
| Semântica | Trace e avaliação em `tmp_path`; estado/recursos conferidos em memória | Exceção antes de `evaluate_plan` impede gravar `result.json`; não verifica execução do plano nem fatos narrados. |
| Experimento de interpretação | Trace em `tmp_path`; `result.json` com variantes, candidatos e avaliação | Rejeição de interpretação é registrada por `run_case`; outras exceções podem impedir o resumo. Não testa recuperação da conversa. |
| Experimento de esquema | Trace em `tmp_path`; `results.json` das duas variantes | A aprovação exige somente a variante `operation-first`; o controle antigo pode falhar. Não verifica efeitos no mundo. |

Todos os módulos usam o marcador `live`, exigem `RUN_OPENAI_LIVE_TESTS=1` e
verificam a presença de `OPENAI_API_KEY` antes de chamar o serviço. A coleta não
exige esses valores nem faz chamadas. Capturar exceções para salvar logs ou
deixar o pytest reprovar o caso não equivale a testar a recuperação implementada
na janela. Falhas externas, resposta inválida do narrador, reinício e retomadas
não têm cenários live dedicados entre os 38 casos auditados.

## 6. Pendências que a migração precisa resolver

1. **Fluxo único:** extrair as transições da janela e conectar o simulador antes
   de migrar os testes. Compartilhar componentes ainda deixa a ordem sob o
   controle de cada teste.
2. **Carregamento/composição únicos:** remover as montagens paralelas de sessão
   e adaptadores, preservando as variações de dados e os experimentos explícitos.
3. **Preparação validada:** substituir atribuições diretas de estado; compartilhar
   a entrada de histórico e identificar o trecho de histórico redigido no teste.
4. **NPCs e reações:** os testes completos precisam avançar NPCs e fornecer escolhas
   públicas de oportunidade quando previstas. O caso de iniciativa hoje para
   justamente antes da ação do guarda.
5. **Plano inteiro:** preservar a avaliação de todas as etapas nos testes que
   pretendam garantir comportamento, em vez de descartar `steps[1:]`.
6. **Configuração efetiva:** unificar resolução do modelo e registrar exceções
   deliberadas de correção/contexto/esquema. A suíte semântica hoje pode chamar
   um modelo diferente do selecionado para o simulador.
7. **Critérios e evidências:** manter oráculos independentes e melhorar, no escopo
   migrado, as garantias sobre fatos narrados e a gravação de resultados em falha.

Essas pendências foram identificadas, não corrigidas neste passo. Experimentos
isolados continuam úteis com sua classificação explícita; não precisam simular
uma partida completa para comparar variantes de um pedido ao provedor.

## 7. Verificação desta auditoria

Comando executado, sem serviços externos:

```bash
poetry run pytest tests/live --collect-only -q
```

Resultado: **38 casos coletados em seis arquivos**. Os parâmetros e caminhos
foram conferidos por leitura do código, incluindo os auxiliares chamados por
`runpy`. Nenhum teste live foi executado e não se inferiu taxa de sucesso a
partir da coleta. Não houve alteração no comportamento da aplicação ou dos testes.

# Fluxo do jogo e modos

Tier 3 · [Aplicação](README.md) · [Visão geral](../../../README.md)

## Coordenador de aplicação

`application/game_flow.py` implementa `GameFlow`, extraído da coordenação da
janela. Recebe a sessão e os contratos de interpretador, diretor do Mundo e
narrador. Não importa Pygame, CLI ou SDK, nem redefine regras de movimento,
combate ou contexto: delega a `Conversation`, à sessão e ao executor de viagens.

As projeções publicadas por `Conversation` são `AIContext` validados por fase.
O marcador de tipo fica fora do JSON e acompanha os snapshots dos workers.
Veja [campos, limites de informação e revisão dos contratos](../ia/contextos-e-contratos.md).

| Entrada pública | Comportamento |
| --- | --- |
| `start()` | Solicita a descrição inicial uma vez, a partir de `idle`. |
| `submit(text)` | Separa on/off e conduz a mensagem. Ignora entrada vazia ou envio durante uma chamada pendente. |
| `pending_request` | Pedido externo escolhido pelo fluxo, com id, etapa, prompt quando aplicável e snapshot do contexto. |
| `pending_request.run()` | Chama apenas o adaptador com cópia do contexto; devolve resposta ou exceção, sem alterar sessão/conversa. Pode rodar em worker. |
| `receive(id, result)` | Valida tipo/etapa e aplica o resultado na thread dona; escolhe a próxima etapa. Resultados antigos ou duplicados são ignorados. |
| `check_owner()` | Confere a thread dona antes de uma agenda síncrona despachar pedidos. |
| `choose_opportunity(accept)` | Resolve aceitar/recusar e retoma somente as ações restantes do NPC. |
| `reset()` | Restaura sessão e conversa, invalida pedidos antigos e solicita nova abertura. Não cancela a chamada de rede já iniciada; sua resposta deixa de ser aplicável. |

`start`, `submit`, `receive`, `choose_opportunity` e `reset` devem rodar na thread
que construiu o fluxo; outra thread recebe `GameFlowError` antes de alterar o
estado. O consumidor só agenda o pedido já escolhido, sem selecionar etapas:

```python
request = flow.pending_request
if request is not None:
    result = request.run()              # pode executar no worker
    flow.receive(request.id, result)    # de volta à thread dona
```

Esse trecho agenda **uma chamada**. Cada pedido deve ser despachado uma vez;
repetir `run()` faria outra chamada ao provedor. A proteção de `receive` impede
aplicar duas vezes o resultado, sem prometer eliminar custo de chamadas que um
consumidor repetiu. O coordenador não cria threads, filas nem um loop de eventos.
Os logs `game_flow.*` e os adaptadores mantêm os identificadores de correlação
mesmo quando a chamada é executada em outra thread.

As etapas externas são `interpret`, `world`, `npc_turn` e `narrate`. `FlowStatus`
informa a situação da interação:

| Status | Significado |
| --- | --- |
| `idle` | Fluxo recém-criado, sem interação iniciada. |
| `pending` | Há uma chamada externa a agendar/aguardar. |
| `awaiting_reaction` | A resposta foi entregue e o movimento aguarda escolha de oportunidade. |
| `completed` | A resposta da interação foi entregue. Não significa sucesso de toda ação nem vitória no jogo. |
| `failed` | Erro de entrada, contrato ou serviço, disponível em `error`, `message` e na conversa. Efeitos anteriores permanecem. |

`report.status` e seus impedimentos informam se a ação física foi concluída ou
barrada. Assim, uma ação bloqueada pode ter sua explicação narrada e a interação
terminar em `completed`. `awaiting_reaction` também é uma propriedade: continua
verdadeira quando uma falha de narração deixou uma escolha legítima pendente.
Os booleanos retornados por entradas indicam que foram recebidas/processadas,
não que a ação teve sucesso; leia `status`, `report` e `error`.

O fluxo mantém as seguintes decisões:

- Pergunta exclusivamente off só narra; não interpreta nem avança NPCs.
- Plano sem etapas, validado como pergunta/negação, segue para narração sem
  consultar o Mundo. O adaptador conserva a política existente de correção de
  interpretação; o coordenador não acrescenta retries.
- Um NPC já ativo é resolvido antes de interpretar o pedido on recebido. O
  pedido original é preservado se houver pausa para reação e perguntas off.
- Depois da execução do jogador, resolve os turnos de NPCs até devolver o
  controle, encontrar impedimento ou o jogador ficar com 0 PV. Há um limite de
  sequência pelo número de criaturas, como proteção contra turnos repetidos.
- Uma oportunidade pendente pausa a continuação. Resolver a escolha preserva
  os efeitos parciais e remove somente o impedimento de escolha já resolvido;
  outros impedimentos continuam no relatório. Não pede um novo plano para
  repetir o trecho do NPC que já foi executado.
- Destino além do movimento disponível do NPC produz `movement_limited`, com
  percurso/custo reais, `stop_code=insufficient_movement`, motivo em
  `movement_limit_reason` e `stop_reason=null`. As ações seguintes ainda passam
  pelas validações normais; gastar movimento não impede um ataque ao alcance.
- Se uma ação de um plano de NPC falha durante a execução, preserva efeitos e
  falhas estruturadas, descarta o restante e encerra o turno com
  `fallback=end_turn`. O fluxo segue para o próximo participante, sem nova
  decisão da IA ou renovação de recursos dentro do turno. É uma política de
  recuperação do Trama, não uma regra adicional de D&D. O relatório mantém a
  causa; `turn_pending` só é verdadeiro quando o ator ainda tem o turno ativo.
- Falha de narração não desfaz nem repete execução. Falha numa decisão de NPC
  mantém o turno pendente e os efeitos dos NPCs anteriores, sem repetir chamadas
  automaticamente.

Essa última situação inclui indisponibilidade do provedor e rejeição do contrato
do plano antes da execução; não se inventa uma decisão para esses casos. As
regressões e a bateria paga focada estão em [turnos de NPCs](../qualidade/turnos-npc-live.md).

Sem interpretador, pedidos on recebem erro explícito. Sem narrador, a execução
pode fornecer um resumo local em off, identificado como indisponibilidade; a
abertura informa o erro de configuração. Sem diretor do Mundo, o fluxo usa uma
resposta vazia para a ação do jogador, sem inventar ações ou avançar NPCs por ele.

`tests/integration/test_game_flow.py` cobre esses caminhos com os construtores e
regras reais, rolagens controladas e adaptadores locais. Também verifica a
correção do interpretador real com transporte simulado, separação de threads,
snapshots, correlação e proteção contra resultados repetidos/anteriores ao reset.
Não há chamadas pagas nesses testes.

## Fluxo de uma mensagem

1. A aplicação separa falas on/off. Somente o on pode propor ação.
2. O interpretador traduz a intenção do Jogador: caminhar, abrir/fechar, atacar,
   usar um recurso, encerrar seu turno ou uma intenção narrativa (observar,
   falar, esperar). Recebe contexto mínimo e não decide respostas dos guardas.
   Registra trechos literais e sua classificação em `request_parts`. O código
   verifica origens, referências e consistência declarativa, sem interpretar
   verbos. Inconsistência permite uma correção; persistindo, não executa o plano.
3. O diretor do Mundo recebe o cenário, o histórico on e a proposta do Jogador.
   Decide se há resposta: falas, ações de NPCs, teste de Percepção ou interrupção.
   Uma lista vazia significa que o Mundo não tem ação a executar; o novo local
   ainda será descrito ao jogador.
4. Na thread principal, a aplicação executa a proposta e as respostas nos pontos
   indicados, validando os efeitos. Preserva o progresso até um impedimento.
5. Se a iniciativa chegar a um NPC, a aplicação consulta uma decisão para esse
   NPC, executa-a e encerra seu turno. Repete até a vez do Jogador. Uma decisão
   inválida interrompe sem repetir automaticamente golpes ou chamadas.
6. O narrador recebe estado atual, percepção, ações realizadas e respostas
   validadas. Descreve a situação em on e responde dúvidas/impedimentos em off.

Descrição inicial e perguntas exclusivamente off fazem somente a chamada de
narração. Uma mensagem com ação faz normalmente três chamadas. Cada turno de NPC
acrescenta outra decisão do Mundo. Não há chamadas extras para gerar logs.
Uma pergunta reconhecida na mensagem on pode retornar um plano sem etapas:
nesse caso, após interpretar, o fluxo solicita a resposta off do narrador sem
consultar o Mundo. Postura, como ficar de frente para a sala, é detalhe narrativo
sem custo; não impede movimento nem adiciona uma regra de orientação.

O contrato de ações não possui uma operação genérica `narrative`. Caminhar em
qualquer modo é executado como `move`, com destino ou percurso, inclusive quando
preparado pela aplicação para abrir/fechar uma passagem. Interações sem alteração
mecânica usam operações específicas: `look`, `speak`, `wait` ou `challenge`.
Um pedido misto de caminhar e falar deve produzir duas etapas distintas.

No relatório, `progress` indica mudança efetiva do estado do Jogador;
`narrative_interaction` indica uma interação que pode receber resposta, mesmo sem
alterar o estado. O narrador recebe `execution.player_movement` com ocorrência,
distância real e posições inicial/final. Uma intenção de caminhar escrita em texto
não autoriza narrar deslocamento se esse resumo indicar que ele não ocorreu.
O mapa desenha a posição validada pela aplicação, nos dois modos.

## Abordagem antes da iniciativa

Uma ordem que exige resposta pode interromper a ação em modo narrado. `parley`
registra interlocutor e posições de detecção; o NPC aguarda a resposta sem ganhar
aproximação gratuita. Uma fala pode receber avaliação de disposição e Influence:
aceitar ouvir mantém custódia e posição; recusa/falha não inicia combate sozinha.
Ataque explícito pode iniciar combate diretamente. Perguntas off preservam a
abordagem. Veja [contrato, referências e limites](conversa-antes-do-combate.md).

## Modos

- **Narrado** (`narrated`): padrão inicial. Não há limite de deslocamento ou
  interações por mensagem/turno. Velocidade não limita uma caminhada até um
  destino. Obstáculos, ocupação, alcance e recursos de classe continuam válidos.
  “Todo meu movimento” usa a velocidade como distância pedida (9 m aqui);
  “caminho até a porta” percorre todo o caminho acessível. Esta é uma decisão
  de fluxo do usuário; não implementa ainda tempos de viagem ou fadiga.
- **Por turnos** (`turn_based`): um ataque válido ou uma resposta de conflito do
  Mundo inicia iniciativa. O código calcula a ordem antes de resolver ataques.
  Movimento, ações, bônus e reações seguem as regras já implementadas. Se um
  NPC ganha iniciativa, o ataque do Jogador ainda não acontece: os NPCs agem e
  a vez volta ao Jogador, que escolhe sua ação. Declarar que fica parado, não faz
  mais nada ou aguarda, sem outra ação na mensagem, expressa passar a vez. A IA
  propõe `end_turn`, inclusive com recursos disponíveis; não exige a frase
  “encerro meu turno”. “Fico parado e uso Retomar o Fôlego” pede o poder sem
  encerrar. “Ataco e depois não faço mais nada” pede ataque e fim do turno.
  A aplicação não encerra o turno do Jogador apenas porque uma ação foi gasta:
  ele ainda pode ter movimento, bônus ou Surto de Ação.

Um NPC pode encerrar conflito por causa narrativa explícita, como trégua. Isso
remove a iniciativa e os limites de turno; não cura nem recupera recursos de
classe. Um ataque que deixa todos os inimigos com PV zerados encerra o combate automaticamente.
Não existem botões para iniciar combate ou renovar turno.

## Referências e validação

PHB 2024: Playing the Game (exploração, interação social, combate e iniciativa),
D20 Tests / Ability Checks (CD determinada pelo mestre), perícia Perception
(Wisdom), e regras de [movimento](../regras/movimento.md) e
[ações](../regras/acoes.md). O modo narrado
sem orçamento artificial e os pontos de interrupção são decisões de fluxo
solicitadas pelo usuário. Não há motor completo de condições, morte, surpresa,
viagem ou audição neste incremento.

`tests/integration/test_world_flow.py` usa decisões fixas e dados controlados;
os testes da janela verificam as três etapas, execução local e turnos de NPCs.
Nenhum teste padrão usa rede, credenciais ou chamadas pagas.

# Jogador, Mundo e modos de jogo

O usuário controla o Jogador. A IA controla o Mundo. O Python valida regras e
altera o estado; a narração descreve o retorno do Mundo e os resultados reais.

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
nesse caso, após interpretar, a janela solicita a resposta off do narrador sem
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

## Respostas do Mundo

`WorldPlan` é separado de `ActionPlan`. Cada `WorldReaction` aponta para uma
etapa do Jogador (`step_index`, base zero) e um ponto de execução:

- `after_squares=0`: antes da etapa;
- inteiro positivo: após essa quantidade de casas realmente percorridas na etapa;
- `null`: depois da etapa concluída.

Se uma porta ou o saldo de combate impedir alcançar o ponto, a resposta não
dispara. Trechos anteriores ficam realizados; portas e criaturas são verificados
de novo ao prosseguir. `interrupt` exige uma justificativa do Mundo. Ouvir passos
ou falar não interrompe automaticamente uma caminhada. Iniciar conflito pausa
a ação para respeitar a iniciativa.

NPCs existentes podem falar, mover-se, abrir/fechar passagens, aguardar, atacar
corpo a corpo e iniciar/encerrar conflito. A IA não pode mover o Jogador, atravessar
paredes, atacar fora de alcance ou ignorar a ordem e os recursos de turno. Um
deslocamento de NPC usa a mesma busca de caminho de menor custo do Jogador,
respeitando paredes, quinas, terreno difícil e casas ocupadas. A IA escolhe o
destino; o Python encontra o percurso. A casa de uma porta aberta pode ser ocupada.
Sem caminho livre, uma rota arquitetônica permite aproximar-se de uma porta
fechada, mas a execução para nela, sem abri-la ou atravessá-la. Sem rota até o
destino, a ação é rejeitada. Isso não escolhe alvos ou táticas pelo NPC.

Se um movimento parar antes do destino, inclusive por saldo insuficiente no
turno, o relatório preserva a posição, o custo e o motivo da parada. As ações
seguintes da resposta não são executadas, evitando tentar um ataque cuja
aproximação falhou. Em turno de NPC, o fluxo pausa sem avançar a iniciativa ou
repetir automaticamente a decisão. Os logs incluem o percurso encontrado e
`world.reaction_interrupted` com motivo e quantidade de ações restantes.

Uma resposta pode depender de `PerceptionCheck`: o código rola d20 + Percepção,
compara com a CD proposta (1 a 30 neste recorte) e só executa as ações condicionadas se passar. A CD é
uma decisão do mestre contextualizada em `reason`. Não há regra inventada de
distância fixa para ouvir passos através de uma porta. Os testes do Jogador
continuam fora dos comandos deste incremento.

Descrições e falas são narrativas. Alterações mecânicas exigem operações
estruturadas. `describe` não cria objetos, obstáculos ou condições persistentes;
novos tipos de alteração do Mundo precisam de implementação própria.

## Contexto e logs

O narrador recebe `execution` para a execução atual e `previous_execution` para
a tentativa anterior do motor, inclusive quando rejeitada sem efeitos. O registro
contém id, ator, relatório e uma fotografia da situação ao final: modo, rodada,
vez ativa, posição do Jogador e se o turno ficou pendente. Ao narrar uma execução
atual, ela não é repetida como anterior. Ao fazer uma pergunta sem executar ações,
o registro mais recente aparece como anterior, mesmo se o histórico já o omitiu.

`execution.failures` contém dados de aplicação: ator, operação, código, mensagem
original, causa concreta conhecida, posição inicial, destino, posição após a
tentativa, obstáculo e ações seguintes que não foram executadas. Códigos de
movimento vêm do cálculo ou da busca de caminho; o texto do erro não é analisado
para adivinhar a causa. Uma casa ocupada por um guarda com 0 PV é registrada como
ocupação, sem inventar parede. O relatório também conserva progresso parcial.

Perguntas off ou planos só de perguntas não substituem a última execução. Novas
tentativas de execução do Jogador/NPC a substituem; reiniciar a sessão limpa o
registro. Falha do serviço de narração não apaga efeitos nem o resultado salvo.
Isso é memória em processo, não persistência do jogo em disco. Erros de serviço
ou validação antes de executar continuam nas mensagens e logs; não são tratados
como uma nova execução física do mundo.

Ao explicar uma ação impedida, o narrador deve apresentar causa e consequência,
incluindo etapas puladas e o turno pendente, usando os dados registrados. Não deve
atribuir novas ações ao registro anterior, inventar motivos, repetir ataques nem
avançar a iniciativa para responder. A redação continua sendo da IA; os testes
locais verificam que ela recebe fatos completos, sem garantir toda resposta real.
`conversation.execution_recorded` correlaciona o id da execução, os impedimentos
e a situação final nos logs, sem gerar chamadas adicionais ao modelo.

`MODE_INSTRUCTIONS`, em `application/modes.py`, contém o texto fixo compartilhado
pelos três adaptadores. O contexto completo contém `mode`, mapa, personagem, fichas,
combate, histórico e `world`, com todos os NPCs deste pequeno cenário, inclusive
ocultos. Não há seleção ou recuperação externa de contexto neste incremento.
O interpretador recebe uma projeção pequena desses dados. O Mundo mantém o
contexto completo. Veja [a autorização de planos](action-authorization.md).

O campo de visão e `perception` continuam separados: fatos conhecidos pela IA
como mestre não são automaticamente conhecidos pelo Jogador. O narrador só deve
revelar criaturas vistas e acontecimentos marcados como perceptíveis; falas
audíveis podem ser percebidas sem visão. A coerência de ocultação em texto depende
do cumprimento dessas instruções pelo modelo; a interface filtra a visão por código.

Com `--debug`, ficam registrados os pedidos completos de interpretação, decisão
do Mundo e narração, além das decisões e dos efeitos. Eventos `world.*` incluem
atores, testes, respostas e interrupções, usando a mesma correlação dos demais
módulos. Não há acesso aos pensamentos internos do modelo.

## Referências e validação

PHB 2024: Playing the Game (exploração, interação social, combate e iniciativa),
D20 Tests / Ability Checks (CD determinada pelo mestre), perícia Perception
(Wisdom), e regras de movimento/ações já documentadas na POC. O modo narrado
sem orçamento artificial e os pontos de interrupção são decisões de fluxo
solicitadas pelo usuário. Não há motor completo de condições, morte, surpresa,
viagem ou audição neste incremento.

`tests/integration/test_world_flow.py` usa decisões fixas e dados controlados;
os testes da janela verificam as três etapas, execução local e turnos de NPCs.
Nenhum teste padrão usa rede, credenciais ou chamadas pagas.

## Aproximação de criaturas e oportunidades

Criaturas visíveis também são destinos de `move`: a aplicação busca uma casa
livre adjacente à posição atual do alvo, sem entrar no espaço dele. Os números
exibidos no mapa são enviados à interpretação junto do id e nome. Aproximar-se
e atacar continuam etapas distintas, cada uma validada antes de executar.

Durante movimentos em conflito, o coordenador de deslocamento verifica saídas
do alcance antes de cada passo que possa provocar oportunidade. A reação usa a
mesma resolução de ataque, sem gastar a ação normal nem exigir que seja o turno
de quem reage. Se o Jogador confirmar ou recusar uma oportunidade pendente,
somente a parte ainda não realizada do turno do NPC é retomada. Veja
[regras, escolha e limitações](opportunity-attacks.md).


## Cenário do simulador

A dungeon de quatro celas usa `DungeonSession` sobre a sessão existente. Suas
interações e respostas do roteiro são adjudicadas no código e publicadas em
`execution.reactions`. O contexto `scenario` declara as operações adicionais ao
interpretador; `world.scenario` contém estado completo, segredos e decisões de
mestre. Na exploração, o diretor é instruído a não duplicar essas respostas.
Os turnos de combate do guarda continuam passando pelo diretor e pelo executor
do Mundo. A interface consome uma projeção `map_view()`, sem acessar o estado
privado do cenário. Veja [escopo e regras da dungeon](../pocs/simulador/README.md).


## Movimento contextual e requisitos espaciais

Uma ação do Jogador pode pedir apenas seu objetivo. A própria implementação
publica um `SpatialRequirement`, consultável sem rolagens ou efeitos, com o tipo
de condição, alvo e posições válidas. O coordenador não conhece a lógica da
Cela 4, inventários ou classes para calcular a caminhada.

| Ação | Requisito |
| --- | --- |
| Investigar | Estar dentro da área referida |
| Pegar | Estar ao alcance do objeto conhecido |
| Atacar | Estar no alcance corpo a corpo e com linha de visão |
| Abrir/fechar, destrancar, escutar | Estar ao alcance da passagem |
| Acordar | Estar ao alcance do prisioneiro ou da sua grade |

`GameSession` publica requisitos de portas e ataques; `DungeonSession` publica os
das interações do cenário. `application/preparation.py` só calcula o percurso
sobre a grade de navegação e devolve `PreparedMovement`. A execução reutiliza
movimento, checkpoints, oportunidades e respostas do Mundo. Não há nova chamada
à IA para inserir uma microetapa. Um movimento explícito anterior não se duplica.

Antes de caminhar, `validate_preparation` verifica condições conhecidas: alvo,
visibilidade necessária, arma possuída, inspiração solicitada, chave e orçamento
de ação/interação. Não se gasta um recurso para validá-lo. Uma fechadura ainda
não examinada continua sendo descoberta na tentativa de interação; não se revela
um segredo apenas porque o motor conhece o estado completo.

Se uma aproximação contextual de ataque começa fora de combate, a aplicação
rola iniciativa antes de caminhar. Se um NPC agir primeiro, a tentativa para
sem movimento/ataque gratuito; o fluxo normal resolve os turnos de NPCs e o
Jogador volta a escolher sua ação quando tiver a vez. Se o Jogador agir primeiro,
a aproximação usa seu saldo de turno, sem Dash implícito. Se o saldo acabar,
conserva-se o percurso e a ação de ataque não é consumida. Pedidos de Surto de
Ação seguidos de ataque continuam ordenados: o poder concede o recurso antes da
validação do ataque; ele não concede movimento adicional automaticamente.

Depois do percurso, as condições são verificadas novamente e a primitiva valida
alcance/posição e executa a ação. Se o alvo mudou, a aproximação não vira uma
perseguição automática. O movimento já executado permanece registrado. A regra
primitiva `GameSession.execute` continua exigindo a posição correta; a
coordenação é de `Conversation.execute`, não do core de portas ou combate.

`allow_approach=false` em portas, ataques e interações de cenário proíbe movimento
contextual. A IA reconhece restrições como “sem sair do lugar” e publica o campo;
o Python o aplica sem analisar verbos. O campo controla aproximação implícita,
não cancela um movimento que o Jogador explicitamente pediu em outra etapa.

Uma operação já satisfeita não exige aproximação, gasto ou interrupção do plano.
Abrir uma grade já aberta e fechar uma já fechada são reconhecidos antes de
cobrar alcance. Destrancar uma já destrancada e acordar alguém já acordado também
são `already_satisfied`. No simulador isso não avança a rotina do banheiro nem
revela a fechadura à distância. Movimento protegido de crítico não é perdido por
essas operações sem alteração.

Os relatórios distinguem `completed`, `already_satisfied` e `blocked`. O último
pode coexistir com progresso parcial. `execution.player_movement` inclui a
aproximação; cada evento preparado aponta para a ação original com
`preparation_for`. A narração descreve somente os efeitos calculados.

O contexto do Mundo mantém os índices do plano original, publica
`spatial_requirement` e o percurso previsto em `preparation`.
`initiative_before_movement` sinaliza a preparação tática de um ataque. Os
checkpoints positivos contam casas da aproximação; `after_squares=null` ocorre
somente depois da ação. O percurso é recalculado quando a etapa é alcançada.
O motor não abre barreiras intermediárias, destranca, gasta poderes ou usa Dash
por conta própria. Alçapões novos não foram implementados neste incremento: os
checkpoints continuam disponíveis para impedimentos de Mundo já modelados.

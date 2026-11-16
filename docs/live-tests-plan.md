# Plano para live tests compartilharem o fluxo do simulador

## Objetivo e situação atual

Queremos que o simulador e os testes percorram a mesma aplicação. Uma alteração
em mapas, regras, contexto ou coordenação deve chegar aos dois caminhos sem
atualizar uma implementação paralela de teste.

Hoje, `tests/live/test_contextual_movement.py` constrói a dungeon real por
`application.scenarios.build_session`, também usado por `load_session` no
simulador. Ele delega a `DungeonSession.from_data` e `Scene.from_data`. Não existe um gerador de
mapas exclusivo dessa suíte. Ela também reutiliza `Conversation`, intenções,
regras, projeções de contexto, instruções, esquemas e adaptadores reais.

Os oito casos contextuais agora usam `open_game` e `game.runner`, com o mesmo
`GameFlow` da janela. A composição/configuração, a preparação por operações
públicas e a entrada validada de histórico são compartilhadas. O teste só declara
entradas, observa resultados e confere critérios; NPCs e narração são coordenados
pela aplicação. As outras cinco suítes mantêm os limites parciais/experimentais
registrados no inventário.

Este documento é um plano de trabalho. Os passos 1 a 12 estão concluídos: política,
inventário, carregamento e coordenador estão disponíveis, a janela usa esse
coordenador, os contratos de contexto têm validação e revisão offline e os
arranjos contextuais têm preparação reproduzível validada. A composição dos serviços
é compartilhada e registra a configuração efetiva. A execução sem janela está
disponível pelo mesmo fluxo e adotada pelos oito casos contextuais. Controles
offline demonstram a detecção das regressões motivadoras. O
[experimento do passo 12](experiments/step12-20261116T205209Z.md) executou os oito
casos contextuais uma vez: oito aprovações mecânicas, 33 chamadas reais, sem
repetições e com ressalvas de narração registradas. As outras cinco suítes
continuam com cobertura parcial/experimental; não foram executadas nessa bateria.

O objetivo de reúso não inclui gerar as expectativas pela própria aplicação:
dados iniciais, mensagens, rolagens e resultados esperados continuam pertencendo
ao experimento. Compartilhamos a execução e mantemos uma avaliação independente.

## Passos de implementação

### 1. Documentar e adotar a política dos live tests

**Concluído.** A [política](live-tests-policy.md) define fonte única
da execução, preparação permitida, contratos de contexto, critérios independentes,
evidências e limites da confiança em IA real. O `AGENTS.md` exige sua leitura antes
de criar, alterar ou executar live tests; os READMEs apontam para ela.

**Aceite:** quem entrar no repositório encontra a política antes de acrescentar
um caso. As suítes existentes não são declaradas conformes sem auditoria.

### 2. Inventariar os caminhos e classificar as suítes existentes

**Concluído.** O [inventário dos fluxos e das suítes](live-tests-audit.md) registra
as transições da janela, a matriz de cobertura dos seis arquivos e 38 casos,
preparação/histórico, configurações, evidências e pendências. Naquela auditoria,
nenhuma suíte foi classificada como fluxo completo. Foram usadas leitura e coleta offline,
sem chamadas à IA.

Listar as transições hoje distribuídas em `MovementWindow.start`, `submit`,
`poll`, `_request_npc_turn`, `_choose_opportunity` e `_reset`. Compará-las com
as chamadas de cada arquivo em `tests/live/`.

Classificar cada suíte como fluxo completo, contrato de adaptador ou experimento
de provedor. Manter os testes isolados úteis, deixando explícito o que não cobrem.
Registrar também preparação direta de estado, histórico substituído e diferenças
de parâmetros do SDK/modelo.

**Aceite:** uma matriz mostra, por suíte, abertura, interpretação, Mundo,
execução, NPCs, reações, narração e falhas realmente percorridos.

### 3. Compartilhar o carregamento e a construção do cenário

**Concluído.** `application/scenarios.py` contém `load_session(path)` e
`build_session(data)`, usados pelo simulador, pelos live tests e pela POC de
interpretação. Mantém os construtores e validadores existentes e a injeção de
rolagens. `simulator.py` reexporta os carregadores anteriores por compatibilidade.
As variações de porta/posição são dados anteriores à construção. Não há um
map builder alternativo nos testes live. Regressões offline cobrem os três mapas
existentes, grade simples, variações válidas/inválidas, ligação com a CLI e
independência de Pygame/SDK/CLI no carregamento. Não foram feitas chamadas pagas.

Extrair de `simulator.py` somente o carregamento necessário para uma função
independente de CLI, Pygame e SDK, por exemplo em `application/scenarios.py`.
Simulador e testes passam a usar essa função, que continua delegando a
`DungeonSession.from_data`, `Scene.from_data` e às estruturas reais de fichas,
passagens e objetos. Não criar outro map builder para os testes.

O cenário-base continua em `pocs/simulador/dungeon.json`. Variações dos testes
são dados explícitos, aplicados antes da construção e submetidos aos mesmos
validadores. Se a aplicação ganhar um construtor de mapas futuramente, este
mesmo ponto de entrada deverá utilizá-lo. Não precisamos criá-lo agora.

**Aceite:** mudanças em geometria, objetos, fixação, bloqueios, fichas ou
validações chegam aos dois consumidores. Nenhum helper do teste reconstrói o mapa.

### 4. Extrair a coordenação do jogo para a aplicação

**Concluído.** `GameFlow`, em `application/game_flow.py`, coordena abertura,
mensagens, execução, NPCs, reações, narração e reinício, com os contratos existentes.
Expõe pedidos externos separados da aplicação de seus resultados na thread dona;
ids protegem contra entregas repetidas ou anteriores ao reinício. As regressões
offline verificam efeitos reais, erros, retomadas, snapshots e correlação, sem
chamadas pagas. A [API e seus estados](game-flow.md#coordenador-de-aplicação)
estão documentados. A conexão com a janela foi concluída no passo 5; os live
tests ainda não foram migrados para essa entrada.

Criar um coordenador pequeno, por exemplo `GameFlow` em
`application/game_flow.py`, extraindo o comportamento existente da janela.
Ele usa `Conversation` e os contratos dos adaptadores, sem importar Pygame ou o
SDK da OpenAI. Não duplicar regras já presentes na sessão e nos executores.

Sua interface pública precisa permitir abertura, envio de mensagem, decisão de
reação e reinício, além de informar conclusão, erro ou espera por escolha do
jogador. A sequência interna deve preservar:

- separação on/off e histórico;
- interpretação, validação e correção já previstas;
- decisão do Mundo e execução determinística;
- turnos dos NPCs até devolver o controle ao jogador;
- pausa e retomada de oportunidades, sem repetir efeitos;
- narração com os fatos executados e preservação do estado quando ela falhar.

A extração deve manter as mutações sob o controle da thread dona da sessão.
Chamadas externas podem continuar em workers. A agenda de execução pode variar
entre janela e execução sem interface; as decisões sobre a próxima etapa ficam
no coordenador compartilhado. Não criar uma arquitetura de agentes ou um motor
genérico de workflows para essa extração.

**Aceite:** nenhum consumidor precisa decidir por conta própria quando chamar o
Mundo, avançar um NPC ou narrar.

### 5. Fazer o simulador utilizar o coordenador primeiro

**Concluído.** `MovementWindow` delega abertura, mensagens, reações e reinício a
`GameFlow`; sua coordenação anterior foi removida. A UI mantém desenho, edição,
rolagem e agenda de workers, com despacho único por id e entrega dos resultados
ao fluxo na thread principal. Estado do jogo/conversa/relatório é consultado
pelo coordenador. As regressões anteriores passaram pela entrada real de
mensagens; novos testes verificam delegação, threads, respostas antigas/duplicadas,
reinício, falha de agenda, retomadas e equivalência com a entrada direta do fluxo.
Não foram executadas chamadas pagas. A migração live continua nos próximos passos.

Adaptar `MovementWindow` para traduzir eventos de interface em chamadas públicas
do fluxo e exibir seu estado. Deixar na UI entrada de texto, desenho, rolagem da
conversa e integração com a agenda de workers. Remover a coordenação equivalente
que foi extraída; manter os testes locais existentes como regressão.

**Aceite:** o caminho que o jogador usa já depende de `GameFlow` antes de migrar
os live tests. Mover código para `src/` sem conectá-lo ao simulador não atende ao
objetivo.

### 6. Explicitar os contratos de contexto por fase

**Concluído.** `application/context_contracts.py` declara as seis fases, campos,
origem e tipos; `Conversation` produz `AIContext` validado. Os adaptadores
preservam a projeção preparada e verificam seu tipo de fase. A
[documentação dos contratos](ai-contexts.md) descreve informação permitida,
nulabilidade e revisão. `tools/context_contracts.py --check` e a suíte offline
comparam declarações, projeções atuais, textos, instruções e esquemas com a
referência em `docs/contracts/ai-contexts.json`, incluindo ordem de propriedades.
Atualizar exige `--update --reason`; a referência não alimenta a aplicação.
As regressões verificam campo novo chegando à chamada real, limites de informação,
mudanças de instrução/esquema, normalização de ids e ausência de leitura da
referência pelo jogo. Não houve chamadas pagas.

Revisar e organizar as projeções existentes em `application/context.py`,
`interpretation_context.py` e `Conversation`, sem inventar uma cópia para testes.
Documentar, para cada fase, campos obrigatórios/opcionais, origem, significado e
limites de informação: interpretação, Mundo, turno de NPC, narração inicial,
resultado e pergunta off. Usar tipos/validações compartilhados na medida necessária.

Manter instruções e esquemas nos adaptadores reais. O contexto deve ser calculado
do estado atual; fixtures congelam a situação, não o payload enviado à IA.

Acrescentar uma verificação offline das diferenças do contrato aprovado. Ela
deve apontar campos, instruções e esquemas alterados e exigir revisão explícita.
O registro de referência é evidência de revisão, não entrada para chamadas.
Valores variáveis como ids e horários não devem causar diferenças artificiais.

**Aceite:** adicionar um campo chega automaticamente ao fluxo e às chamadas dos
testes; a mudança de contrato é visível mesmo se os comportamentos continuarem
corretos. Atualizar a referência exige explicar a alteração, sem enfraquecer os
critérios para esconder uma regressão.

### 7. Tornar as condições iniciais reproduzíveis sem fabricar regras

**Concluído.** Os oito casos de movimento contextual declaram cenário/variação,
planos de preparação, quantidade de dados e pré-condições. A preparação usa
`build_session`, construtores reais de intenções e `Conversation.execute`; saldo
de movimento e reconhecimento do disfarce agora vêm de caminhada e interações
com teste de Percepção/iniciativa reais. Não há atribuição de estado/histórico.
`DialogueMessage.from_data` e `Conversation.extend_history` validam o histórico
registrado pela mesma entrada usada na conversa normal, sem executar o texto ou
substituir relatórios. A frase inventada de preparação da grade fechada foi
removida. Regressões offline verificam os oito arranjos e preparações inválidas,
incluindo pré-condições impossíveis, falta de abertura/caminhada e dados errados.
Veja a [preparação reproduzível](live-test-preparation.md). Não houve chamadas
pagas nem mudança dos critérios da interação avaliada. A coordenação dos live
tests continua parcial, para os próximos passos.

Manter fixtures declarativas com cenário/variação, mensagens, escolhas, rolagens,
pré-condições e expectativas. Preparar situações intermediárias por operações
públicas reais e conferir suas condições antes de medir a interação com IA.
Por exemplo: posição, grade aberta, espada descoberta/equipada e recurso restante.

Retirar atribuições diretas como `session.state = ...` ou alterações de campos
privados. Quando não houver um caminho público necessário, avaliar a menor
operação validada que também faça sentido para o simulador; não criar um modo
que permita aos testes ignorarem validações. Um sistema geral de save/load não
é pré-requisito deste trabalho.

Injetar rolagens pelo contrato existente, sem substituir testes de habilidade ou
resolução de ataques. Para histórico real congelado, usar uma entrada compartilhada
e validada de histórico, preservando papéis e canais, sem reescrever instruções.
Não confundir essa regressão com uma conversa inteira gerada ao vivo desde o início.

**Aceite:** estado inicial impossível reprova na preparação; mudanças no motor
podem invalidar a preparação, em vez de serem contornadas por atribuições diretas.

### 8. Compartilhar a composição e a configuração dos serviços

**Concluído.** `infrastructure/openai_config.py` centraliza padrões e opções por
fase; `openai_services.py` resolve serviços/cliente, registra configuração e
controla fechamento. `bootstrap.py` compõe cenário, sessão e `GameFlow`; a CLI
entrega esse fluxo à janela. As seis suítes live e a POC usam a mesma composição
dos serviços. Variantes sem correção/contexto completo/esquema legado são
identificadas como experimentos; a suíte semântica passou a respeitar o modelo
do ambiente. Evidências registram parâmetros, perfil/diferenças, SDK e host,
inclusive em falhas de inicialização. Regressões offline verificam parâmetros
reais, ciclo de vida e novos padrões chegando à janela e à suíte contextual.
Veja a [composição dos serviços](service-composition.md). Os padrões e os contratos
de contexto foram preservados; não houve chamadas pagas. A execução live ainda
é parcial e será conduzida pelo coordenador nos próximos passos.

Extrair uma composição comum para criar sessão, fluxo e adaptadores. A UI e os
testes resolvem modelo, parâmetros, timeout e política de correção pelo mesmo
código, com configuração explícita. O cliente real continua na infraestrutura;
o coordenador depende dos contratos já utilizados pela aplicação.

Fixtures podem controlar aleatoriedade e destino dos artefatos. Uma configuração
de modelo alternativa deve ser identificada como experimento, sem apresentá-la
como avaliação do padrão. Não acrescentar instruções de teste ao pedido da IA.

**Aceite:** mudar o padrão da aplicação muda a configuração efetiva das duas
entradas. As evidências registram a configuração realmente usada.

### 9. Disponibilizar uma execução sem interface pelo mesmo fluxo

**Concluído.** `application/game_runner.py` fornece `GameRunner`: abertura,
mensagens, escolha de reação, retomada e reinício delegam ao `GameFlow`. A agenda
só despacha pedidos públicos e entrega resultados, sem outro loop de decisões
de NPCs ou construção de contexto. `game.runner` disponibiliza essa entrada na
composição compartilhada. Os resultados registram etapas/contextos/respostas,
falhas, pausas e despachos incompletos; não há decisão implícita de oportunidade.
Regressões offline comparam janela e runner e verificam efeitos únicos, thread
dona, falhas e retomadas. Veja a [execução sem janela](headless-runner.md).
O limite opcional conta despachos, não custo monetário. Não houve chamadas pagas.
A adoção desta API pelos oito casos live permanece no passo 10, sem declarar
concluída essa migração nem alterar seus critérios antecipadamente.

Criar na aplicação uma forma de conduzir o coordenador até conclusão ou espera
por entrada. O runner live chama essa entrada pública e observa o resultado.
Ele não chama interpretador, diretor e narrador em sequência manualmente, não
usa métodos privados da janela e não implementa seu próprio loop de NPCs.

Escolhas de oportunidade são novas entradas do jogador pelo mesmo contrato
usado pela UI. Se houver escolha pendente sem resposta prevista, o caso termina
nesse limite declarado ou é inconclusivo; o teste não decide silenciosamente.

**Aceite:** janela e runner usam o mesmo fluxo para abertura, mensagens, reações
e reinício, preservando as diferenças necessárias de apresentação/agendamento.

### 10. Migrar os oito casos de movimento contextual

**Concluído.** Os oito casos usam a composição e o runner reais para abertura,
mensagem, turnos de NPCs, reações declaradas e narração. A preparação é feita na
mesma conversa, validada antes da abertura. As frases e critérios foram mantidos;
o caso de iniciativa agora exige o turno do guarda e a volta ao Jogador. Seus
dados obrigatórios foram preservados, com um d20 opcional declarado para um
ataque legal do NPC. O orçamento passou a 33 chamadas normais/41 máximas nos
padrões atuais e é imposto antes do SDK, incluindo correções. Orçamento esgotado
ou escolha ausente registra execução inconclusiva e reprova. Evidências preservam
abertura, etapas, estados, planos, dados, falas, tokens/logs e ids reais.
As outras cinco suítes foram revistas e continuam classificadas pelos limites
que de fato cobrem. Veja a [migração contextual](contextual-live-flow.md).
Regressões locais usam apenas transporte simulado; não houve chamadas pagas.

Migrar primeiro a suíte solicitada, mantendo as frases que revelaram falhas e
os critérios de efeitos e recursos. Substituir a sequência manual de chamadas
pelo fluxo compartilhado e a preparação pelo caminho validado dos passos acima.
Revisar todos os arquivos live depois, conforme a classificação do passo 2.

O caso em que o guarda vence a iniciativa hoje para antes de executar seus
turnos. Ao avaliá-lo como fluxo completo, incluir esses turnos e conferir a volta
ao jogador ou uma interrupção legítima. Se quisermos manter uma avaliação só
da decisão inicial, identificá-la como contrato parcial, com esse limite explícito.

Preservar logs, antes/depois, planos e critérios. Atualizar o orçamento de chamadas:
abertura, turnos de NPCs e retomadas podem aumentar o custo em relação às três
chamadas habituais. O teto deve interromper e sinalizar execução incompleta,
sem pular etapas para obter aprovação.

**Aceite:** uma falha na coordenação real pode reprovar a suíte; a migração não
enfraquece os critérios para manter resultados anteriores.

### 11. Demonstrar offline que os testes detectam regressões

**Concluído.** `tests/integration/test_regression_detection.py` acrescenta 17
verificações com composição, carregadores, adaptadores e fluxo reais, simulando
somente o transporte. Compara janela e runner com expectativas independentes e
rejeita aproximação omitida, Surto sem ataque, NPC sem conclusão, oportunidade
sem evento/dano/reação e texto de movimento sem efeito. As cópias negativas de
observações nunca são aplicadas ao motor. O avaliador live é reutilizado onde
existe; Surto é uma prova local, sem nova suíte paga. Evidências e limites estão
na [demonstração de regressões](regression-detection.md). Nenhuma regra, prompt
ou contrato foi alterado. Não houve chamadas pagas; a prova não substitui a
avaliação semântica dos textos ou o experimento real do passo 12.

Usar transportes simulados somente em testes locais para verificar a integração
do fluxo: decisões conhecidas, mesmas entradas públicas e mesmo estado inicial.
Conferir delegação da UI ao fluxo e resultados observáveis independentes, além
de comparar as entradas da janela e da execução sem interface.

Demonstrar que os critérios detectam os defeitos motivadores: omitir aproximação,
executar somente Surto de Ação sem o ataque pedido, não avançar NPCs, perder
oportunidade e narrar movimento não realizado. Essa prova pode usar resultados
negativos controlados na avaliação, sem introduzir uma segunda implementação de
regras nem um framework de mutações.

**Aceite:** os critérios reprovam a ausência dos efeitos esperados. A igualdade
entre dois caminhos, sozinha, não basta: ambos poderiam compartilhar o mesmo bug.

### 12. Executar um experimento live autorizado e publicar a cobertura real

**Concluído.** Em 16/11/2026, os oito casos contextuais passaram na primeira e
única execução com o padrão `gpt-5.6-terra`, raciocínio `low`, retries zero:
33 chamadas, abaixo do teto prévio de 41, sem correções de interpretação, falhas
de serviço ou inconclusivos. Foram informados 331.806 tokens de entrada e 2.801
de saída. O [relatório](experiments/step12-20261116T205209Z.md) e seu registro
versionável preservam configuração, proveniência, resultados por caso e revisão
das 16 narrações. Essa revisão encontrou imprecisão espacial, regras em `on` e
um adjetivo que pode sugerir vantagem mecânica inexistente. Não houve ajuste de
critérios/prompts nem repetição para ocultar esses resultados.

Definir previamente casos, repetições, configuração e limite de chamadas/custo.
Executar apenas com a autorização prevista no cenário. Salvar também falhas de
serviço, diferenças de interpretação e execuções interrompidas, usando os logs
da aplicação. Não escolher a melhor repetição nem repetir até passar.

Revisar os efeitos e os textos, registrar resultados por caso e as limitações
semânticas que os critérios automáticos ainda não verificam. Atualizar a matriz
de cobertura, os comandos e a política conforme o que realmente foi implementado.

**Aceite:** relatório distingue sucesso, regressão funcional, falha de serviço e
execução inconclusiva. Não transforma uma bateria aprovada em promessa de resposta
determinística do modelo para qualquer situação futura.

## Ordem e conclusão

Executar os passos incrementalmente. A janela usa o coordenador, os contratos
de contexto têm revisão offline e as condições iniciais contextuais são
reproduzíveis por operações públicas validadas. O experimento autorizado foi
executado com plano e orçamento prévios; resultados e limites estão publicados
no relatório do passo 12. Nenhuma repetição foi descartada ou acrescentada.

A migração da suíte contextual está concluída: os testes contêm preparação
declarada, entradas, observação e critérios; carregamento, construção do mapa,
coordenação, contextos, serviços e efeitos são os utilizados pelo simulador.
Testes parciais/experimentais permanecem identificados como tal. Uma execução
aprovada não demonstra repetibilidade nem resolve as ressalvas semânticas.

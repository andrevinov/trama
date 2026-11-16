# Situações congeladas de movimento contextual

Leia a [política](../../../docs/live-tests-policy.md) e a
[preparação reproduzível](../../../docs/live-test-preparation.md) antes de alterar
as fixtures. O arranjo não contém instruções de sistema, esquemas de resposta,
respostas simuladas de IA ou regras alternativas.

`cases.json` declara, por caso:

- Caminho do cenário e variações de passagens anteriores à construção.
- Sequência de preparações em `setup` e quantidade de dados usada nessa fase.
- Pré-condições de posição, portas, itens, disfarce, combate e recursos.
- Mensagem do jogador, histórico registrado opcional, dados e critério de resultado.
- Escolhas explícitas em `choices` e teto compartilhado em `max_sdk_calls`.

`preparations.json` contém planos declarados de movimento, porta, cenário e regra.
O helper desserializa as entradas usando os construtores reais das intenções e
as executa por `Conversation.execute`. Não decide regras, alcance, movimento
contextual, custos, CDs ou dano.

A dungeon de `pocs/simulador/dungeon.json` é construída por
`application.scenarios.build_session`, também usado por `load_session` no
simulador. A porta do banheiro aberta é uma variação explícita dos dados e passa
pelos mesmos validadores. Não há um map builder exclusivo dos testes.

O caso com pouco movimento inicia combate e percorre um circuito legal de cinco
casas, retornando à mesma posição e gastando 7,5 m. Não atribui o saldo. No caso
de oportunidade, o jogador larga e recolhe a espada diante do guarda; o teste de
Percepção real faz o disfarce cair e dispara iniciativa. Isso acrescentou um d20
de preparação. Os dados e critérios da interação avaliada foram preservados.

Cada plano exige seu status declarado, nenhuma falha estruturada, nenhuma etapa
pendente e nenhuma oportunidade que demande escolha/retomada. Revelar a espada
exige especificamente o status `blocked` com evento `start_conflict`: é a
interrupção de início de combate produzida pelo motor, com as ações realizadas.
Não é uma permissão geral para ignorar erros de preparação.

As pré-condições são expectativas escritas na fixture, comparadas com o estado
real antes da chamada. Nunca são geradas pelo resultado atual da aplicação.
As rolagens fixam tipo, ordem e valor de cada dado; uma rolagem extra, inválida
ou de tipo errado falha explicitamente. `preparation_rolls` confere o ponto de
separação entre os dados da preparação e os da interação avaliada.

O caso em que o guarda vence iniciativa ganhou `optional_world_rolls`: um d20
fixado em 1, disponível depois de todos os dados obrigatórios, caso ele ataque.
Se esperar, esse dado pode sobrar; ele é registrado separadamente. A sequência
obrigatória original continua exigida. O critério agora inclui a execução do
turno do guarda e devolução do controle ao Jogador, sem ataque gratuito deste.

`investigation_history.json` preserva as mensagens reais anteriores à falha de
16/11/2026, com origem identificada. A leitura usa `DialogueMessage.from_data` e
`Conversation.extend_history`, a mesma entrada usada pelas mensagens novas da
aplicação. Papéis e canais são preservados, incluindo off; off não entra no
contexto de interpretação. O pedido atual é acrescentado por
`game.runner.submit`, que usa `Conversation.prepare`. Esse caso é uma regressão com histórico congelado,
não uma conversa toda gerada ao vivo.

O histórico não executa ações nem altera a memória dos relatórios reais da
preparação. Sua origem identifica o texto registrado; a engine não tenta provar
pela leitura do texto que todos os fatos narrados ocorreram. Posição, inventário
e demais condições mecânicas são verificados separadamente.

Os artefatos guardam também as preparações declaradas, o histórico com origem e
os dados usados na preparação. As operações e rolagens reais ficam nos logs.
A coordenação agora usa `open_game`/`game.runner`, da própria aplicação. A
preparação é validada antes da primeira chamada à IA; a abertura descreve a
situação preparada. O histórico registrado é acrescentado depois da abertura
para preservar a janela da regressão. Os critérios continuam independentes.

Os sete casos sem turno adicional preveem 4 chamadas normais e teto de 5;
o caso de iniciativa prevê 5 e teto de 6. No total: 33 normais/41 máximas, com
uma correção por interpretação e retries padrão zero. O teto é aplicado antes
de cada chamada lógica ao SDK, incluindo correções. Orçamento esgotado e escolha
ausente são inconclusivos e reprovam; `choices=[]` nunca significa recusar reação.
Não há teto monetário. Consulte a [migração e seus limites](../../../docs/contextual-live-flow.md).

A checagem local em `tests/integration/test_contextual_live_scenarios.py` verifica
as preparações e os critérios, inclusive arranjos propositalmente inválidos.
Ela não substitui a execução dos oito testes live.

# Decisão do Mundo e turnos de NPCs

Tier 3 · [IA](README.md) · [Visão geral](../../../README.md)

## Entradas e proposta

Código: [openai_world_director.py](../../../src/trama/infrastructure/openai_world_director.py).
O serviço implementa `WorldDirector` e devolve `WorldPlan`, separados do plano
do jogador. A aplicação produz duas projeções: resposta a uma proposta do jogador
e decisão do NPC ativo. Os [contratos](contextos-e-contratos.md) distinguem essas fases.

Para uma ação do jogador, o diretor recebe o Mundo completo, o plano e os
requisitos/preparações previstos. O plano ainda não aconteceu. O modelo decide
se há reação pertinente e em que ponto ela deve ocorrer. Uma lista vazia é
válida: a mudança de local ainda pode exigir narração sem ação do Mundo.

Para um turno de NPC, recebe o estado atual e a identidade de quem pode agir.
Não recebe o plano anterior do jogador como nova autorização de execução.
A proposta deve permitir concluir legalmente o turno, respeitando posição,
alvo, alcance e recursos disponíveis.

## Operações e execução

As respostas podem envolver fala, deslocamento, passagem, ataque, espera,
conflito ou testes permitidos. As condições, índices e pontos ao longo de
movimento são definidos em [execução do Mundo](../aplicacao/execucao-do-mundo.md).
O executor determinístico valida e aplica a proposta; uma descrição não cria
objetos, condições persistentes ou dano por si só.

O [fluxo](../aplicacao/fluxo-do-jogo.md) conduz NPCs até devolver o
controle, encontrar impedimento, precisar de escolha ou o jogador ficar sem PV.
Uma decisão inválida é uma falha observável, sem repetição automática das ações
já feitas. Pausar uma oportunidade preserva a continuação daquele turno.

## Cenário e informação

O diretor conhece os segredos para tomar decisões. O executor marca o que é
perceptível para a [narração](narracao.md). Na dungeon, respostas de exploração
já são adjudicadas pelo roteiro e não devem ser duplicadas. A rotina do banheiro
não é uma nova decisão livre da IA a cada quadro da interface.

Um teste de Percepção proposto usa o dado e o modificador calculados pelo motor;
a CD exige justificativa contextual, não uma distância universal inventada.
O [cenário](../simulador/fuga-da-dungeon.md) documenta as CDs fixas
próprias da aventura.

## Verificação

A integração é exercitada por [test_world_flow.py](../../../tests/integration/test_world_flow.py)
e pelo [fluxo real compartilhado](../qualidade/movimento-contextual-live.md).
A [observabilidade](../observabilidade/logs.md) permite distinguir
proposta, ação confirmada, interrupção e narração entregue.

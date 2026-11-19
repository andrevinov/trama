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

Em `say`, o diretor pode propor metadados do
[estado da conversa](../aplicacao/estado-da-conversa.md), incluindo o objetivo
privado do próprio NPC. `world.conversations` contém perspectivas por personagem;
a raiz `conversations` é a perspectiva do jogador. A execução usa os ouvintes
reais e resolve referências somente após as falas anteriores da etapa acontecerem.
Isso permite contrapropostas sem antecipar recepção ou efeitos materiais.

O diretor conhece os segredos para tomar decisões. O executor marca o que é
perceptível para a [narração](narracao.md). Na dungeon, respostas de exploração
já são adjudicadas pelo roteiro e não devem ser duplicadas. A rotina do banheiro
não é uma nova decisão livre da IA a cada quadro da interface.

Um teste de Percepção proposto usa o dado e o modificador calculados pelo motor;
a CD exige justificativa contextual, não uma distância universal inventada.
O [cenário](../simulador/fuga-da-dungeon.md) documenta as CDs fixas
próprias da aventura.

## Avaliação privada de opções

`reactions[].opinions` propõe impactos semânticos após uma fala real no modo
narrado. O código valida dono, versão e termos percebidos, calcula as notas e
guarda os motivos em `world.social.opinions`, sem produzir evento público ou
resolver Influence. Um ator avaliado não recebe ações nesse mesmo plano: sua
escolha ocorre em `npc_agency` depois dos números reais, na mesma interação. `actions=[]` é válido quando há opiniões. Em `npc_agency`,
`opinions` na raiz traz somente avaliações calculadas do próprio ator; novas
avaliações nessa fase e em combate ficam fora deste recorte. Veja o
[contrato completo](../aplicacao/opinioes-por-opcao.md).

## Verificação

A integração é exercitada por [test_world_flow.py](../../../tests/integration/test_world_flow.py)
e pelo [fluxo real compartilhado](../qualidade/movimento-contextual-live.md).
A [observabilidade](../observabilidade/logs.md) permite distinguir
proposta, ação confirmada, interrupção e narração entregue.

`intent` em `npc_agency` separa objetivo da conversa, iniciativa, motivo privado
e `opinion_ids`. O objetivo central opcional está em `profile.persona.objective`.
Aceitar/recusar exige nota atual da versão correspondente; contrapropor ou revisar
a própria oferta compara termos finais com a alternativa avaliada, incluindo
tipo, responsável e ordem. Conversa comum, fila, espera e limites estão no
[contrato de agência](../aplicacao/intencoes-dos-npcs.md).

As [relações iniciais](../aplicacao/relacoes-iniciais.md) fornecem confiança e
afeto direcionais em `world.social.relationships` e na projeção própria
`relationships`. O diretor propõe pertinência por termo, sem escolher os níveis
ou pesos. Python soma R com limite ±12, mantém limiares e
exclui de M aspectos já resumidos por uma dimensão aplicada. Amizade não prova
confiabilidade e uma relação forte não obriga aceitar. Os pedidos Influence
anteriores conservam seu contrato.

No passo 6, `reactions[].episodes` permite propor uma interpretação de evidência
própria ativa. O código valida percepção, autoria, referência de compromisso,
ordem temporal, categoria e aplicação única; a variação é fixa por categoria.
Relações mudam antes das opiniões, sem ação antecipada pelo mesmo dono nesse
plano. `npc_agency` continua escolhendo depois, com a base atual. Rumor só pode
fundamentar suspeita; compromisso verbal não comprova cumprimento. História,
fontes e notas permanecem privadas. Veja o
[contrato de episódios e memória](../aplicacao/evolucao-das-relacoes.md).

O passo 7 acrescenta `npc_review` para acontecimentos pertinentes realmente
percebidos. Essa projeção é individual: o diretor não recebe o estado onisciente
do mestre para preencher lacunas do NPC. Pode conservar as avaliações ou propor
somente as afetadas. Após o cálculo, `npc_agency` escolhe a mudança de prioridade,
incluindo suspensão, retomada ou investigação/proteção com uma operação suportada.
Não há ataque livre nem incidente físico criado por texto. Fontes, orçamento e
alcance estão em [acontecimentos e prioridades](../aplicacao/acontecimentos-e-prioridades.md).

Nas [conversas casuais](../simulador/conversas-casuais.md), escutar, aconselhar
com abertura ou oferecer orientação não exige avaliação de proposta. Objetivo
e foco podem mudar sem criar acordo. O diretor pode escolher `listen` com fala
de acolhimento e espera ou `leave` com despedida e destino visto; só a execução
real produz movimento. Relações iniciais não obrigam ajuda, companhia ou romance,
e a moeda anterior declarada no cenário não é uma nova operação de transferência.

O passo 9 acrescenta `reactions[].bonds` nas fases de cálculo. O diretor propõe
formação, manutenção ou ruptura com fontes próprias; Python valida critérios
e sequência antes da decisão. Amizade, atração, paixão e amor não adicionam R
ou comprovam reciprocidade. `romance_boundary` registra disponibilidade própria
explicitamente falada, e `romantic_expression` exige elegibilidade e respeito aos
limites conhecidos. Veja [vínculos afetivos](../aplicacao/vinculos-afetivos.md).

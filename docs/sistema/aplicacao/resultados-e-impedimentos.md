# Resultados, impedimentos e memória mecânica

Tier 3 · [Aplicação](README.md) · [Visão geral](../../../README.md)

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
contexto completo. Veja [a autorização de planos](planos-e-validacao.md).

O campo de visão e `perception` continuam separados: fatos conhecidos pela IA
como mestre não são automaticamente conhecidos pelo Jogador. O narrador só deve
revelar criaturas vistas e acontecimentos marcados como perceptíveis; falas
audíveis podem ser percebidas sem visão. A coerência de ocultação em texto depende
do cumprimento dessas instruções pelo modelo; a interface filtra a visão por código.

Com `--debug`, ficam registrados os pedidos completos de interpretação, decisão
do Mundo e narração, além das decisões e dos efeitos. Eventos `world.*` incluem
atores, testes, respostas e interrupções, usando a mesma correlação dos demais
módulos. Não há acesso aos pensamentos internos do modelo.

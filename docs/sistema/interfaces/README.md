# Interfaces e formas de execução

Tier 2 · [Visão geral do Trama](../../../README.md) ·
[Aplicação](../aplicacao/README.md) · [Simulador](../simulador/README.md)

Esta área reúne as formas de conduzir a partida e consultar seus resultados.
A janela Pygame atende o jogador; a execução sem janela permite consumir o
mesmo fluxo de aplicação programaticamente, inclusive nos testes.

## Responsabilidade e fronteiras

A interface transforma mensagens e escolhas em entradas públicas do fluxo.
Ela apresenta conversa, mapa, fichas e pendências a partir das projeções reais
da aplicação. A definição das etapas do jogo permanece no coordenador.

A janela agenda chamadas externas em workers e entrega seus resultados ao
fluxo na thread principal. O runner sem janela agenda os pedidos de forma
síncrona. Essa diferença de agendamento preserva as mesmas decisões de fluxo,
validações e operações do jogo.

## Partes desta área

| Parte | Responsabilidade | Código de referência |
| --- | --- | --- |
| Janela e entrada | Receber mensagens, tratar eventos e apresentar conversa, mapa e escolhas de reação. | [movement_window.py](../../../src/trama/ui/movement_window.py) |
| Ficha e inimigos | Organizar dados e cartões de consulta, com detalhes expansíveis e disponibilidade atual. | [character_panel.py](../../../src/trama/ui/character_panel.py) |
| Texto | Apoiar apresentação e organização de texto na janela. | [text.py](../../../src/trama/ui/text.py) |
| Execução sem janela | Despachar pedidos públicos do fluxo até conclusão, falha ou necessidade de nova entrada. | [game_runner.py](../../../src/trama/application/game_runner.py) |

O runner está no pacote de aplicação porque pode ser reutilizado por diferentes
consumidores. Ele aparece nesta área documental como uma forma de entrada na
partida, ao lado da janela; a coordenação compartilhada é descrita em
[Aplicação](../aplicacao/README.md).

## Estado apresentado e escolhas

O desenho do mapa usa posições e visibilidade calculadas pelo sistema. Uma
criatura fora do campo de visão deixa de aparecer; um marcador de criatura com
PV zerados pode indicar que ela está fora de combate, sem declarar sua morte.

A ficha consulta projeções produzidas por
[sheets.py](../../../src/trama/application/sheets.py) e
[sheet_options.py](../../../src/trama/application/sheet_options.py). Ela separa
ações possíveis agora, recursos com recuperação e dados do personagem. Consultar
ou expandir detalhes de um cartão não executa a ação nem consome recursos.

As escolhas de oportunidade do jogador são entradas explícitas. A execução
sem janela também pausa quando uma escolha está pendente; um consumidor precisa
fornecê-la para continuar. Falha, impedimento físico e espera por escolha são
situações diferentes e devem ser apresentadas como tal.

## Relações com outras áreas

- A [Aplicação](../aplicacao/README.md) recebe entradas, mantém o estado e publica
  relatórios e projeções; a interface agenda e apresenta esse trabalho.
- O [Mundo](../mundo/README.md) fornece geometria, objetos e visão. A camada
  visual apresenta seus efeitos sem redefinir bloqueios ou alcance.
- A [IA](../ia/README.md) participa por serviços ligados ao fluxo. A UI não
  depende do SDK da OpenAI para organizar seus controles e sua apresentação.
- O [Simulador](../simulador/README.md) compõe cenário e serviços e entrega a
  partida à janela ou ao consumidor sem janela.
- A [Qualidade](../qualidade/README.md) verifica a integração da UI localmente e
  compara entradas da janela e do runner com critérios de efeitos independentes.

## Alcance e detalhamento existente

A janela atual contém conversa, mapa e guias Jogo/Ficha/Inimigos. Ações são
solicitadas por mensagem, com controles específicos para oportunidade e reinício.
Não há botões de iniciar combate ou renovar turno. A existência de uma API de
regra no motor não implica que ela tenha um comando ou controle na interface.

| Assunto | Referência de tier 3 |
| --- | --- |
| Execução sem janela pelo mesmo fluxo | [execucao-sem-janela](execucao-sem-janela.md) |
| Janela Pygame e entrada do jogador | [pygame](pygame.md) |
| Ficha e opções disponíveis | [ficha-do-personagem](ficha-do-personagem.md) |

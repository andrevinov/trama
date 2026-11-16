# Regras determinísticas

Tier 2 · [Visão geral do Trama](../../../README.md) ·
[Aplicação](../aplicacao/README.md) · [Mundo](../mundo/README.md)

Esta área reúne os cálculos e as validações de D&D 5.5e implementados no motor.
Ela permite resolver uma operação com entradas explícitas e obter seu resultado,
independentemente de como o jogador expressou o pedido ou de como ele será narrado.

## Responsabilidade e fronteiras

As regras calculam custos, disponibilidade, rolagens e efeitos. A aplicação
coordena quando utilizá-las e aplica os resultados ao estado da partida. Uma
regra de ataque, por exemplo, calcula acerto e dano a partir de fichas e dados;
a aplicação verifica também posição, alcance e disponibilidade daquela ação.

Esses componentes não dependem do SDK da OpenAI ou do Pygame. Movimento utiliza
geometria e unidades; combate utiliza fichas e dados. A integração entre movimento
e combate, necessária para oportunidades, é coordenada pela aplicação.

## Partes desta área

| Parte | O que resolve | Código de referência |
| --- | --- | --- |
| Movimento | Custos por casa, terreno, saldo e interrupção do percurso solicitado. | [movement.py](../../../src/trama/movement.py) |
| Ações | Orçamento de ação, bônus, reação e interação; operação básica de portas. | [actions.py](../../../src/trama/actions.py) |
| Personagens | Fichas, atributos, perícias, armas e recursos do recorte Humano/Guerreiro/Campeão. | [characters.py](../../../src/trama/characters.py) |
| Combate | Iniciativa, ordem de turnos, resolução de ataques e efeitos implementados. | [combat.py](../../../src/trama/combat.py) |
| Reações | Condição geométrica para provocar uma oportunidade ao sair do alcance. | [reactions.py](../../../src/trama/reactions.py) |
| Dados e testes | Rolagens com fonte injetável; testes de atributo combinam dados e ficha. | [dice.py](../../../src/trama/dice.py), [characters.py](../../../src/trama/characters.py) |
| Unidades | Representação em metros, conversão de entradas e formatação. | [distances.py](../../../src/trama/distances.py) |

## Relações com outras áreas

- O [Mundo](../mundo/README.md) fornece grade, obstáculos, passagens e posições.
  As regras de movimento operam sobre essa geometria.
- A [Aplicação](../aplicacao/README.md) combina os resultados com os recursos do
  encontro, preserva progresso parcial e coordena reações durante um percurso.
- A [IA](../ia/README.md) propõe operações e recebe seus resultados. As rolagens
  e os efeitos mecânicos são calculados pelo código.
- As [Interfaces](../interfaces/README.md) mostram projeções de fichas e ações
  disponíveis, construídas pela aplicação a partir dessas regras.
- A [Qualidade](../qualidade/README.md) usa dados controlados e expectativas
  independentes para verificar efeitos e consumo de recursos.

Por exemplo, Surto de Ação altera o orçamento disponível. Quando o pedido inclui
um ataque em seguida, a aplicação executa essa sequência e consulta as regras
de ataque com o novo orçamento. A regra do poder não interpreta a frase inteira.

## Alcance atual

O recorte cobre movimento terrestre em grade, portas, combate básico e as fichas
de Humano/Guerreiro dos níveis 1 a 3, incluindo Campeão. Algumas capacidades,
como efeitos de descanso, têm API determinística sem comando na conversa.
Preparar, Desengajar e um sistema completo de condições e morte ainda não têm
execução geral no jogo.

Referências da edição 2024 e simplificações devem acompanhar o assunto específico.
CDs, rotinas de NPCs e escolhas de equipamento de uma aventura pertencem ao
[Simulador](../simulador/README.md), enquanto as operações reutilizáveis permanecem
no motor.

## Documentos de tier 3

| Assunto | Referência de tier 3 |
| --- | --- |
| Aproximação e ataques de oportunidade | [reacoes](reacoes.md) |
| Iniciativa, turnos e ataques | [combate](combate.md) |
| Movimento terrestre e unidades | [movimento](movimento.md) |
| Ações, orçamento e portas | [acoes](acoes.md) |
| Personagens, traços e recursos | [personagens](personagens.md) |
| Dados, vantagem e testes de atributo | [dados-e-testes](dados-e-testes.md) |

A ficha e os dados do cenário escolhido determinam equipamento e condições iniciais.
As referências distinguem regras reutilizáveis de políticas exclusivas da aventura.

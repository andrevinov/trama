# Dados, vantagem e testes de atributo

Tier 3 · [Regras](README.md) · [Visão geral](../../../README.md)

## Fonte das rolagens

Código: [dice.py](../../../src/trama/dice.py) e [characters.py](../../../src/trama/characters.py).
O contrato `Roller.roll(sides)` fornece um inteiro entre 1 e o número de faces.
`RandomRoller` usa uma fonte local de aleatoriedade. `roll_die` valida o valor;
booleanos, resultados fora do intervalo ou de outro tipo são rejeitados.

A IA pode propor um teste permitido com sua justificativa; o código rola o dado
e calcula o resultado. Os modelos não escolhem o valor obtido.

## D20 e testes

`D20Roll` conserva dados, índice escolhido, modificador e vantagem/desvantagem.
`natural` é o valor escolhido antes do modificador; `total` soma ambos.
`roll_d20` rola dois dados quando há somente vantagem ou somente desvantagem,
selecionando o maior ou menor respectivamente. Com ambas, usa um dado.

`ability_check` usa perícia, ficha e CD, preservando estado e informação da
rolagem. O Campeão tem vantagem em Atletismo no recorte implementado.
Mente Tática e inspiração possuem APIs específicas; sua existência não implica
que todo teste possa solicitá-las pela conversa atual.

A resolução de ataques interpreta 1/20 naturais e o crítico de Campeão em
[combate](combate.md). As regras do dado não aplicam sucesso ou fracasso
universal a todo teste de atributo por obter 1 ou 20 natural.

## CDs, referências e preparação

PHB 2024: D20 Tests, Ability Checks, Advantage/Disadvantage e recursos de
Humano/Guerreiro/Campeão. Uma CD de audição ou disfarce do simulador é uma
[decisão da aventura](../simulador/fuga-da-dungeon.md#testes-e-decisões-de-mestre),
não uma lei geral de distância ou rotina.

Os testes injetam uma implementação de `Roller`, controlando faces, ordem e
resultado sem trocar as regras. Nas [fixtures live](../qualidade/preparacao-de-cenarios.md),
dados de preparação e de interação são conferidos separadamente. Um dado
inesperado reprova a condição reproduzível, em vez de usar uma reserva aleatória.

## Verificação e observabilidade

As regressões de [dados e personagens](../../../tests/unit) cobrem validação, escolha
com vantagem/desvantagem e consumo de recursos. Os eventos `dice.rolled`,
`dice.d20_resolved` e os testes resolvidos são descritos no
[contrato dos logs](../observabilidade/logs.md).

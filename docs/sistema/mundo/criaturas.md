# Criaturas posicionadas e identificação

Tier 3 · [Mundo](README.md) · [Visão geral](../../../README.md)

## Contrato

Código: [creatures.py](../../../src/trama/creatures.py).
`Creature` contém `id`, `name`, `position` e `hostile`. Identificador e nome
precisam ser preenchidos e hostilidade é booleana. `creatures_from_data` usa
essa estrutura para ler os participantes posicionados do cenário.

Essa representação não contém comportamento ou uma ficha de classe.
A sessão conecta ids a fichas, estados e orçamento no
[encontro](../../../src/trama/application/encounter.py); a
[decisão de NPC](../ia/decisao-do-mundo.md) é proposta pela IA e
executada pela aplicação.

## Identificação e ocupação

Os números exibidos no mapa acompanham id e nome no contexto. “Guarda 1” pode
assim ser resolvido para um alvo existente, sem inventar um id de lugar.
A numeração é estável ao ocultar e revelar criaturas. A navegação até um alvo
visível procura espaço livre ao alcance, em vez de entrar em sua casa.

A sessão genérica bloqueia as casas das criaturas cadastradas. Na dungeon,
guardas com PV zerados podem ser atravessados como terreno difícil, mas sua
casa não é destino para terminar o percurso. É uma política específica de
[DungeonSession](../../../src/trama/application/dungeon.py), não uma regra universal
para qualquer tamanho, aliado ou condição.

## Visibilidade e criaturas do cenário

O campo de visão filtra marcadores e resumos de inimigos apresentados ao
jogador. A IA como mestre pode receber criaturas ocultas; a narração deve
respeitar a [percepção](visao-e-percepcao.md). `at_zero_hp` indica PV zerados,
sem equivaler a uma resolução completa de morte.

O prisioneiro da dungeon é uma entidade específica da aventura, com estado de
sono, libertação e acompanhamento, sem ficha fictícia de Guerreiro ou turno
completo próprio. Veja o [cenário de fuga](../simulador/fuga-da-dungeon.md).

## Verificação e limites

As regressões de [aproximação](../../../tests/integration/test_approach_creature.py),
[simulador](../../../tests/integration/test_dungeon_simulator.py) e
[interface](../../../tests/integration/test_movement_window.py) verificam ids, ocupação,
visão e apresentação. O recorte não é um sistema geral de relações entre facções,
tamanhos de criaturas ou condições de inconsciência e morte.

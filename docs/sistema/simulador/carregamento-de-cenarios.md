# Carregamento e formato de cenários

Tier 3 · [Simulador](README.md) · [Visão geral](../../../README.md)

## Entradas compartilhadas

Código: [scenarios.py](../../../src/trama/application/scenarios.py).
`load_session(path, roller=...)` lê JSON e chama `build_session(data, roller=...)`.
`load_dungeon` exige que o resultado seja uma dungeon. As entradas não importam
Pygame, CLI ou SDK e não executam chamadas de IA.

A construção escolhe `DungeonSession` quando há a chave `dungeon`; usa `Scene`
para mapas com `areas`; caso contrário, constrói uma grade simples. Fichas e
criaturas passam pelos construtores reais. Uma variação declarada antes da
construção precisa satisfazer os mesmos validadores.

## Dados da grade e da cena

| Dados | Uso |
| --- | --- |
| `width`, `height`, `start` | Dimensões e posição inicial em base zero. |
| `speed_meters` | Velocidade em metros; o padrão pode vir da ficha. |
| `blocked`, `difficult` | Casas da grade simples; mapas nomeados derivam piso e paredes das áreas. |
| `areas`, `passages` | Arquitetura nomeada e estados de portas/grades. |
| `objects`, `dim`, `dark` | Objetos estáticos e iluminação opcional da cena. |
| `player`, `creatures[].sheet` | Escolhas de ficha dos participantes. |
| `creatures` | Identidade, posição e hostilidade de criaturas cadastradas. |
| `dungeon` | Dados específicos da aventura, interpretados por `DungeonSession`. |

Formato de [áreas e passagens](../mundo/mapas-e-passagens.md),
[objetos](../mundo/objetos.md) e [fichas](../regras/personagens.md)
tem validadores próprios. Esse resumo não é um esquema JSON genérico completo.
O exemplo mínimo a seguir usa a grade simples:

```json
{"width": 10, "height": 10, "start": [3, 5], "speed_meters": 9}
```

Exemplos completos são os arquivos reais:
[dungeon.json](../../../pocs/simulador/dungeon.json),
[cela_guardas.json](../../../pocs/movimento/cela_guardas.json) e
[scenario.json](../../../pocs/movimento/scenario.json).

## Estado inicial e preparação

O carregador constrói a sessão, mas não prepara inventário, turnos ou histórico
intermediário. Rolagens são injetadas na construção pelo contrato `Roller`.
A [preparação dos testes](../qualidade/preparacao-de-cenarios.md)
usa operações públicas depois disso, validando pré-condições antes da avaliação.

Usar esses mesmos construtores em simulador e testes evita map builders
paralelos. Não há gerador procedural de mapas ou sistema geral de save/load.
As regressões em [test_scenario_loading.py](../../../tests/integration/test_scenario_loading.py)
verificam os três formatos, variações, erro de posição e independência das interfaces.

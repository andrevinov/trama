# Carregamento e formato de cenários

Tier 3 · [Simulador](README.md) · [Visão geral](../../../README.md)

## Entradas compartilhadas

O comando oficial usa como padrão um recurso de
`src/trama/scenarios/dungeon_escape.json`, incluído na distribuição do pacote.
A CLI o resolve com `importlib.resources` e entrega seu caminho a `open_game`.
Isso independe do checkout e mantém o carregador abaixo como fonte única da
construção. Veja [a entrada do simulador](execucao.md).

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
[dungeon_escape.json](../../../src/trama/scenarios/dungeon_escape.json),
[legacy_cell_and_guards.json](../../../tests/fixtures/scenarios/legacy_cell_and_guards.json) e
[simple_grid.json](../../../tests/fixtures/scenarios/simple_grid.json).

A dungeon é o cenário ativo distribuído com a aplicação. Os dois mapas
anteriores são [fixtures de regressão](../../../tests/fixtures/scenarios/README.md),
mantidos fora do pacote e carregáveis pelo mesmo `--scenario`. Seus dados foram
preservados sem criar um construtor exclusivo dos testes.

## Estado inicial e preparação

O carregador constrói a sessão, mas não prepara inventário, turnos ou histórico
intermediário. Rolagens são injetadas na construção pelo contrato `Roller`.
A [preparação compartilhada](../qualidade/preparacao-de-cenarios.md)
usa operações públicas depois disso, validando pré-condições antes da abertura.

Usar esses mesmos construtores em simulador e testes evita map builders
paralelos. Não há gerador procedural de mapas ou sistema geral de save/load.
As regressões em [test_scenario_loading.py](../../../tests/integration/test_scenario_loading.py)
verificam os três formatos, variações, erro de posição e independência das interfaces.

## Situações reproduzíveis

O [catálogo](../../../src/trama/scenarios/situations.json) acompanha o pacote da
aplicação. Ele contém `schema_version: 1`, grupos de `preparations` e uma lista de
`situations`. É uma declaração de como chegar a um estado, sem copiar o mapa ou
substituir os executores. O recorte atual contempla a dungeon de fuga.

```bash
poetry run trama-simulator --situation investigar-cela-do-log --debug
poetry run trama-simulator --situation ataque-com-movimento-insuficiente --debug
```

| Identificador | Situação preparada |
| --- | --- |
| `investigar-cela-do-log` | Corredor diante da Cela 4 aberta, com histórico da sessão que motivou a regressão. |
| `pegar-espada-distante` | Espada descoberta na cela; personagem de volta ao corredor. |
| `atacar-com-aproximacao` | Personagem disfarçado junto à sala, com espada escondida; sem iniciativa ainda. |
| `ataque-com-movimento-insuficiente` | Turno do jogador com apenas 1,5 m de movimento restante. |
| `ataque-guarda-vence-iniciativa` | Mesmo ponto de aproximação, com dados que favorecem o guarda na iniciativa. |
| `investigar-grade-fechada` | Personagem diante da Cela 4, com a grade fechada. |
| `investigar-sem-sair-do-lugar` | Cela 4 aberta; o pedido avaliado pelo teste proíbe aproximação. |
| `abordagem-distante` | Jogador no corredor antes do ruído; dados levam o guarda à primeira detecção junto à porta. |
| `conversa-evita-combate` | Mesmo ponto inicial, com Persuasão favorável após a abordagem. |
| `conversa-falha-inicia-combate` (id histórico) | Perfil neutro/cauteloso e Persuasão falha; recusa sem iniciativa automática. |
| `conversa-jogador-ataca` | Mesmo ponto inicial, com iniciativa favorável ao guarda quando o jogador escolhe lutar. |
| `investigar-com-ataque-de-oportunidade` | Personagem junto ao guarda, em combate, com banheiro acessível. |

Os 13 identificadores `percepcao-*` usam `perception_rooms.json`, uma situação
genérica sem lógica de dungeon. Seus [casos e condições iniciais](../qualidade/percepcao-live.md)
cobrem visão, porta, escuridão, sons, furtividade, busca e sono. Podem ser abertos
por `--situation` e reiniciados pelos mesmos mecanismos da aplicação.

Os identificadores `turno-npc-distante` e `turno-npc-aproxima-e-ataca` usam o
corredor genérico `npc_turn_corridor.json`, com combate preparado por operação
pública. Consulte os [critérios de conclusão do turno](../qualidade/turnos-npc-live.md).

Os quatro identificadores `memoria-*` usam `knowledge_rooms.json`, com arquivista,
aprendiz e conhecimento inicial por NPC. As [condições e critérios](../qualidade/conhecimento-live.md)
incluem ausência de memória, posição oculta diferente da lembrança e relato novo.

As três situações `memoria-vinculos-*` usam a dungeon e seu guarda corrupto, com
abordagem preparada em [8,20] e guarda em [10,6]. Os [casos de vínculos sociais](../qualidade/vinculos-memoria-live.md)
cobrem uma mesma alegação afetando vários interesses sem multiplicar sua pontuação.

Cada situação declara:

- `id` e `scenario`: identificação e nome de recurso JSON existente no pacote, sem caminhos externos.
- `start_variation`, `sense_variations` e `lighting_variations`: posição inicial,
  perfis sensoriais por id de NPC e casas `dim`/`dark`, validados pelo carregador.
- `passage_variations`: mudanças explícitas de `is_open`/`locked` antes da construção.
- `knowledge_variations`: substitui a lista de memórias de NPCs existentes;
  `object_variations` varia somente a posição de objetos estáticos declarados.
- `social_variations`: substitui o perfil social de NPCs existentes; alinhamento,
  persona e interesses passam pelo mesmo validador do cenário. As sete situações
  `disposicao-*` do corredor genérico demonstram os perfis e a relevância de novas
  informações. Veja [disposição social](../aplicacao/disposicao-social.md).
  Os dados passam pelos mesmos construtores e validadores do cenário.
- `setup`: grupos de planos determinísticos; cada etapa declara seu `intent` e os
  campos dos construtores reais de movimento, porta, regra, narrativa ou cenário.
- `rolls` e `optional_world_rolls`: pares `[faces, valor]` na ordem de consumo.
- `preparation_rolls`: quantidade exigida antes de abrir a conversa.
- `preconditions`: igualdades sobre o estado observado, com caminhos separados
  por ponto. Coordenadas dessa observação usam base 1, como a tela.
- `history`, opcional: registro com `source` e `messages`, validado pelos contratos
  de diálogo e acrescentado após a descrição inicial.

`Situation` valida e executa a preparação por `Conversation.execute`, sem
interpretá-la com IA. Um plano não cumprido, uma rolagem divergente ou uma
pré-condição falsa impede abrir a situação. Um término `blocked` só é aceito
quando declarado com efeitos esperados, como o início de conflito. Não é uma
permissão para ignorar erros ou ações pendentes.

`open_situation(load_situation(id), ...)`, em `bootstrap.py`, usa `open_game` e
entrega o mesmo `GameFlow` à janela ou a `game.runner`. Reiniciar restaura a sessão,
repõe os dados, refaz as operações e confere novamente o estado. O histórico
registrado é acrescentado uma vez por abertura concluída; não executa ações.

As rolagens são estritas: ao esgotar os dados ou pedir um dado de outro tipo,
a execução informa o erro, sem sortear um substituto. As situações são recortes
de diagnóstico; não cobrem qualquer continuação da aventura. A IA continua
podendo variar. O modo normal do simulador, sem `--situation`, usa dados aleatórios.

As [fixtures dos testes](../../../tests/fixtures/contextual_movement/README.md)
conservam as frases, escolhas, orçamento e critérios de sucesso, sem duplicar a
preparação. [test_simulator_situations.py](../../../tests/integration/test_simulator_situations.py)
confere seleção pela CLI, equivalência com a entrada sem janela, reinício e
rejeição antes de chamar modelos. O teste de empacotamento também abre uma
situação diretamente do wheel, sem checkout.

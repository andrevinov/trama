# Objetos, fixação e bloqueios

Tier 3 · [Mundo](README.md) · [Visão geral](../../../README.md)

## Objetos do mapa

O campo `objects`, na raiz de `dungeon.json`, descreve objetos estáticos do mapa.
As quatro tochas usam esta estrutura (coordenadas do JSON começam em zero):

```json
{
  "id": "torch_1",
  "name": "Tocha 1",
  "kind": "torch",
  "position": [8, 8],
  "attachment": {"surface": "wall", "side": "east"},
  "blocks_movement": false,
  "blocks_vision": false,
  "description": "Tocha acesa, fixada à parede leste do corredor."
}
```

`position` identifica a casa de piso à qual o objeto pertence. `attachment`
indica chão (`floor`, sem `side`) ou parede (`wall`, com `north`, `east`, `south`
ou `west`). Uma fixação de parede exige parede no lado indicado; o limite do mapa
também pode servir de parede. A fixação determina a localização do desenho e não
adiciona bloqueios por si só. Vários objetos podem compartilhar a mesma casa.

`blocks_movement` e `blocks_vision` são independentes. Por exemplo:

| Objeto de exemplo | Bloqueia passagem | Bloqueia visão |
| --- | --- | --- |
| Tocha na parede | não | não |
| Cerca | sim | não |
| Cortina atravessável | não | sim |
| Caixote alto | sim | sim |

Esses efeitos são configurações do cenário, por decisão do usuário, e representam
a **casa inteira** neste incremento. Não há volume, altura, cobertura parcial ou
barreiras apenas entre duas casas. Cerca, cortina e caixote são exemplos usados
nos testes; a dungeon continua contendo apenas as quatro tochas como objetos
estáticos. Itens coletáveis continuam no inventário próprio do cenário.

`Scene.grid` contém terreno e passagens; `Scene.movement_grid` combina esse terreno
com os bloqueios dos objetos. A sessão usa `movement_grid`. `Scene.opaque` combina
paredes, portas fechadas e os objetos que bloqueiam visão. Uma grade fechada
continua transparente, mas um objeto opaco na mesma casa bloqueia visão. Abrir uma
passagem preserva todos os efeitos dos objetos nela. Planejamento de rotas,
movimento contextual e deslocamento dos NPCs respeitam os mesmos obstáculos.

O contexto do Mundo inclui todos os objetos em `map.scene.objects`. O interpretador
recebe os visíveis e o narrador os encontra em `perception.visible_scene_objects`,
com fixação e efeitos. É possível caminhar até uma tocha pelo seu nome/id; remover,
apagar ou carregar esses objetos estáticos ainda não tem execução. O Pygame recebe
marcadores por uma projeção da sessão, sem calcular colisão ou visibilidade.

# Composição e ciclo de vida da partida

Tier 3 · [Aplicação](README.md) · [Visão geral](../../../README.md)

## Responsabilidades

- `infrastructure/openai_config.py`: configurações imutáveis, validação e resolução
  do modelo. Não importa o SDK, regras ou credenciais.
- `infrastructure/openai_services.py`: cria o cliente e os três adaptadores com a
  configuração resolvida. Controla o fechamento e registra a configuração.
- `bootstrap.py`: compõe sessão e `GameFlow` com esses serviços, pelo carregador
  compartilhado. Não importa Pygame nem cria outra sequência de execução.
- `simulator.py`: usa essa composição e entrega o fluxo já criado à janela.
  A janela mantém entrada, desenho e agenda de workers.

O coordenador e as regras continuam dependendo de contratos de aplicação, sem
importar a infraestrutura ou o SDK.

## Abrir uma partida

Exemplo de composição para uma entrada de aplicação:

```python
from trama.bootstrap import open_game

with open_game('src/trama/scenarios/dungeon_escape.json') as game:
    flow = game.flow
    configuration = game.services.metadata
    # A janela agenda os pedidos de flow; game.runner oferece a agenda sem janela.
```

`open_game` aceita arquivo, dados de cenário ou uma sessão já preparada. As
rolagens são injetadas ao construir a sessão; tentar trocá-las depois de preparar
uma sessão é rejeitado. `compose_game(session, services)` permite usar serviços
já abertos. Nenhuma dessas funções executa chamadas ou conduz um loop de NPCs.

A composição disponibiliza o fluxo e suas agendas sem executar mensagens.
A configuração e o fechamento do cliente são descritos em [Integração OpenAI](../ia/integracao-openai.md).

`open_situation(situation, ...)` usa essa mesma composição com dados do
[catálogo do simulador](../simulador/carregamento-de-cenarios.md#situações-reproduzíveis).
Ela injeta as rolagens e uma preparação determinística no `GameFlow`, que a
executa ao compor e ao reiniciar a sessão. O fluxo acrescenta o histórico
registrado após a abertura concluída. Sem situação, esses parâmetros são vazios
e a partida mantém seu início normal. Uma falha na preparação fecha os serviços
e impede entregar uma partida inválida à janela ou ao runner.

## Entradas e agendas compartilhadas

O comando `trama-simulator` usa `open_game` e entrega `game.flow` à janela.
Os mapas antigos são arquivos selecionados por `--scenario`; o runner que
montava serviços separadamente foi removido.

`game.runner` agenda os pedidos do mesmo tipo de fluxo, incluindo interpretação,
Mundo, turnos de NPCs, pausas para reação e narração. Isso é compartilhamento da
coordenação; não exige que o runner abra Pygame. Testes parciais de adaptadores
continuam com o escopo declarado e não são apresentados como partidas completas.

O cliente criado pela composição é fechado ao sair do contexto, inclusive se
carregar o cenário ou abrir a janela falhar. A política para cliente injetado,
pertencente ao chamador, continua na referência dos serviços.

## Relações e verificação

O carregamento usa [cenários compartilhados](../simulador/carregamento-de-cenarios.md). A janela e o runner consomem o mesmo `GameFlow`; o fechamento da composição libera os serviços mesmo quando o consumidor falha. Veja [a entrada sem janela](../interfaces/execucao-sem-janela.md) e [test_service_composition.py](../../../tests/integration/test_service_composition.py).

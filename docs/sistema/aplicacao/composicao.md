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

with open_game('pocs/simulador/dungeon.json') as game:
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

## Relações e verificação

O carregamento usa [cenários compartilhados](../simulador/carregamento-de-cenarios.md). A janela e o runner consomem o mesmo `GameFlow`; o fechamento da composição libera os serviços mesmo quando o consumidor falha. Veja [a entrada sem janela](../interfaces/execucao-sem-janela.md) e [test_service_composition.py](../../../tests/integration/test_service_composition.py).

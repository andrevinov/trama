# Execução sem janela pelo mesmo fluxo

`application/game_runner.py` oferece `GameRunner`, uma agenda síncrona para
`GameFlow`. A janela agenda os pedidos em workers; o runner os executa na thread
dona do fluxo. Ambos usam o mesmo coordenador e as mesmas operações públicas.
O runner não importa Pygame, SDK ou CLI, nem seleciona ações de NPCs, calcula
regras ou constrói contextos por conta própria.

## Entrada compartilhada

A [composição](service-composition.md) publica `game.runner`, criado sob demanda
e reutilizado para o mesmo `game.flow`. Exemplo com os serviços reais configurados
(as operações abaixo podem chamar o provedor):

```python
from trama.bootstrap import open_game

with open_game('pocs/simulador/dungeon.json') as game:
    opening = game.runner.start()
    result = game.runner.submit('Saio da cela e observo o corredor.')
    print(result.reply.text if result.reply else result.status)
```

Um consumidor que já possui um fluxo pode usar `GameRunner(flow)`. A janela
continua recebendo esse mesmo tipo de fluxo pela composição, sem depender do
runner ou da infraestrutura de IA.

| Método do runner | Entrada correspondente no fluxo |
| --- | --- |
| `start()` | `flow.start()`, seguido da execução dos pedidos pendentes |
| `submit(text)` | `flow.submit(text)`, seguido dos pedidos pendentes |
| `choose_opportunity(True/False)` | `flow.choose_opportunity(accept)`, seguido da continuação escolhida pelo fluxo |
| `reset()` | `flow.reset()`, que restaura e solicita a abertura |
| `run_until_input()` | Continua somente os pedidos já pendentes, sem nova mensagem |

As chamadas devem acontecer na thread que construiu o fluxo. `check_owner()`
valida isso antes de qualquer despacho externo. O runner executa exclusivamente
`pending_request.run()` e `flow.receive(id, result)` até não haver outro pedido.
É o `GameFlow` que decide quando interpretar, consultar o Mundo, avançar NPCs,
pausar para reação ou narrar.

## Resultado e pontos de parada

`RunResult` é uma observação da invocação:

- `status`: motivo pelo qual o runner parou, conforme tabela abaixo.
- `flow_status`: estado público do coordenador nesse momento.
- `accepted`: `True`/`False` retornado pela entrada; `None` ao apenas continuar.
- `requests`: pedidos despachados nesta invocação, com id, etapa, prompt,
  snapshot do contexto, resultado ou exceção e `applied` retornado por `receive`.
- `report`, `reply`, `error`: relatório, fala e erro públicos do fluxo.
- `awaiting_reaction`, `pending_request_id`: escolha pendente e pedido que ainda
  precisa ser executado, quando existirem.

Os contextos, resultados estruturados e relatório são copiados para observação;
alterá-los não muda os efeitos da partida. Erros mantêm a exceção original.
O resultado não contém uma segunda implementação do estado do jogo: consulte
`game.flow.session` para observar o estado real pelas projeções existentes.

| `RunStatus` | Significado |
| --- | --- |
| `idle` | Nenhuma interação foi iniciada. |
| `completed` | O fluxo entregou a resposta da interação. |
| `awaiting_reaction` | O fluxo aguarda uma escolha de oportunidade do jogador. |
| `failed` | O fluxo reportou falha; os efeitos anteriores permanecem. |
| `rejected` | A entrada não foi aceita, por exemplo mensagem vazia ou envio com pedido pendente; nenhum pedido foi despachado por essa tentativa. |
| `request_limit` | O limite de despachos desta invocação foi atingido; o próximo pedido permanece intacto. |
| `stale_result` | `receive` recusou um resultado antigo; o runner não despacha implicitamente o novo pedido. |

`completed` não significa que a ação física teve sucesso ou que o jogo terminou.
Uma ação bloqueada pode ter sido explicada normalmente: confira `report.status`,
impedimentos e critérios independentes. `applied=True` também inclui uma exceção
entregue ao fluxo e tratada como falha; não significa sucesso do provedor.

## Escolhas explícitas e falhas

O runner nunca usa uma reação nem deixa uma oportunidade passar automaticamente.
Depois da narração da pausa, devolve `awaiting_reaction`. Um consumidor recebe a
escolha do jogador ou uma escolha explicitamente declarada na fixture e chama
`choose_opportunity(True)` ou `choose_opportunity(False)`. Ausência de escolha
não equivale a recusa. Valores diferentes de booleanos são rejeitados pelo fluxo.

Uma pergunta off pode ser enviada enquanto a reação está pendente; ela usa o
mesmo desvio do fluxo e não resolve a escolha. Falha de narração pode deixar
`status=failed` e `awaiting_reaction=True`: o runner não esconde a falha nem
consome a escolha. A retomada explícita usa o estado e a continuação preservados.

Falhas retornadas pelo provedor são entregues uma vez ao fluxo. Não há retry
adicional do runner, fallback de plano conhecido ou repetição da execução para
obter aprovação. Interrupções como `KeyboardInterrupt` propagam ao chamador;
a mesma instância não despacha novamente aquele id. É preciso reiniciar ou
entregar ao fluxo um resultado já obtido, conforme a situação.

## Limite de despachos

Todos os métodos aceitam `max_requests`, inteiro não negativo ou `None`.
Zero permite iniciar/agendar a interação sem executar o primeiro pedido. Um
valor inválido é rejeitado antes de alterar a conversa. Após `request_limit`,
use `run_until_input(max_requests=...)` para continuar o pedido pendente, sem
reenviar a mensagem e sem repetir etapas já executadas.

Esse limite conta **FlowRequests nesta invocação**, não chamadas individuais do
SDK ou custo monetário. Uma interpretação pode executar uma correção interna,
conforme a configuração compartilhada. A migração live precisa declarar seu
orçamento real e verificar os logs; atingir esse limite é uma execução incompleta,
nunca um sucesso por ter pulado etapas. Não há um teto monetário implementado aqui.

## Verificação e adoção

```bash
poetry run pytest tests/integration/test_game_runner.py tests/integration/test_window_game_flow.py -q
```

Os testes locais usam regras, carregadores e coordenador reais, com decisões
externas explícitas e transporte simulado. Cobrem abertura, on/off, planos sem
etapas, movimento, NPCs, reações, retomadas, falhas, limites, reinício, snapshots e
thread dona. Comparam janela e runner em movimento, abertura, reação e reinício,
com critérios independentes de posição, PV e efeitos únicos.

`game_runner.request_dispatched` e `game_runner.stopped` complementam os logs
existentes, com correlação e sem duplicar prompts ou contar tokens por estimativa.
O teste da composição também exercita `game.runner` com os três adaptadores reais
e o transporte simulado. Não foram executadas chamadas pagas.

O passo 10 [migrou os oito casos contextuais](contextual-live-flow.md) para esta
API, incluindo abertura, NPCs, critérios e limite de chamadas no transporte.
Esse limite de chamadas é distinto de `max_requests` do runner. As outras cinco
suítes mantêm seus limites parciais/experimentais; ver o [plano](live-tests-plan.md).

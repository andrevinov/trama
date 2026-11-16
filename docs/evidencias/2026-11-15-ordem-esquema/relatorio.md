# Comparação de ordem de esquema — 15/11/2026

[Evidências](../README.md) · [Interpretação atual](../../sistema/ia/interpretacao-do-jogador.md)

Registro histórico extraído do README da POC; contrato anterior ao atual.

## Ordem das propriedades

O jogo usa `operation-first`: todas as variantes de ação começam por `operation`.
O formato antigo de movimento/portas começava por `segments`; os demais, por
`operation`. A documentação de [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs#key-ordering)
informa que a saída segue a ordem das chaves do esquema. O formato `legacy` é
mantido somente para controle no experimento; o jogo não alterna entre eles.

Na comparação local real de 15/11/2026, com Terra, seis chamadas e sem correções:

| Pedido | `legacy` | `operation-first` |
| --- | --- | --- |
| Olhar para a porta | `look`, correto | `look`, correto |
| Usar Retomar o Fôlego | `second_wind`, correto | `second_wind`, correto |
| “Vou avança até a porta da sala dos guardas e ficar diante dela.” | `challenge`, incorreto | `move` para `guard_door`, correto |

As requisições de cada par diferiram somente na ordem de `properties`. As
evidências locais estão em `logs/interpretacao/schema-order-terra-20261115/`.
O replay determinístico da resposta corrigida chegou à coluna 13, linha 6,
percorrendo 13,5 m e mantendo a porta fechada. Esse resultado é uma amostra de
três pedidos; não prova confiabilidade para toda linguagem natural. A checagem
descrita acima foi feita com o contrato anterior. O contrato atual também exige
request_parts; esses resultados históricos não são uma medição do novo contrato.

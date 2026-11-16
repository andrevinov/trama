# Demonstração offline de detecção de regressões

Tier 3 · [Qualidade](README.md) · [Visão geral](../../../README.md)

`test_regression_detection.py` demonstra offline que os critérios detectam as regressões motivadoras. São 17 verificações com controles positivos e negativos, composição e adaptadores reais e transporte simulado, sem nova suíte paga de poderes.

## O caminho exercitado

Cada execução usa `open_game`, carregadores reais, os adaptadores OpenAI e suas
instruções/esquemas atuais. Somente `client.responses.create` é substituído por
um transporte local com respostas explícitas. Um espião transparente registra o
plano que o adaptador realmente devolveu; não o reconstrói da expectativa.

As situações da dungeon vêm das mesmas fixtures e operações públicas da suíte
live. O caso de Surto usa o mapa legado real, com posição/porta declaradas antes
da construção. Iniciativa e primeiro ataque são resolvidos por operações reais,
com dados injetados pelo contrato da aplicação.

Cada situação passa por duas entradas:

- Janela real do Pygame, com driver SDL sem tela, usando `start`, campo de texto,
  `submit` e `poll`. O teste apenas entrega os resultados dos workers.
- `game.runner`, usando as mesmas operações de abertura e envio.

Em ambos, o `GameFlow` escolhe as etapas. Nenhum teste decide uma sequência
alternativa de NPCs, substitui a resolução de regras ou atribui estado privado.

## O que precisa reprovar

| Defeito | Controle negativo | Critério independente |
| --- | --- | --- |
| Omitir aproximação | Resposta estruturada propõe investigar com `allow_approach=False`, embora o caso exija entrada na cela | Exige entrada na Cela 4, percurso de 3 m e descoberta real dos itens; ficar no corredor reprova. |
| Executar só Surto de Ação | Resposta válida declara apenas o poder e omite o ataque | Exige eventos ordenados `action_surge`, `attack`, um golpe contra o alvo, PV e consumo da ação extra. |
| Não avançar NPC | Uma cópia da observação deixa o guarda ativo ou retira o evento de fim de turno | O mesmo avaliador live exige controle devolvido ao jogador e conclusão real do turno do guarda. |
| Perder oportunidade | Cópias isoladas retiram o evento, o dano ou o consumo da reação | Chegar ao banheiro não basta: são exigidos evento único, 5 de dano e reação do guarda usada. |
| Narrar deslocamento inexistente | Plano propõe somente observar; o narrador devolve uma frase dizendo que percorreu 3 m e entrou na cela | Texto não substitui posição, percurso e descobertas. A resposta é entregue, mas o critério mecânico reprova o caso. |

Os controles de NPC/oportunidade alteram **somente cópias entregues à avaliação**.
Não alteram sessão, regras, dados ou resposta do provedor em produção. Cada
observação original passa antes e depois do controle negativo, demonstrando
que a cópia defeituosa não adulterou a execução válida. Não foi criado um motor
alternativo ou um framework de mutações.

O cenário de Surto começa com a ação normal usada e o guarda com 9 PV, depois
de um ataque real com d20 fixado em 1 e dano de Graze já implementado. O pedido
deve gastar o uso de Surto e a ação extra e terminar com o guarda em 6 PV após
outro golpe de 3 de dano. Se ocorrer somente o poder, o guarda continua em 9 PV
e sobra uma ação extra: o controle reprova, embora o fluxo entregue uma resposta.
Esses números são expectativas literais do caso; o teste não chama novamente a
regra de dano para calcular o esperado.

## Igualdade não basta

Os quatro controles positivos comparam estado, relatório e pedidos efetivos
entre janela e runner: modelo, instruções, parâmetros de geração, esquemas e
contextos. A comparação preserva a ordem de chaves; somente `execution_id`
variável é retirado da observação comparada, sem alterar o pedido enviado.

Além dessa igualdade, **cada entrada precisa passar nos critérios independentes**.
Nos três controles de efeito do jogador, janela e runner chegam ao mesmo
resultado defeituoso, mas ambos reprovam. Assim, compartilhar o mesmo erro não
se transforma em evidência de correção.

Para aproximação, NPC e oportunidade, os testes chamam o mesmo `evaluate` da
suíte live. Não existe uma cópia mais permissiva desse avaliador. O critério de
Surto é local e verifica efeitos concretos; não acrescenta um caso pago aos oito
live tests de movimento contextual.

## Evidências e comando

```bash
poetry run pytest tests/integration/test_regression_detection.py -v
```

Para preservar os artefatos em um diretório escolhido:

```bash
poetry run pytest tests/integration/test_regression_detection.py -v --basetemp=/tmp/trama-regression-proof
```

Use um diretório descartável novo: o pytest administra o conteúdo de `--basetemp`.
Cada caso grava `proof.json` com estados, relatório, plano realmente devolvido,
fala, erros dos critérios e quantidade de chamadas ao transporte simulado.
As observações `evaluation_only` são explicitamente distinguíveis das reais.
Arquivos `window-*.jsonl` e `runner-*.jsonl` guardam os logs da aplicação, incluindo
os pedidos completos e os resultados simulados.

Os testes novos complementam as verificações anteriores de delegação da UI,
threads, reações, correções, orçamento e falha de NPC. Não mudam regras, prompts,
contratos ou os critérios dos oito casos live para fazê-los passar.

## Limites da prova

Essa demonstração verifica execução, integração e capacidade dos critérios de
detectar as ausências indicadas. Não mede a frequência com que um modelo real
escolhe cada plano, nem prova que ele sempre responderá do mesmo modo.

O controle de narração mostra que **texto afirmando deslocamento não aprova a
ausência do deslocamento exigido pelo caso**. Não implementa um verificador
genérico de verdade para português. Afirmações falsas que coexistam com os
efeitos mecânicos esperados ainda exigem avaliação semântica/revisão dos textos.
O experimento real foi executado depois, no
[experimento de 16/11/2026](../../evidencias/2026-11-16-movimento-contextual/relatorio.md): oito casos contextuais,
uma execução cada, todos aprovados mecanicamente, com ressalvas na revisão das
narrações. Esta demonstração offline não fez chamadas pagas; Surto continua sendo
uma prova local e não integrou essa bateria live.

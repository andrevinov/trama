# Movimento contextual pelo fluxo compartilhado

O passo 10 migrou os oito casos de
[`test_contextual_movement.py`](../tests/live/test_contextual_movement.py) para
`open_game` e `game.runner`. O trecho avaliado não chama interpretação, Mundo,
execução ou narração por conta própria. Não há outro loop de NPCs no teste.

## O que acontece em cada caso

1. Ler cenário, variações, dados e entradas declaradas da fixture.
2. Compor a partida pelo mesmo carregador, configuração e adaptadores do simulador.
3. Preparar a situação pela conversa do fluxo, usando operações públicas reais;
   conferir os dados consumidos e todas as pré-condições antes de consultar IA.
4. Pedir a descrição inicial da situação preparada por `game.runner.start()`.
5. Acrescentar o histórico registrado, quando houver, pela entrada validada.
6. Enviar a frase original por `game.runner.submit()`. O `GameFlow` escolhe todas
   as etapas, incluindo validação, NPCs e narração dos fatos executados.
7. Responder somente a escolhas explicitamente declaradas em `choices`.
8. Conferir os critérios independentes sobre o estado e o relatório reais.

É fluxo completo **para a interação avaliada**, a partir de uma situação
preparada. Não é uma conversa inteira gerada desde a cela inicial. A preparação
não testa interpretação. No caso do log, o histórico real é acrescentado depois
da abertura para preservar a janela recente que precedia a frase problemática;
a abertura gerada permanece como prefixo registrado, sem substituir o histórico.

Foram preservadas as oito frases, a geometria real e os critérios de movimento,
itens, portas, dano, recursos e restrições. O teste da iniciativa foi ampliado:
o Jogador continua sem aproximação/ataque gratuito; o guarda que venceu deve ter
seu turno resolvido e devolver o controle ao Jogador. Uma resposta inválida que
deixe o turno do guarda preso reprova o caso. Não basta iniciar o combate.

Nesse caso, `optional_world_rolls` declara um d20 adicional fixado em 1. Ele só
é usado depois de terminar a sequência obrigatória: permite que o guarda erre
um ataque legal, mas também que apenas espere sem rolar. O resto opcional é
registrado separadamente. Dados obrigatórios não consumidos continuam reprovando;
não se acrescentou uma reserva aleatória para esconder ações indevidas.

## Limites e escolhas

| Casos | Normal, sem correção | Máximo de chamadas lógicas ao SDK |
| --- | ---: | ---: |
| Sete casos sem turno adicional de NPC | 4 por caso | 5 por caso |
| Guarda vence iniciativa | 5 | 6 |
| Oito casos, uma vez cada | **33** | **41** |

O máximo inclui uma correção do interpretador. A abertura passou a ser uma
chamada real; a decisão do NPC também é contada. A tabela declara limites,
não autoriza a execução. A medição do passo 12 está registrada abaixo; uma
falha em outra execução pode terminar antes.

`CallBudget`, na infraestrutura, é compartilhado pelos três adaptadores. Reserva
antes de cada `responses.create`, inclusive correções e tentativas que falham.
Ao atingir o teto, impede o próximo despacho ao SDK; não pula a fase para fazer
o teste passar. Nenhum campo desse orçamento é enviado à IA.

O limite conta chamadas lógicas ao SDK, não dinheiro. Com os retries padrão em
zero, não há tentativas HTTP adicionais por retry. Para configurações diferentes,
os metadados registram também o limite superior de tentativas de transporte:
`max_calls * (max_retries + 1)`. Um cliente injetado continua sob responsabilidade
do chamador. Tokens e respostas continuam nos logs reais; não há preço presumido.

`choices` está vazio nos oito casos atuais. Uma oportunidade inesperada termina
como **inconclusiva**, sem aceitar nem recusar a reação. Novas escolhas precisam
ser declaradas, com revisão do orçamento e dos critérios. Uma escolha declarada
que não seja solicitada também reprova, em vez de ser silenciosamente ignorada.

## Evidências e classificação

Os arquivos persistentes continuam em
`logs/live/contextual_movement/<execução>/<caso>/`. `result.json` guarda:

- Configuração efetiva, cenário/caso e preparações declaradas.
- Estado original, situação preparada e estado ao final de cada interação.
- Abertura, mensagem e retomadas em `runs`, com seus ids de correlação reais.
- Etapas, contextos, planos/respostas, relatório, falas e erros observados do runner.
- Dados obrigatórios/opcionais usados e restantes; escolhas consumidas.
- Orçamento reservado/usado e critérios que falharam.

`trace.jsonl` mantém os prompts, esquemas, saídas brutas, correções, tokens,
movimentos e erros emitidos pela aplicação. Uma interpretação corrigida ocupa
um pedido do fluxo, mas suas duas chamadas ficam nos logs e no orçamento.
Uma tentativa barrada pelo orçamento pode ter seu payload registrado sem ter
sido enviada: use `call_budget.used` e os eventos de reserva para contar tentativas
ao SDK, em vez de contar apenas os payloads preparados.

| `outcome` | Interpretação |
| --- | --- |
| `passed` | Fluxo concluído e critérios satisfeitos. |
| `failed` | Preparação, resultado ou critério divergente. |
| `flow_failed` | O fluxo reportou falha de serviço, interpretação ou contrato; tipo/etapa e logs identificam a causa. |
| `inconclusive` | Execução incompleta por orçamento ou entrada ainda necessária. |

Inconclusivos e falhas reprovam no pytest; não viram skips ou repetições até
passar. A narração continua exigindo texto/on conforme o resultado, com texto
completo salvo para revisão; não há avaliação automática completa de coerência.

## Verificação e outras suítes

Os testes locais executam os oito caminhos pelos adaptadores reais, simulando
somente o transporte. Também verificam NPC que espera ou move/ataca, erro de
alcance, orçamento, correção, escolha ausente/declarada e pré-condição inválida.
Nenhuma chamada paga foi feita para implementar esta migração.

As outras cinco suítes foram revistas: dungeon e movimento antigo continuam
parciais; semântica é contrato do interpretador; comparação de contexto e esquema
são experimentos. Seus limites continuam explícitos no
[inventário](live-tests-audit.md). O passo 11 acrescentou a
[prova offline dos critérios](regression-detection.md), incluindo Surto e narração
sem efeito.

## Medição real do passo 12

Em 16/11/2026, o [experimento autorizado](experiments/step12-20261116T205209Z.md)
executou os oito casos uma vez, com o padrão da aplicação: **8 passed**,
33 chamadas reais, sem correções, retries, reruns ou inconclusivos. O guarda que
venceu a iniciativa moveu, atacou e encerrou seu turno; a oportunidade no caminho
do banheiro aplicou dano e consumiu a reação. Os critérios não foram alterados.

As 16 narrações foram lidas; há ressalvas de redação espacial e separação on/off,
além de linguagem que pode sugerir efeito mecânico inexistente. O relatório
registra essas limitações, uso de tokens, configuração e evidências. Uma execução
por caso não mede a frequência de acerto do modelo.

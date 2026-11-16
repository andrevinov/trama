# Movimento contextual pelo fluxo compartilhado

Tier 3 · [Qualidade](README.md) · [Visão geral](../../../README.md)

Os oito casos de `test_contextual_movement.py` usam `open_situation` e `game.runner`, como a seleção `--situation` na CLI.
O teste declara entradas e observa o fluxo compartilhado; a aplicação escolhe
interpretação, Mundo, execução, NPCs e narração. Não há outro loop de NPCs no teste.

## O que acontece em cada caso

1. Ler a situação do catálogo da aplicação e as entradas/critérios da fixture.
2. Compor a partida pelo mesmo carregador, configuração e adaptadores do simulador.
3. Preparar a situação pela conversa do fluxo, usando operações públicas reais;
   conferir os dados consumidos e todas as pré-condições antes de consultar IA.
4. Pedir a descrição inicial da situação preparada por `game.runner.start()`.
5. Deixar o fluxo acrescentar o histórico registrado após a abertura, quando houver.
6. Enviar a frase original por `game.runner.submit()`. O `GameFlow` escolhe todas
   as etapas, incluindo validação, NPCs e narração dos fatos executados.
7. Responder somente a escolhas explicitamente declaradas em `choices`.
8. Conferir os critérios independentes sobre o estado e o relatório reais.

É fluxo completo **para a interação avaliada**, a partir de uma situação
preparada. Não é uma conversa inteira gerada desde a cela inicial. A preparação
não testa interpretação. No caso do log, o histórico real é acrescentado depois
da abertura para preservar a janela recente que precedia a frase problemática;
a abertura gerada permanece como prefixo registrado, sem substituir o histórico.

As oito frases usam a geometria real e critérios de movimento, itens, portas,
dano, recursos e restrições. O teste da iniciativa exige que o Jogador não tenha
aproximação/ataque gratuito; o guarda que venceu deve ter
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

O máximo inclui uma correção do interpretador. A abertura e a decisão do NPC
são chamadas reais contabilizadas. A tabela declara limites, sem autorizar a
execução. Medições ficam nos relatórios datados; uma falha pode terminar antes.

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
- Situação preparada e estado ao final de cada interação; estado anterior à preparação nos logs `situation.preparation_started`.
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

## Verificação e cobertura

Os testes locais executam os oito caminhos pelos adaptadores reais com transporte
simulado e verificam orçamento, correções, escolhas e condições iniciais.
A [cobertura atual](cobertura-atual.md) distingue as demais suítes parciais e
experimentos. A [detecção de regressões](deteccao-de-regressoes.md) demonstra
que efeitos ausentes reprovam, mesmo quando a resposta é formalmente válida.

## Evidências de execução

O [experimento de 16/11/2026](../../evidencias/2026-11-16-movimento-contextual/relatorio.md)
registra uma execução por caso, resultados mecânicos, revisão narrativa, consumo
e configuração efetiva. Sua aprovação não é medição de repetibilidade.

## Casos e execução

| Caso | O que verifica |
| --- | --- |
| `investigar-cela-do-log` | Reproduz “Eu checo a cela, procurando por algo útil.” e o histórico real da falha. Entra na Cela 4, investiga e descobre os itens, sem coletá-los. |
| `pegar-espada-distante` | Aproxima-se da espada já descoberta e a coloca no inventário/equipamento real. |
| `atacar-com-aproximacao` | Declara apenas ataque, resolve iniciativa antes da caminhada, aproxima 4,5 m e consome a ação para golpear com a espada longa. |
| `ataque-com-movimento-insuficiente` | Tem só 1,5 m disponível: percorre esse trecho, para antes do alcance e preserva a ação. Não usa Dash ou Surto de Ação automaticamente. |
| `ataque-guarda-vence-iniciativa` | O guarda vence: não há aproximação nem golpe gratuito do jogador. O fluxo resolve o turno do guarda e deve devolver o controle ao jogador; resposta de NPC incompleta reprova. |
| `investigar-grade-fechada` | A grade barra a investigação. Não atravessa nem abre/destranca por conta própria. |
| `investigar-sem-sair-do-lugar` | A restrição impede a aproximação; não há movimento nem investigação remota. |
| `investigar-com-ataque-de-oportunidade` | Sair do alcance para investigar o banheiro provoca a reação: aplica 5 de dano, gasta a reação do guarda e continua a caminhada/investigação. O evento deve chegar ao relatório do narrador. |


As fixtures ficam em [tests/fixtures/contextual_movement](../../../tests/fixtures/contextual_movement/README.md).
O comando parte da raiz, exige a autorização do experimento e os requisitos da política:

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_contextual_movement.py -m live -v
```

Para um caso, acrescente `-k pegar-espada-distante`. A coleta `--collect-only -q`
não consulta a API. `TRAMA_CONTEXTUAL_ARTIFACTS` permite escolher o diretório
persistente dos artefatos. O orçamento declarado é imposto pelo transporte;
`max_requests` do runner limita despachos de fluxo e é uma medida diferente.

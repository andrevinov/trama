# Dificuldades contextuais e referências de memória — 17/11/2026

[Índice](../README.md) · [Bateria e critérios](../../sistema/qualidade/dificuldade-live.md) ·
[Implementação](../../sistema/aplicacao/avaliacao-de-dificuldade.md) · [Manifesto](manifesto.json)

## Resultado observado

Dez casos novos têm execução aprovada: três conversas de memória e sete tarefas
contextuais. Foram 14 execuções: 11 aprovadas e três falhas iniciais preservadas.
Usamos **40 chamadas ao SDK**, exatamente o teto agregado anunciado; nenhuma
suíte live anterior foi executada. O modelo efetivo foi `gpt-5.6-terra`, perfil
padrão da aplicação, sem retries de transporte, sem configuração experimental.
A configuração completa por tentativa está no [resumo](resumo.json).

| Rodada | Casos | Resultado | Chamadas |
| --- | --- | --- | --- |
| `20261117T201931-23506e89` | Dez casos novos | Sete dificuldades aprovadas; três memórias reprovadas | 28 |
| `20261117T205228-c3ac0aa6` | Somente as três memórias corrigidas | Três aprovadas | 9 |
| `20261117T205803-5d225ee7` | Somente o furto após estabilizar fatos da tarefa | Aprovado | 3 |

Uso medido: 478.239 tokens de entrada e 8.477 de saída, total 486.716; 135.139
entradas em cache. Não se estima valor monetário sem tabela do provedor.
As tentativas reais, suas mensagens e orçamentos, incluindo a correção de
interpretação do primeiro caso informativo, estão nos arquivos preservados.

## Falhas e correções

A regressão original da sessão `329e25bd16f8463e9b2b84b2d9a9a249`, interação
`2aabef3cf3734f7699a009ed0bc72047`, tinha `memory_ids` em Influence. A saída
estruturada agora separa fala e avaliação privada. A gravação original é
reproduzida offline: referência própria e relevante pode ser lida, sem divulgação;
referência de outro NPC é rejeitada. Sua fonte e hashes estão na fixture.

Na primeira medição, os dois casos sociais já deixaram `memory_ids` vazio,
mas preencheram `target_id` externo de Influence, que o domínio exige nulo.
Reforçamos isso no esquema específico de Influence, preservando a validação.
O alvo do pedido permanece na avaliação social. A nova resposta inválida também
virou fixture e regressão local. Após a correção, ambas as conversas concluíram
sem movimento, iniciativa, pagamento, objeto ou liberdade física automática.

O primeiro caso informativo não isolava a referência pública: a preparação tinha
um prisioneiro que já respondera à pergunta e uma abordagem pendente. A IA ainda
classificou a pergunta dirigida ao NPC como dúvida off. O caso passou a usar o
arquivista, numa situação sem interrupção pendente, pedindo seu conhecimento da
chave; a instrução passou a distinguir pergunta diegética de dúvida de regras.
O relato efetivamente compartilhou memória própria e preservou sua incerteza
temporal. A mudança de caso não torna a tentativa anterior aprovada.

A revisão local encontrou outra sequência possível: aceitar o disfarce durante
a aproximação mudava fatos transitórios do pedido de furto. A avaliação agora
se refere à tarefa de pegar a chave exposta sob observação; presença e visão
são verificadas no instante da execução. Uma regressão local abre a porta,
aceita o disfarce, aproxima e furta na mesma mensagem. Somente o live de furto
foi reavaliado após esse ajuste, usando as três chamadas restantes.

## Dificuldades e narração observadas

- Porta grossa fechada: fala normal não provocou detecção; a passiva do guarda
  refletiu desvantagem, sem ensinar conteúdo inaudível.
- Porta fina com frestas: grito foi ouvido e houve abordagem, sem ataque nem dano.
- Escuta ativa: dados baixos com desvantagem falharam sem revelar conteúdo;
  dados altos passaram e revelaram apenas a atividade prevista do guarda.
- Busca: Percepção encontrou roupa escondida; nenhum item foi transferido sem take.
- Furto: a aproximação legal foi realizada e a chave transferida somente após
  sucesso de Prestidigitação contextual.
- Inspeção: o guarda não encontrou a espada escondida com o dado baixo; a CD
  fixa de Influence para o disfarce foi preservada.

Revisamos as narrações salvas dos casos aprovados. Elas respeitaram os resultados
acima, o relato antigo da chave e a negociação sem libertação material.
A revisão humana é limitada a esses textos e não garante futuras respostas.

## Verificações locais e limites

A suíte nova offline cobre resultado automático, impossibilidade, CD típica,
rolagens e modificadores, julgamento ausente/inventado, fatos não fornecidos,
cache/reinício e privacidade. CDs fixas de Hide, detecção contra Furtividade,
Influence e magia continuam determinísticas. A regressão também verifica que
um julgamento acústico automático não elimina o total real de Furtividade e
que vantagem circunstancial não é descartada por uma segunda comparação.

Os testes de preparação/oráculos dos sete casos de dificuldade passam sem rede.
A verificação de contratos foi revisada explicitamente, atualizada com motivo e
conferida sem rede. `poetry check` passou. A medição dos sete primeiros lives
precede os refinamentos locais de redação privada e detecção de ocultos; esses
ramos adicionais têm testes offline, sem nova medição paga depois do teto.

As portas descritas nos casos são variações explícitas; o cenário padrão não
ganha material/espessura inventados. Alcances e atenuação geométrica são recortes
do Trama. D&D não impõe um modificador universal para todas as portas fechadas.
O cache acústico classifica barreiras/volume/finalidade; não é simulação física.

A execução local ampla teve 1.141 aprovações e 11 falhas em fixtures antigas:
dois doubles de SDK não forneciam os julgamentos exigidos e nove comparações
exigiam UUIDs de observação idênticos entre sessões/reinícios. Os doubles passaram
a declarar julgamentos locais; as comparações preservam memórias e seus conteúdos,
removendo somente IDs de correlação. Todos os 11 casos reprovados passaram na
reavaliação focada de 20 testes. A bateria focal de adjudicação, preparação,
contratos e fronteiras passou com 117 testes, incluindo os casos acrescentados
após a coleta ampla. Não houve outra execução integral depois desses ajustes.

## Preservação

Logs originais completos: `logs/live/difficulty/<rodada>/<caso>/trace.jsonl` e
`result.json`, com pedidos/respostas, correlação, contexto, estado, dados e erros.
O [manifesto](manifesto.json) inventaria seus hashes e tamanhos; o
[resumo](resumo.json) preserva resultados e configuração. Os
[contratos enviados](contratos-enviados.json) guardam instruções/esquemas reais,
deduplicados, e o [snapshot final](snapshot-final.json) registra fontes e fixtures
finais. A primeira rodada não é apresentada como medição do esquema corrigido.
Evidências históricas anteriores não foram reescritas.

```sh
poetry run python tools/check_evidence.py --manifest docs/evidencias/2026-11-17-dificuldade-contextual/manifesto.json --require-local
```

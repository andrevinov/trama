# Disposição social — 17/11/2026

[Cobertura atual](../../sistema/qualidade/cobertura-atual.md) ·
[Plano e critérios](../../sistema/qualidade/disposicao-live.md) ·
[Regra implementada](../../sistema/aplicacao/disposicao-social.md) ·
[Manifesto](manifesto.json)

## Escopo e configuração

O usuário solicitou disposição baseada em alinhamento, persona e memórias,
reavaliação somente com informação relevante e execução somente dos testes novos.
Usamos o corredor genérico jogável, `open_situation` e `game.runner.submit`, com
interpretador, Mundo, regras e narrador reais. A preparação determinística oferece
a abordagem a 12 m; não avalia a interpretação dessa preparação nem a dungeon
inteira. Todas as chamadas usaram a composição padrão `gpt-5.6-terra`, contexto
minimal, reasoning low, timeout 30 s, retries 0, até uma correção, SDK 3.49.0.
Tetos de saída: 1000 interpretação/narração e 2000 Mundo.

Foram **45 chamadas ao SDK**, dentro do teto agregado inicial de 48. Não houve
chamada de abertura nem execução das suítes live antigas. Os dados controlados
não substituem a resolução de Influence: somente valores do d20 são fixados.

## Execuções preservadas e correções

| Bateria local em `logs/live/social/` | Chamadas | Resultado original |
| --- | ---: | --- |
| `20261117T125757-e78c63de` | 21 | Sete reprovações, todas na primeira mensagem: o critério exigia alvo jogador, apesar de o contrato também permitir guarda destinatário da escuta. |
| `20261117T130036-0f151ea9` | 15 | Corrupto reprovado na oferta nova; memória interrompida na terceira mensagem, roupa azul. |
| `20261117T130410-5a2d7006` | 9 | Caso completo corrupto aprovado, após correção do registro de promessas e do vínculo da evidência. |

A ambiguidade de alvo foi corrigida aceitando ouvinte/falante no critério e
unificando a chave de reutilização de pedidos `listen`. Nenhuma falha original
foi apagada. A [reavaliação offline dos critérios](reavaliacao-criterios.json)
registra que os cinco casos de uma mensagem satisfazem os critérios corrigidos;
os dois casos multimensagem permaneciam incompletos. Isso não transforma a
primeira execução do pytest em sete aprovações.

A segunda bateria encontrou um erro real: a oferta condicionada de ouro estava
na fala e nos novos impactos de persona, mas o interpretador produziu `claims=[]`
e o Mundo não citou uma memória nova. O motor, corretamente exigindo informação
nova, reutilizou a recusa. As instruções passaram a registrar promessas como
compromissos declarados e a vincular a Claim ao interesse afetado. Não se presume
pagamento nem capacidade financeira confirmada.

Na conversa de memória, o guarda já estava ouvindo. Diante da roupa azul, o Mundo
não pediu nova avaliação; a decisão e a custódia permaneceram iguais. O critério
exigia um evento de avaliação mesmo para informação irrelevante e foi corrigido
para aceitar ausência de avaliação quando há uma decisão prévia preservada.
O teste parou ali: **a alegação de filiação nobre não chegou a ser executada live**.
Esse caso não recebe aprovação de fluxo completo. Reavaliação por nova alegação
ouvida, falsidade não confirmada e irrelevância têm regressões locais aprovadas.

Após essas correções, a última execução focada no corrupto completou as três
mensagens com nove chamadas e apenas um d20. O teste restante de memória não foi
repetido; a ausência de conclusão live é uma limitação desta medição.

## Comportamentos observados

| Pedido/perfil | Alinhamento / persona / memória | Resultado observado |
| --- | --- | --- |
| Pedido original ao profissional | 0 / 2 / 0 | Hesitante; d20=20, total 19 contra CD15; aceita escuta, mantendo distância/custódia. |
| Compassivo | 1 / 4 / 0 | Disposto sem dado; aceita ouvir. |
| Sádico | -1 / -4 / 0 | Indisposto sem dado; recusa a pausa sem atacar nem se mover. |
| Protocolo, leal e neutro | 1 / 2 / 0 | Disposto sem dado. |
| Mesmo protocolo, caótico e neutro | -1 / 2 / 0 | Hesitante; sucesso com d20=20. |
| Corrupto, última execução, sem incentivo | 0 / 0 / 0 | Hesitante; d20=1 falha, mantendo abordagem sem combate. |
| Corrupto, nova recompensa | 0 / 4 / 1 | Disposto; reavaliação verdadeira, sem dado adicional; oferta conta como relato do jogador. |
| Corrupto, mesma recompensa repetida | Resultado anterior preservado | Reutilizado, sem novo dado ou nova avaliação. |

Revisão da prosa salva: as respostas observadas mantiveram os interlocutores a
distância, escuta limitada e custódia; o sádico negou clemência verbalmente. A
recompensa não foi paga; não houve chave entregue, porta aberta, libertação,
golpe ou avanço inventado nas interações examinadas. Uma aprovação mecânica não
certifica toda prosa futura. As pontuações são **política do Trama**, não fórmula
oficial de D&D nem obrigação de conduta imposta pelo alinhamento.

## Verificação local final e parecer

Somente arquivos novos de testes foram executados: **61 aprovações** em
`test_social_disposition.py`, `test_social_judgment.py`,
`test_social_live_scenarios.py` e `test_social_transport.py`. Cobrem todos os
alinhamentos, limiares, persona, fontes, informação não ouvida/irrelevante,
reutilização, novo relato, reset, transporte e ausência de liberdade gratuita.
Contratos de IA revisados e conferidos offline; `poetry check` e verificação de
diff também passaram. A suíte local completa não foi executada. Os testes antigos
de conversa foram migrados para a nova semântica, sem execução nesta rodada.

O recorte separa a possibilidade narrativa de uma rolagem de Carisma e impede
que aceitar ouvir seja equivalente a deixar um prisioneiro fugir. Os pesos são
auditáveis e limitam o poder do alinhamento. A interpretação dos impactos e a
extração de informação continuam dependentes do modelo; o erro de oferta
mostra por que a evidência live não pode ser substituída por testes do cálculo.
A sequência completa de nova nobreza permanece o ponto sem medição live final.

## Preservação

`revisao-inicial.json` guarda fontes/contratos da primeira bateria;
`revisao-final.json` guarda o recorte final. O manifesto inventaria snapshots,
critérios, relatório, configuração e hashes dos `result.json`/`trace.jsonl`
originais, com consumo de tokens e identificação das execuções. Logs brutos
permanecem locais e ignorados pelo Git. Nenhum inventário histórico foi alterado.

```bash
poetry run python tools/check_evidence.py --manifest docs/evidencias/2026-11-17-disposicao-social/manifesto.json --require-local
```

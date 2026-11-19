# Foco da conversa no conselho — 19/11/2026

[Índice](../README.md) · [Casos e orçamento](../../sistema/qualidade/foco-conversa-live.md) ·
[Resumo medido](resumo.json) · [Manifesto](manifesto.json)

## Resultado e consumo

O usuário autorizou três casos, uma tentativa comportamental por caso e teto
agregado de 30 chamadas ao SDK. A primeira rodada com rede teve dois aprovados
e um reprovado. Após a correção adicional, uma nova tentativa especificamente
autorizada aprovou o terceiro caso: **os três casos têm execução aprovada**, com
a falha anterior preservada. Não houve repetição automática até passar.

| Rodada | Caso | Resultado | Chamadas |
| --- | --- | --- | ---: |
| `20261119T172501-cac7620c` | Os três casos | Três aberturas impedidas por DNS no sandbox; sem resposta do provedor. | 1 + 1 + 1 |
| `20261119T172546-f6eb7fc2` | `apresentacao-com-gesto` | Abertura, fala/gesto, resposta executada e off aprovados. | 5 |
| `20261119T172546-f6eb7fc2` | `reencontro-e-proposito` | Falha ao validar `active` sem motivo, antes da resposta. | 3 |
| `20261119T172546-f6eb7fc2` | `proposta-de-tregua` | Proposta, resposta sobre garantias e consulta off aprovadas. | 6 |
| `20261119T173401-22892613` | `reencontro-e-proposito` | Nova tentativa autorizada após corrigir estado ativo; abertura, fala e off aprovados. | 5 |

Total: **22 tentativas ao SDK**, 19 respostas. Após o erro de DNS, a execução
com rede foi autorizada e o teto reduzido para nove por caso, preservando o
limite agregado. A verificação adicional foi autorizada com teto de nove
chamadas, dentro do saldo; usou cinco. Erros de
ambiente não contam como aprovação comportamental e permanecem nos artefatos.

Modelo `gpt-5.6-terra`, perfil padrão da aplicação, sem overrides experimentais.
Os contadores recebidos somam 260.411 tokens de entrada e 5.674 de saída:
**266.085 tokens totais**. Cache/raciocínio estão detalhados no resumo, sem somar
novamente. Não há estimativa monetária nem consumo informado para as tentativas
sem resposta.

## Falha original e observação real

Na sessão `b112a56bb510474d90e5a6dd9aa104fb`, interação
`5c7563f6134f4d45bfb5eb229c9d5e8b`, Tristan Knot se apresentou e estendeu a mão.
Duas respostas de Voss foram rejeitadas porque seus focos resumiam a fala, sem
serem citações literais. As sete linhas pertinentes, com hashes e referências,
estão em `tests/fixtures/conversation_focus/regression_source.json`.

Foco passou a ser rótulo semântico; pontos, termos, motivos e limites continuam
literais. As duas respostas rejeitadas passaram na reprodução local pelo runner,
com os focos originais, sem relaxar compromissos ou objetivos privados do jogador.

No live da apresentação, o foco foi “reencontro e apresentação”, não literal.
Voss respondeu e reconheceu as trocas de prisioneiros. A consulta off informou
que não houve aproximação ou contato físico registrado. “Aceito o cumprimento”
permaneceu reconhecimento verbal, sem aperto de mão produzido pelo motor.

Na proposta, o foco foi “garantias para trégua e recuo”, também não literal.
Trinta dias e recuo simultâneo foram preservados; Voss pediu garantias e citou
o ataque de Auren. O off distinguiu proposta pendente de acordo aceito. Não
houve retirada militar ou transferência territorial por fala.

## Segunda falha e correção posterior

No reencontro, a IA declarou `status="active", reason=null` ao continuar uma
conversa. O código exigia motivo mesmo sem mudança de estado e rejeitou a fala.
Os registros estão em `tests/fixtures/conversation_focus/active_status_source.json`,
com caminho, número e hash das linhas originais.

A correção posterior normaliza somente `active` sem motivo em conversa nova ou
já ativa, registrando continuação sem transição. Retomar conversa suspensa ou
encerrada, fechar e suspender continuam exigindo motivo literal. A resposta real
passou na reprodução local; contrapartes rejeitam retomada indevida sem alterar
o estado anterior.

Após autorização específica, o reencontro foi reavaliado na rodada
`20261119T173401-22892613`, com cinco chamadas. A abertura, a resposta executada
e a consulta off passaram. Voss lembrou as trocas de prisioneiros e pediu uma
proposta; o off explicou o assunto sem inventar acordo. A falha da primeira
rodada permanece reprovada, sem reclassificação retroativa. As duas primeiras
aprovações são anteriores a esse refinamento de estado e não foram repetidas.

## Revisão narrativa e limites

Foram lidas as respostas on/off das três execuções completas. Preservaram distância,
ausência de contato, caráter pendente da oferta e segredo de Valdren. Uma abertura
acrescentou “rumor distante do vestíbulo”, ambientação sem evento sonoro registrado:
a prosa não foi certificada como reprodução exata de toda percepção do motor.

Os critérios exigem resposta executada e ouvida, termos preservados, ausência de
efeitos físicos não solicitados e consulta off sem avanço. Permitem redações e
iniciativas legais diferentes; não exigem foco específico no live. As regressões
locais cobrem explicitamente os rótulos problemáticos, fontes literais e controles
negativos. Uma rodada não mede repetibilidade. O caso reprovado terminou antes
da fala de Voss e da consulta off, sem aprovação dessas etapas.

## Preservação

Logs/resultados das três rodadas permanecem em `logs/live/conversation_focus/`.
As duas rodadas com respostas incluem `source_snapshot/` com os arquivos
pertinentes à versão medida, cenário e entradas. A primeira antecede a correção
de estado ativo; a última a inclui. O manifesto
inventaria bytes e hashes. O resumo versionado guarda configuração, consumo,
respostas, falhas e fases alcançadas, sem credenciais. As fontes históricas e
os resultados desfavoráveis não foram reescritos.

## Verificação local final

A suíte completa iniciada antes da correção de estado ativo terminou com
**1.312 aprovações em 390,14 s**. Após essa correção e três controles novos,
as seleções de foco/agência/vínculos/casual (71) e conversa/audição/contratos/
fronteiras (141) passaram. Há sobreposição entre as seleções; não se somam como
casos distintos. A coleta atual contém 1.315 testes locais. Não foi repetida
a suíte completa após o refinamento final.

Contratos de IA foram revisados com justificativa explícita e conferidos sem
rede; esquemas e estruturas permaneceram. Metadados e diff conferem. A conferência
do manifesto exige arquivos locais para validar também logs e snapshots.

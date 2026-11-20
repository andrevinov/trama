# Foco semântico da conversa — regressão local e live

Tier 3 · [Qualidade](README.md) · [Política obrigatória](politica-live-tests.md)

## Falha e correção

Em 19/11/2026, no conselho, a apresentação de Tristan Knot com mão estendida
produziu duas respostas válidas de Voss bloqueadas pelo mesmo motivo. Os rótulos
“reencontro sob salvo-conduto” e “propósito da audiência” resumiam suas falas,
mas o código exigia que fossem citações literais. Primeiro falhou `player_action`,
depois `npc_agency`; a narração recebeu somente as rejeições.

`focus` agora é rótulo semântico de até 160 caracteres, sustentado pela fala e
pelo contexto percebido. Não cria fatos, compromissos ou objetivos do jogador.
Pontos, termos de propostas, motivos de transição e limites continuam literais.
Não há descarte geral de metadados, nova chamada de correção ou aceitação de
termos que não foram falados. Veja o [contrato](../aplicacao/estado-da-conversa.md).

A medição revelou ainda `status=active, reason=null` ao continuar uma conversa.
O código agora normaliza somente essa repetição em conversa nova/já ativa;
fechar, suspender ou retomar conversa inativa continuam exigindo motivo literal.
O caso foi preservado em `active_status_source.json` e reproduzido localmente
com a resposta real. Uma verificação adicional autorizada aprovou esse caso,
preservando o resultado reprovado anterior.

As sete linhas pertinentes da sessão original estão preservadas em
`tests/fixtures/conversation_focus/regression_source.json`, com caminho, número,
hash SHA-256 da linha e conteúdo original. A reprodução local usa as respostas
reais rejeitadas, sem reescrever seus focos. Essa gravação não alimenta o live.

## Casos, fluxo e critérios

`tests/live/test_conversation_focus_live.py` usa `open_game` com o mesmo
`generals_council.json` selecionável por `--scenario` no simulador. Abertura,
interpretação, Mundo, eventual revisão/agência, narração e consulta off passam
por `game.runner`. Não há setup artificial, coordenador alternativo ou contexto
pré-redigido. As entradas ficam em `tests/fixtures/conversation_focus/cases.json`.

| Caso | Entrada e expectativa | Teto de chamadas ao SDK |
| --- | --- | ---: |
| `apresentacao-com-gesto` | Frase exata da sessão: apresentação e mão estendida; fala ouvida, resposta de Voss executada, sem rejeição por foco. | 10 |
| `reencontro-e-proposito` | Saudação, lembrança das trocas de prisioneiros e intenção de conversar; resposta registrada sem proposta inventada. | 10 |
| `proposta-de-tregua` | Oferta de trinta dias com recuo simultâneo; termos conhecidos preservam duração e simultaneidade; Voss pode aceitar, recusar, questionar ou contrapropor. | 10 |

Cada caso abre uma sessão independente, envia uma mensagem on e uma off. Não se
exige rótulo específico, foco não literal ou redação única do modelo. A regressão
local é que garante a aceitação dos dois rótulos efetivamente rejeitados.

Critérios independentes: fluxo completo, nenhuma falha/interrupção, fala do
jogador ouvida, resposta `say` de Voss executada e ouvida, contribuição dele no
registro, oferta explícita preservada e ausência de proposta em cumprimento
social. O jogador não solicita deslocamento, gasto de recurso, alteração de
porta ou combate. Deslocamento legal do NPC pode variar; não se exige que ele
aperte a mão, esteja sempre imóvel ou aceite termos. Dados inesperados reprovam:
essas entradas não exigem teste de perícia ou combate.

A consulta off despacha apenas narração, sem mudar estado mecânico, conversa,
intenções ou conhecimento. A narração não recebe o relatório reservado de Voss.
Revisão humana dos textos salvos deve conferir contato físico e distância,
coerência com a fala realmente executada, privacidade, culpa institucional de
Auren e ausência de aceitação/cumprimento inventados. As verificações automáticas
não certificam toda a prosa. Testes locais exercitam os mesmos critérios com
respostas fixas e contrapartes sem fala, sem termos ou com estado off alterado.

## Configuração, autorização e limites

**Uma tentativa por caso, três casos, teto agregado de 30 chamadas lógicas ao
SDK.** Esperam-se aproximadamente 15–18 chamadas nas fases normais; o teto cobre
correção limitada do interpretador e decisões adicionais escolhidas pelo fluxo.
`CallBudget` reserva antes do SDK, contando tentativas que falham. Não é limite
monetário ou de tokens. Configuração efetiva, limites de saída, timeout, modelo
e retries são os da aplicação, sem override experimental; `TRAMA_OPENAI_MODEL`
continua sendo respeitado. O padrão usa zero retries de transporte.

Criar/coletar estes testes não autoriza chamadas pagas. Solicitar autorização
para esta bateria concreta antes de usar `RUN_OPENAI_LIVE_TESTS=1`. Exige
`OPENAI_API_KEY` no ambiente. Não repetir casos até passar. Orçamento esgotado,
falha de serviço ou decisão pendente são execução incompleta, preservada como
falha/inconclusivo, sem trocar o resultado por uma resposta conhecida.

```bash
poetry run pytest tests/live/test_conversation_focus_live.py::test_live_conversation_focus --collect-only -q
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_conversation_focus_live.py::test_live_conversation_focus -m live -v
```

## Evidências e alcance

Artefatos por rodada/caso em
`logs/live/conversation_focus/<rodada>/<caso>/{trace.jsonl,result.json}`. A variável
`TRAMA_FOCUS_ARTIFACTS` altera a pasta-base. São salvos inclusive em falhas:
configuração, hash do cenário, pedidos/respostas reais, correlação, planos,
relatórios, estado antes/depois, texto, dados, orçamento, tokens e erros.
Os logs da aplicação preservam o conteúdo enviado ao SDK, sem credenciais.

`TRAMA_FOCUS_CALL_CAP` pode reduzir o teto por caso, nunca aumentá-lo. Após erro
de ambiente, uma nova tentativa explicitamente identificada deve preservar a
anterior e respeitar o saldo agregado autorizado; não é repetição de resultado
comportamental até obter aprovação.

Medição autorizada em 19/11/2026: a primeira rodada com rede teve dois aprovados
e uma falha de metadados. Após corrigir `active`, uma nova tentativa especificamente
autorizada aprovou o terceiro caso. **Os três casos têm execução aprovada**, com
a falha anterior preservada. Total: **22 de 30 chamadas**, incluindo três aberturas
impedidas por DNS. Veja o
[relatório com falhas, consumo e limites](../../evidencias/2026-11-19-foco-conversa/relatorio.md).
Essas observações não garantem todas as respostas futuras.

A regressão posterior de [pontuação em falas citadas](pontuacao-conversa-live.md)
tem três casos adicionais em outra função do mesmo módulo, com orçamento e
autorização próprios. Executar o módulo inteiro seleciona ambas as baterias;
use os seletores explícitos acima para limitar esta execução aos casos de foco.

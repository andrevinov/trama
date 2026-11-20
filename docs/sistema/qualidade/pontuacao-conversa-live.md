# Pontuação em falas citadas — regressão local e live

Tier 3 · [Qualidade](README.md) · [Política obrigatória](politica-live-tests.md)

## Falha e recorte corrigido

Na interação `7053277b1c2848feb3536be984a29bab`, de 19/11/2026, a fala sobre
o Tratado da Ponte foi rejeitada nas duas tentativas do interpretador porque a
IA acrescentou um ponto após “reinos”, antes ausente no fechamento das aspas.
O trecho correspondia à fala proposta, mas não ao texto bruto do jogador.
As linhas pertinentes estão em
`tests/fixtures/conversation_punctuation/regression_source.json`, com caminho,
número, timestamp e hash SHA-256 originais. Essa evidência não é reescrita.

A comparação agora admite espaços, equivalência Unicode NFC, formatos de aspas
e um ponto final simples ao fim do trecho. Não apaga pontuação interna nem troca
palavras, maiúsculas, números, negações, condições, perguntas ou reticências.
Não permite cortar palavras ou números decimais/de milhar. Os dados e os textos
armazenados são preservados. A normalização é só de comparação; não é prova de
equivalência semântica ou de que uma seleção parcial capturou toda a intenção.

Pontos, termos, motivos e limites continuam ancorados na fonte. Erros identificam
o campo, seu trecho e se a comparação foi com a fala proposta, a mensagem original
ou a fala executada. A correção limitada da IA recebe esse motivo específico,
evitando trocar um foco que já era válido sem localizar o trecho problemático.
`request_parts` continua exigindo origem literal na mensagem original; não foi
relaxada a autorização de ações ou de recursos.

## Casos novos e fonte única

Os três casos estão em `tests/fixtures/conversation_punctuation/cases.json`,
executados por `test_conversation_focus_live.py::test_live_conversation_punctuation`.
Reutilizam observação e registro da bateria de foco, incluindo `open_game`, o
cenário real `generals_council.json`, serviços/configuração reais e `game.runner`.
Não há cópia de contexto, esquema, prompt de sistema, resposta do modelo ou
coordenação do jogo dentro desta bateria.

| Caso | Critério adicional |
| --- | --- |
| `pontuacao-posicao-de-auren` | Mensagem exata com duas falas separadas por “falo”; posição, retorno dos cidadãos e convivência preservados. |
| `pontuacao-aspas-e-condicao` | Aspas tipográficas, quebra de linha e “digo”; trinta dias, simultaneidade e condição de fiscalização nos termos. |
| `pontuacao-negacao-e-prazo` | Recusa de retirada unilateral, trinta dias em vez de trezentos e fiscalização condicional; sem perda da negação. |

Cada caso abre uma sessão nova, envia uma mensagem on e uma consulta off. O caso
original não congela o histórico ou os IDs antigos: a IA recebe o estado atual
e escolhe anotações novas. A reprodução local das duas respostas rejeitadas é
da etapa de autorização que falhou, sem afirmar reproduzir toda a sessão anterior.
Outros controles usam o runner com decisões fixas para exercitar os efeitos.

Critérios independentes: nenhuma falha/interrupção, fala executada e ouvida por
Voss, resposta dele executada e ouvida, conteúdos essenciais preservados, condição
e duração nos termos quando há oferta explícita. A consulta off deve usar somente
narração e conservar estado, conhecimento, intenções e conversa. Não deve haver
movimento do jogador, gasto de recurso, combate ou alteração de porta por fala.
Nenhum caso obriga aceitação, resposta literal única ou uso de correção automática.

Voss pode aceitar, recusar, questionar ou contrapropor. O primeiro caso admite
classificação como posição/pedido ou proposta, conforme a interpretação; os
demais têm oferta explícita. Controles locais removem conteúdo e termos para
mostrar que os critérios reprovam resultados materialmente diferentes. A revisão
humana deve conferir narração on/off, causalidade, condições, negações e segredos:
sentinelas textuais não compreendem toda prosa nem garantem respostas futuras.

## Limites e autorização

Três casos, **uma tentativa por caso, teto de dez chamadas ao SDK por caso e 30
no total**. Abertura/on/off usam os mesmos parâmetros e modelo do simulador,
respeitando `TRAMA_OPENAI_MODEL`, sem override experimental. O teto inclui as
correções limitadas que o fluxo decidir solicitar, não é limite monetário.
`CallBudget` conta reservas antes do SDK; erros e orçamento esgotado reprovam.
Não repetir até passar nem substituir uma falha por resposta congelada.

Criar ou coletar não autoriza chamadas pagas. A execução desta bateria concreta
exige autorização explícita e `OPENAI_API_KEY`; não reutiliza o orçamento da
medição de foco de 19/11/2026. O módulo também contém os três casos antigos:
use o seletor de função para rodar somente os novos.

```bash
poetry run pytest tests/live/test_conversation_focus_live.py::test_live_conversation_punctuation --collect-only -q
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_conversation_focus_live.py::test_live_conversation_punctuation -m live -v
```

Resultados, pedidos reais, configuração, consumo e falhas ficam sob
`logs/live/conversation_punctuation/<rodada>/<caso>/{trace.jsonl,result.json}`,
inclusive em falha. `TRAMA_PUNCTUATION_ARTIFACTS` altera a pasta-base;
`TRAMA_PUNCTUATION_CALL_CAP` apenas reduz o teto por caso. Logs não versionam
credenciais. Criação e validação local não representam aprovação live; ainda
não há medição paga desta bateria.

## Verificação local em 20/11/2026

A suíte padrão completa terminou com **1.347 testes aprovados em 388,76 s**,
sem chamadas pagas. A seleção focada anterior teve 121 aprovações e está contida
nessa suíte. Foram coletados três casos live novos, sem execução de serviços.

Os testes revalidam os dois planos realmente rejeitados contra a mensagem
original, exercitam o runner com decisões fixas e verificam que a correção da IA
recebe campo, trecho e fonte específicos quando há conteúdo realmente inventado.
Controles negativos preservam palavras, números, negações, condições e sinais
significativos. A auditoria reconstruiu as projeções duas vezes com resultado
idêntico; foram revisadas 15 diferenças de instruções e textos, sem mudança de
esquemas, estruturas ou contratos. Metadados, diff e links locais conferem.

Não há aprovação live atribuída a essa validação local. A execução paga da
bateria continua condicionada à autorização separada descrita acima.

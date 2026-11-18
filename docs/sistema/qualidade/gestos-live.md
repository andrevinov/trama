# Comunicação gestual: live tests

Tier 3 · [Qualidade](README.md) · [Visão geral](../../../README.md)

Quatro situações novas pelo fluxo oficial `open_situation` e `game.runner.submit`,
com interpretação, Mundo, possível acompanhamento do destinatário e narração
da aplicação. A preparação é determinística e não mede a interpretação do
histórico anterior. Não há janela nem controle de renderização nesta avaliação.

| Situação | Critério independente |
| --- | --- |
| `gesto-prisioneiro-sem-visao` | Frase da regressão em [8,20], prisioneiro em [4,18]; falha `gesture_not_visible` explica falta de linha de visão, sem fala ou efeito do sinal. |
| `gesto-aceno-visivel` | Companheiro ao lado vê um aceno e recebe decisão própria de resposta; sem som ou confirmação obrigatória de uma história desconhecida. |
| `gesto-piscadela-proxima` | Piscadela a 1,5 m, em luz normal; a avaliação visual contextual permite percebê-la e há decisão de resposta do companheiro. |
| `gesto-piscadela-distante` | Corpo visível a 28,5 m, piscadela não notada: avaliação impossível ou CD superior à passiva. Sem resposta ao sinal que não chegou. |

O primeiro usa a dungeon e preparação pública da abordagem. Os demais reutilizam
`watched_conversation.json`; o vigia secundário tem visão/audição desabilitadas
na variação declarada para isolar o destinatário e a comunicação visual.
Não existem dados novos previstos; passiva não rola dados.

Fixtures: `tests/fixtures/gestures/cases.json`. O registro
`regression_source.json` preserva quatro eventos da sessão original, caminho,
linhas e hashes; não é um contexto congelado injetado no modelo.
Os controles offline em `test_gesture_live_scenarios.py` reprovam movimento
indevido, omissão da comunicação e ausência do impedimento esperado.

Além de posição, portas, recursos e inventário, os critérios verificam operação,
destinatário, recepção, observadores visuais, ausência de audição automática,
pedidos de dificuldade e decisão de resposta quando devida. A revisão humana
da prosa deve conferir explicação do bloqueio, nenhuma compreensão/coação
automática, nenhuma confirmação inventada ou leitura de pensamentos. Texto
não vazio não certifica esses critérios semânticos.

**Preparações e critérios verificados offline; execução paga requer autorização.**
Uma tentativa por caso, sem repetição até passar, teto de **18 chamadas do SDK**
(4 + 5 + 5 + 4), incluindo correção do interpretador e eventual `npc_agency`.
O caminho normal usa entre 12 e 14 chamadas. Não inclui abertura ou outras suítes.
Criar os testes não autoriza chamadas pagas, conforme a [política](politica-live-tests.md).

```bash
poetry run pytest tests/live/test_gestural_communication_live.py --collect-only -q
# Somente após autorização específica, com OPENAI_API_KEY configurada:
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_gestural_communication_live.py -m live -v
```

Respeita a composição/configuração normal e `TRAMA_OPENAI_MODEL`. Salva pedidos
reais, respostas, contextos, configuração, estado antes/depois, dados, orçamento,
tokens, IDs e erros em `logs/live/gestures/<execução>/<caso>/{trace.jsonl,result.json}`,
inclusive falhas. `TRAMA_GESTURE_ARTIFACTS` muda apenas a pasta.
Erros de serviço, orçamento ou fluxo incompleto reprovam; não há plano substituto.

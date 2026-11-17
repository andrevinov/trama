# Live tests de conversa antes do combate

Tier 3 · [Qualidade](README.md) · [Visão geral](../../../README.md)

## Objetivo, escopo e preparação

`tests/live/test_parley.py` avalia a [regra geral de abordagem](../aplicacao/conversa-antes-do-combate.md)
no cenário da dungeon. Usa `open_situation`, a composição padrão de serviços e
`game.runner`: abertura, interpretação, Mundo, execução, eventuais turnos de NPCs
e narração. Não há coordenação paralela, respostas substituídas ou prompts de teste.
A preparação determinística apenas leva o jogador ao corredor (coluna 8, linha 22),
sem consumo de dados; não é uma partida inteira interpretada desde a cela.

As quatro situações estão em `src/trama/scenarios/situations.json`, acessíveis na
janela por `--situation ID`; reiniciar restaura preparação e rolagens. As frases,
limites e expectativas ficam em `tests/fixtures/parley/cases.json`. A primeira
mensagem reproduz a interação de 16/11/2026: “Vou direto até a última cela e checo
se ela está destrancada.” Os perfis sensoriais resolvem passos e pedido de ajuda evidentes sem rolagens.
O prisioneiro acorda, o guarda ouve a emissão, investiga e abre a porta.
As rolagens declaradas cobrem somente a decisão social e a iniciativa posteriores.

## Casos e critérios independentes

| Situação | Critério principal | Chamadas normais / teto |
| --- | --- | --- |
| `abordagem-distante` | Interromper após 3 m do jogador, em [8,20]; guarda em [10,6], conversa pendente, sem iniciativa/dano. | 4 / 5 |
| `conversa-evita-combate` | Avaliação inicial concede apenas escuta: disposto sem dado, hesitante com Persuasão. Custódia preservada. | 7 / 9 |
| `conversa-falha-inicia-combate` (id histórico) | Perfil neutro/cauteloso e dado baixo recusam escuta sem iniciativa nem aproximação automáticas. | 7 / 10 |
| `conversa-jogador-ataca` | Ataque explícito dispensa teste social; guarda vence iniciativa antes de qualquer movimento do jogador. | 8 / 10 |

No caso de ataque explícito o guarda ainda está distante demais para golpear: pode
aguardar ou caminhar até 9 m, sem dano ao jogador. O pedido de ataque permanece
não executado antes da vez do jogador. Os critérios verificam coordenadas,
relatórios, posições enviadas no primeiro `npc_turn`, dados realmente consumidos,
PV, recursos, inventário, portas e ausência de erros do NPC. Não calculam o
esperado chamando o algoritmo de movimento/visão ou tomando o plano como prova.

O sucesso não fixa disposição hesitante: ela vem da nova avaliação de persona,
alinhamento e memórias. O caso de recusa usa uma variação explícita de perfil
neutro com um interesse de peso 2, que mantém hesitação e consome o d20 baixo.
As falas sociais especificam voz alta para alcançar o guarda distante pelo
caminho auditivo real. Não se exige redação literal do modelo. A posição do bug
original, guarda já em [9,16], continua sendo rejeitada pelos critérios.

Esta suíte antiga foi corrigida, mas não executada neste incremento. O pedido
original foi também incluído no corredor audível da [bateria nova de disposição](disposicao-live.md),
com perfis variados. A avaliação e as evidências dessa bateria têm escopo próprio.

Automação exige narração em on, mas não certifica toda a semântica de texto livre.
Revisão humana deve conferir: ordem audível à distância, oportunidade de responder,
resultado social fiel ao evento e ausência de aproximação, captura ou golpes
inventados. O campo `narrative_review` registra esse critério nos artefatos.

## Execução, orçamento e evidências

Leia a [política live](politica-live-tests.md). São **quatro casos, uma repetição
cada, 27 chamadas normais e teto total de 34 chamadas ao SDK**, incluindo até uma
correção por interpretação. O limite é de chamadas, não monetário. Nenhum retry
até passar é autorizado. Testes não concluídos, falhas de serviço, dados inesperados
e limites esgotados reprovam e conservam suas evidências.

Exige `OPENAI_API_KEY`. Usa o modelo padrão da aplicação ou `TRAMA_OPENAI_MODEL`;
qualquer alteração fica na configuração efetiva registrada. Criar ou coletar os
casos não autoriza custo. A execução paga da bateria requer autorização explícita:

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_parley.py -m live -v
```

Verificações sem rede ou custo:

```bash
poetry run pytest tests/live/test_parley.py --collect-only -q
poetry run pytest tests/integration/test_parley.py tests/integration/test_parley_live_scenarios.py
poetry run python tools/context_contracts.py --check
```

`logs/live/parley/<data-id>/<caso>/` recebe `trace.jsonl` e `result.json`, inclusive
em falha. O resultado registra configuração, situação, todas as mensagens e
etapas com contextos/respostas, relatórios, fotografias de estado, dados usados
e pendentes, orçamento e erros. O trace da aplicação preserva payloads efetivos,
correlação e tokens. `TRAMA_PARLEY_ARTIFACTS` escolhe outro diretório de saída.
Não registre segredos nem reescreva logs históricos como medições deste incremento.

A suíte foi criada e validada offline; isso não afirma aprovação por modelo real.
Uma execução paga futura deve receber seu próprio registro datado de evidências.

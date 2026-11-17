# Conclusão de turnos de NPCs

Tier 3 · [Qualidade](README.md) · [Fluxo do jogo](../aplicacao/fluxo-do-jogo.md)

## Objetivo e recorte

Regressão do turno que ficava pendente quando o guarda pedia um destino além dos
9 m disponíveis. A política geral de conclusão/recuperação está no fluxo do jogo.
Não altera percepção nem implementa Dash ou ações novas para NPCs.

`tests/live/test_npc_turn_completion.py` percorre `open_situation` e `game.runner`,
com a composição real, encerramento do turno do jogador, decisão do
NPC, execução, narração e pergunta off. Não replica o coordenador nem substitui
um plano real. Preparação determinística não testa interpretação dessa preparação.

## Situações e critérios independentes

O cenário genérico `npc_turn_corridor.json` contém um corredor iluminado, sem
portas, e um vigia hostil na coluna 22/linha 3. Usa o recorte de fichas de
Guerreiro já suportado pelo Trama. `response=observe` evita abordagem durante
um combate preparado; não há regra de conclusão específica do mapa.
As situações também abrem na janela com `--situation ID`.

| Situação | Preparação pública | Critérios |
| --- | --- | --- |
| `turno-npc-distante` | Jogador na coluna 3/linha 3; combate iniciado com jogador primeiro. | Vigia se aproxima até 9 m, sem ataque/dano, termina uma vez e devolve ao jogador na rodada 2. |
| `turno-npc-aproxima-e-ataca` | Jogador na coluna 15/linha 3; mesma iniciativa. | Vigia alcança uma casa adjacente em até 9 m, executa um ataque legal e termina uma vez. |

Iniciativa fixa: d20 20/19 para jogador com vantagem, d20 1 para vigia. Ataque
opcional usa d20 1; a espada grande com Graze causa 3 de dano, sem dados de dano.
Fichas, recursos, posição do jogador, passagens e inventário são conferidos.
Pergunta off não pode alterar estado nem disparar NPCs. Erros de serviço,
limite de chamadas, ação inválida e recuperação não contam como aprovação do
plano legal. Evidências preservam também essas falhas.

O modelo pode escolher um destino já dentro do alcance; por isso uma aprovação
live não prova que ele percorreu o ramo `movement_limited`. Regressões locais
forçam esse ramo com destino além do orçamento, inclusive ataque válido/inválido
posterior, movimentos repetidos, gasto anterior, oportunidade e sequência de NPCs.
Os critérios live são exercitados offline e precisam reprovar turno preso e
deslocamento excessivo. Nenhum teste exige uma redação literal do narrador.

## Execução autorizada e limites

Exige `OPENAI_API_KEY` e autorização explícita. A solicitação deste incremento
autoriza uma bateria apenas deste arquivo: uma tentativa por caso, 5 chamadas
normais por caso e teto de 6 no SDK com correção de interpretação, total máximo
de 12. O recorte começa no combate preparado, sem narração de abertura. Respeita
`TRAMA_OPENAI_MODEL` e a configuração padrão da aplicação.
Não executa outras suítes live nem repete até passar.
`TRAMA_NPC_TURN_MAX_CALLS` pode reduzir o teto por caso numa retomada limitada;
falhas anteriores permanecem nas evidências e no orçamento agregado.

```bash
poetry run pytest tests/live/test_npc_turn_completion.py --collect-only -q
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_npc_turn_completion.py -m live -v
```

Limite é de chamadas, não monetário. Coleta e testes locais não pagam chamadas.
Resultados, configuração, rolagens, contextos, respostas, planos, estado e erros
persistem em `logs/live/npc_turns/<execução>/<situação>/result.json` e
`trace.jsonl`; `TRAMA_NPC_TURN_ARTIFACTS` permite outro diretório. O texto salvo
exige revisão humana: aproximação compatível com distância, ataque só ao alcance
e resposta off reconhecendo que já é o turno do jogador, sem espera fictícia.

## Medição deste incremento

O [registro de 16/11/2026](../../evidencias/2026-11-16-conclusao-turnos-npc/relatorio.md)
preserva falhas de conexão, erro inicial no registrador, aprovação do caso
distante, falha tática no próximo e uma reavaliação deste após corrigir a
instrução antiga do Mundo. Não houve execução das demais suítes live nem
aprovação uniforme dos dois casos sob a mesma revisão das instruções.

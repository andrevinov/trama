# Conclusão de turnos de NPCs — 16/11/2026

[Evidências](../README.md) · [Escopo e critérios](../../sistema/qualidade/turnos-npc-live.md)

## Resultado observado

O caso distante devolveu o controle após 9 m, sem ataque ou dano. O caso próximo
inicialmente terminou o turno sem atacar, embora chegasse a 1,5 m do jogador.
Depois de corrigir uma instrução antiga do Mundo, esse caso passou com movimento
de 9 m, ataque, Graze de 3 de dano e iniciativa devolvida ao jogador na rodada 2.
As perguntas off reconhecem que o NPC já concluiu a vez e não alteram o estado.

São duas aprovações em revisões distintas das instruções, não uma bateria 2/2
reexecutada integralmente na revisão final. Não foram executadas outras suítes
live. Uma amostra real não garante futuras decisões do modelo.

## Configuração, autorização e preparação

O usuário solicitou implementação, live tests e execução focada neste incremento.
Composição padrão da aplicação: `gpt-5.6-terra`, SDK 3.49.0, timeout 30 s,
zero retries de transporte, contexto mínimo, até uma correção de interpretação,
esquema com operação primeiro e esforço `low` nas três fases. Cada `result.json`
preserva a configuração efetiva completa, sem credenciais.

`open_situation` prepara `npc_turn_corridor.json` por `start_combat` real, com
rolagens fixas. A interação avaliada passa pelo runner compartilhado. Os testes
não substituem planos do modelo nem inventam regras para o mapa. A preparação
determinística não avalia a interpretação das ações usadas para montá-la.

Datas nos ids são UTC de 17/11; a execução ocorreu em 16/11 no fuso UTC−3.
Os registros originais continuam nos caminhos literais abaixo e no
[manifesto](manifesto.json), com tamanho e SHA-256.

## Tentativas preservadas

| Execução em `logs/live/npc_turns/` | Casos e resultado | Tentativas SDK / respostas |
| --- | --- | ---: |
| `20261117T024559-b4c56700` | Dois erros de conexão dentro da sandbox, na abertura; nenhuma resposta de modelo. | 2 / 0 |
| `20261117T024624-cf9a35b8` | Duas aberturas respondidas; registrador falhou com `TypeError` ao aplicar `asdict` a `AIContext`. Sem interação de turno avaliada. | 2 / 2 |
| `20261117T024923-88ba1fd6` | Distante aprovado (5 chamadas); próximo reprovado por omitir ataque ao alcançar (4 chamadas). Turnos concluídos nos dois casos. | 9 / 9 |
| `20261117T025145-d11e40c6` | Somente próximo, após correção da instrução: aprovado, incluindo pergunta off. Distante não repetido. | 5 / 5 |

O registrador foi corrigido e sua serialização verificada offline. O recorte
passou a começar na interação do combate preparado, dispensando repetir uma
abertura sem relação com o comportamento avaliado. O teto foi reduzido a cinco
chamadas por caso na retomada: as duas primeiras etapas e a bateria cabiam nas
14 tentativas inicialmente anunciadas, com 13 efetivamente usadas.

A reavaliação posterior, anunciada após uma mudança concreta nas instruções,
teve teto adicional de cinco chamadas. Total: **18 tentativas de SDK, 16 respostas**,
dentro do teto agregado de 19 tentativas. Não houve repetição de uma decisão inalterada
até obter aprovação. O total de uso reportado é 102.058 tokens de entrada e
1.388 de saída, 103.446 no total; não foi calculado valor monetário.

## Falha que orientou o ajuste

Na primeira avaliação próxima, o plano continha somente `move`, chegando à
coluna 16/linha 3, ao lado do jogador na coluna 15/linha 3. A justificativa
afirmava incorretamente que ainda não havia alcance. Os critérios reprovaram
a ausência do ataque e dos 3 de dano esperados; o executor não ficou pendente.

As instruções anteriores ainda diziam para interromper ações seguintes tanto
por porta fechada quanto por saldo insuficiente. A revisão distingue o limite
normal de movimento de obstáculos e esclarece que o ataque usa a posição após
a aproximação e sua própria ação. Os hashes dos textos efetivamente enviados
por fase, antes/depois, ficam no manifesto. A reavaliação só aconteceu após esse
ajuste; a falha original permanece registrada.

## Evidência local e limites

- Suíte local completa: **956 testes aprovados**, em 88,35 s. A execução anterior
  com duas expectativas antigas de turno pendente também foi preservada.
- Após o ajuste da instrução, **103 testes focados aprovados**, incluindo os
  contratos e os critérios da bateria. Contratos, Poetry e diff conferidos.
- Regressões locais forçam destino além de 9 m, ataque legal e ilegal posterior,
  múltiplos movimentos, orçamento parcialmente gasto, oportunidade aceita/recusada
  e continuação para outro NPC, sem repetir decisões.
- Nos live aprovados, o modelo escolheu destinos já dentro dos 9 m; o ramo de
  corte `movement_limited` é demonstrado pelas regressões locais, sem atribuir
  essa cobertura específica às chamadas reais.
- Revisão humana: aproximação, dano, distância e devolução do controle coerentes.
  A resposta off final usa “2º turno” para a rodada 2, uma imprecisão de termo
  preservada; o estado estruturado informa `round=2` e jogador ativo.
- UI gráfica, indisponibilidade prolongada de provedor e toda a qualidade tática
  de NPCs não são garantidos por estes dois casos. A recuperação encerra um
  plano inválido preservando sua falha; não o converte em decisão válida da IA.

## Conferência sem rede

```bash
poetry run python tools/check_evidence.py --manifest docs/evidencias/2026-11-16-conclusao-turnos-npc/manifesto.json --require-local
```

Logs brutos são locais e ignorados pelo Git. O inventário histórico anterior
permanece intacto; este é um registro novo da observação.

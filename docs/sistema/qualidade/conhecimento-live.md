# Conhecimento dos NPCs — avaliação live

Tier 3 · [Qualidade](README.md) · [Memórias e contratos](../aplicacao/conhecimento-dos-npcs.md)

## Escopo

`tests/live/test_npc_knowledge_live.py` usa o cenário genérico
`knowledge_rooms.json`, situações públicas e `open_situation`/`game.runner`.
Avalia a interação completa a partir do arranjo preparado, com composição,
contextos, adaptadores, validação, aquisição, Mundo e narração reais. Não há
abertura paga adicional, coordenador alternativo ou resposta de IA substituta.

Um arquivista e seu aprendiz estão na sala oeste; a chave fica oculta atrás de
uma porta fechada na sala leste. Os estados iniciais vêm do catálogo da aplicação,
sem mutações privadas de estado. A posição atual do objeto pode divergir da
lembrança anterior à conversa; isso é preparação declarada, não ação live de
movimentação de objetos estáticos, que não está implementada.

## Casos e critérios anteriores às chamadas

| Situação | Interações e critério | Normal / teto SDK |
| --- | --- | ---: |
| `memoria-inicial` | Perguntar onde o arquivista viu a chave. Resposta cita memória própria; jogador e aprendiz recebem relato com fonte e referência original. | 3 / 4 |
| `memoria-desconhecida` | Mesmo pedido sem memória inicial. NPC reconhece não saber; não concede a informação ao jogador nem aprende pela verdade oculta. | 3 / 4 |
| `memoria-desatualizada` | Lembrança na coluna 13, chave atualmente na coluna 18 sem visão do NPC. Compartilha a ocasião antiga sem atualizar pela posição real. | 3 / 4 |
| `memoria-relato` | Perguntar, comunicar um relato de nova localização e perguntar a informação mais recente com fonte. NPC retém a observação antiga e compartilha o relato atribuído ao jogador; objeto não se move. | 9 / 12 |

Não pode haver deslocamento, iniciativa, dano, alteração de porta, inventário ou
recurso. A avaliação verifica o estado completo de memórias, fontes, afirmações
e referências, não apenas JSON válido. Critérios de desconhecimento também
inspecionam a fala; a revisão humana confere sentido, ocasião e atribuição das
respostas salvas. Uma referência não prova a fidelidade de toda a prosa.

Os critérios e a serialização das evidências são exercitados offline com
adaptadores locais pelo runner real, incluindo controles que reprovam mudança
indevida da localização. Esses testes não substituem a medição real.

## Autorização, comando e evidências

O usuário autorizou executar somente os testes novos deste incremento. Plano:
uma tentativa por caso, 18 chamadas normais, teto total de 24 no SDK incluindo
correções, sem repetir até passar. Não executar outras suítes live nesta bateria.
`TRAMA_KNOWLEDGE_CALLS_RESERVED` desconta tentativas já consumidas por caso numa
retomada por falha de conexão; essas tentativas permanecem no orçamento agregado
e nas evidências, sem ampliar o teto.
São limites de chamadas, não monetários. Exige `OPENAI_API_KEY` e usa a configuração
padrão da aplicação, respeitando `TRAMA_OPENAI_MODEL`.

```bash
poetry run pytest tests/live/test_npc_knowledge_live.py --collect-only -q
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_npc_knowledge_live.py -m live -v
```

Os artefatos persistem, inclusive em falha, em
`logs/live/knowledge/<execução>/<situação>/result.json` e `trace.jsonl`.
`TRAMA_KNOWLEDGE_ARTIFACTS` permite outra raiz. Preservam configuração, contexto
efetivo, mensagens, respostas, planos, estado antes/depois, memórias, fontes,
relatórios, tokens, rolagens e erros, sem credenciais.

Erros de serviço, orçamento, interpretação, origem ou ausência de resposta
reprovam e permanecem nas evidências. Os testes não garantem toda conversa futura,
mentiras semanticamente corretas ou a interpretação de qualquer relato livre.

## Medição deste incremento

O [registro de 17/11/2026](../../evidencias/2026-11-17-conhecimento-npcs/relatorio.md)
preserva os quatro erros de conexão iniciais e a bateria real com quatro
aprovações. Também identifica os refinamentos posteriores, verificados somente
pelos testes locais novos, sem nova medição paga. A revisão medida tem snapshot
próprio; não se atribui retroativamente sua aprovação a outro código/contexto.

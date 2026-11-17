# Live tests de múltiplos interesses por memória

Tier 3 · [Qualidade](README.md) · [Disposição social](../aplicacao/disposicao-social.md)

## Escopo e critérios prévios

`tests/live/test_memory_evidence_links_live.py` usa três situações da dungeon
oficial por `open_situation` e `game.runner.submit`. Interpretador, Mundo, regras,
narração e configuração são os mesmos do simulador. A preparação pública
`guard_challenge_cell_2` chama o guarda, desperta o prisioneiro e produz a
abordagem real: jogador em [8,20], guarda em [10,6], porta aberta e distância
acústica de 22,5 m. Não é uma partida inteira nem interpretação live da preparação.

| Situação | Critério independente |
| --- | --- |
| `memoria-vinculos-original` | Frase real que causou a rejeição: nobreza e recompensa por ajuda para sair. A resposta deve resolver o pedido de libertação sem erro de transporte e sem executar uma fuga só pela fala. |
| `memoria-vinculos-consequencias` | Uma alegação de nobreza com implicações para segurança e emprego deve ser considerada como relato, com pontuação limitada por fato. Pedido restrito à escuta. |
| `memoria-vinculos-repeticao` | Alegação de nobreza e promessa por escuta, seguidas da mesma mensagem: conservar decisão e não rolar outro dado. |

As fixtures contêm mensagens e orçamento; perfis, memórias e preparação pertencem
ao catálogo da aplicação. Não se força uma saída literal nem disposição específica:
o critério exige resolução compatível com dados/limiares, evidência do jogador
não confirmada, uma contribuição por Claim, preservação de todos os vínculos
propostos e ausência de movimento, dano, portas/itens concedidos ou combate.

A IA pode fundamentar um fato em um interesse ou em vários. Não forçamos uma
duplicação artificial na resposta live. A regressão offline congela a resposta
real rejeitada e comprova especificamente dois vínculos positivos para a mesma
Claim; a medição registra quantos vínculos foram efetivamente propostos live.
Revisão humana da prosa confere alegação incerta, promessa sem pagamento e
ausência de liberdade física inventada. Narração não vazia não prova coerência.

## Orçamento e preservação

Autorização: o usuário pediu a correção e três live tests cobrindo o problema.
**Uma tentativa por caso, quatro mensagens, 12 chamadas normais e teto total
de 16 chamadas ao SDK**, incluindo até uma correção de interpretação por mensagem.
Sem chamada paga de abertura ou repetição até passar. Não executa outras suítes.
Usa modelo padrão e configuração efetiva da aplicação, sem prompts alternativos.

Na primeira bateria houve 12 chamadas: consequências e repetição passaram;
o original foi processado sem erro de transporte, mas reprovou por classificar
libertação como acesso e não citar a nova alegação de nobreza como relato.
Uma revisão do contrato distingue essas categorias e exige preservar a fonte
da alegação nova. Apenas o original recebe uma execução corretiva, com teto de
quatro chamadas; as duas baterias juntas permanecem limitadas a **16**. Os
critérios e a frase original não foram relaxados, e a falha fica preservada.

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_memory_evidence_links_live.py -m live -v
```

Exige `OPENAI_API_KEY`. `logs/live/memory-links/<data-id>/<caso>/` conserva
`result.json` e `trace.jsonl`, inclusive falhas: entradas, fontes, configuração,
contextos, planos, relatórios, posições, dados, tokens e erros. A variável
`TRAMA_MEMORY_LINKS_ARTIFACTS` permite trocar a raiz. A evidência desta medição
receberá relatório e hashes próprios; inventários anteriores não são alterados.

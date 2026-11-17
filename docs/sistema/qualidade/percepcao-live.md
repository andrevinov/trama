# Live tests de percepção por NPC

Tier 3 · [Qualidade](README.md) · [Visão geral](../../../README.md)

## Escopo e composição

`tests/live/test_npc_perception.py` avalia 13 condições claras pelo fluxo completo
da interação, desde situações preparadas. Carrega `perception_rooms.json` por
`open_situation`, usa a composição padrão e `game.runner`: abertura, interpretação,
Mundo, regras e narração. Nenhuma regra, contexto, schema ou resposta de modelo
é duplicada no teste. A preparação de ocultação de dois casos é determinística,
por Hide real; não é uma interpretação live da preparação.

As situações e seus sentidos, posições, iluminação e dados ficam no catálogo da
aplicação. A janela pode abri-las por `--situation ID`, com o mesmo reinício.
`tests/fixtures/perception/cases.json` contém mensagens, critérios e limites.
A [referência de percepção](../mundo/visao-e-percepcao.md) explicita regras e
simplificações de alcance, portas, sono e cobertura.

## Critérios definidos antes das chamadas

| Situação | Resultado exigido |
| --- | --- |
| `percepcao-visao-alcance` | Vigia com alcance visual de 3 m; movimento interrompido em [10,3], NPC em [12,3], conversa pendente sem iniciativa. |
| `percepcao-porta-fechada` | Apenas olhar não revela o jogador ao vigia através da porta. |
| `percepcao-escuridao` | Visão normal não detecta o jogador na casa escura. |
| `percepcao-visao-no-escuro` | Visão no escuro de 6 m detecta o alvo a 4,5 m. |
| `percepcao-som-distante` | Voz normal não alcança um vigia configurado com audição normal de 6 m, considerando percurso e porta. |
| `percepcao-grito-distante` | Grito alcança o mesmo vigia; `heard`, sem posição visual revelada. |
| `percepcao-furtividade-passiva` | Hide real resulta em 21; sussurro não é localizado por percepção passiva 13. |
| `percepcao-npc-perspicaz` | O mesmo total 21 é superado por passiva 22; fonte localizada por som, sem visão através da porta. |
| `percepcao-busca-sucesso` | Search deliberado rola 23 contra CD real 21 e localiza por som. |
| `percepcao-busca-falha` | Search rola 4 contra CD 21; nova espera sem mudança não concede outra busca/rolagem. |
| `percepcao-despertar` | Voz normal acorda NPC a 7,5 m, sem ficha de Guerreiro ou teste de Percepção inconsciente. |
| `percepcao-sono-preservado` | Sussurro à mesma distância não o acorda. |
| `percepcao-furtividade-falha` | Hide resulta em 2; um sussurro alcançável não recebe proteção de uma ocultação inexistente. |

Todos os casos proíbem movimento de NPC, dano, gasto de recursos de classe,
iniciativa indevida, alteração de portas não pedida e turnos artificiais. Os
casos sem caminhada preservam a posição do jogador. Dados declarados precisam
ser realmente consumidos; não há testes de alcance sorteados para acomodar saídas.
Os critérios não chamam novamente os algoritmos de visão, audição ou rolagem
para produzir o esperado. A regressão local demonstra que eles reprovam uma
observação fabricada através da parede/escuridão ou apesar da furtividade.

Asserções exigem narração em on, mas não certificam toda a semântica livre. A
revisão humana dos artefatos deve verificar ouvido/localizado/visto, preservar
conhecimento oculto dos NPCs, distinguir passiva de busca deliberada e conferir
sono, luz, dados e ausência de aproximação/captura/golpes inventados. As capacidades
são reais; não são simuladas no contexto. Modelos podem variar e reprovar.

## Autorização, orçamento e artefatos

Leia a [política obrigatória](politica-live-tests.md). Uma bateria prevê **uma
repetição de cada um dos 13 casos: 64 chamadas normais e teto de 81 chamadas ao
SDK**, contando até uma correção por interpretação. O teto é de chamadas, não
monetário; não há retry até passar. Criar/coletar a suíte não autoriza custo.
Exige `OPENAI_API_KEY` e autorização explícita de execução:

```bash
RUN_OPENAI_LIVE_TESTS=1 poetry run pytest tests/live/test_npc_perception.py -m live -v
```

Usa a configuração padrão da aplicação e respeita `TRAMA_OPENAI_MODEL`. Casos
incompletos, erros, decisões fora do orçamento e dados inesperados reprovam,
preservando os resultados desfavoráveis. Não são substituídos por planos conhecidos.

`logs/live/perception/<data-id>/<caso>/` guarda `trace.jsonl` e `result.json`,
inclusive em falha: configuração efetiva, situação, mensagens, contextos e
respostas reais, relatórios, estados, dados usados/pendentes, orçamento e erros.
O trace da aplicação preserva payloads, tokens e correlação. A saída pode ser
alterada com `TRAMA_PERCEPTION_ARTIFACTS`. Não registre credenciais.

Verificações sem rede/custo:

```bash
poetry run pytest tests/live/test_npc_perception.py --collect-only -q
poetry run pytest tests/unit/test_perception_rules.py tests/integration/test_perception.py tests/integration/test_perception_live_scenarios.py
poetry run python tools/context_contracts.py --check
```

A preparação e os critérios foram validados offline pelo runner compartilhado.
Isso não constitui aprovação de um modelo real. Uma execução paga futura deve
ter suas próprias evidências datadas, sem reescrever inventários históricos.

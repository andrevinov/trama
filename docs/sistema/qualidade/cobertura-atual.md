# Cobertura atual e evidências

Tier 3 · [Qualidade](README.md) · [Visão geral](../../../README.md)

## O que esta matriz representa

A classificação abaixo descreve os caminhos implementados das suítes live,
separando escopo de teste de resultado observado. A composição de serviços e o
carregador são compartilhados; isso não transforma uma sequência parcial em
fluxo completo. Os dados e as escolhas de cada fixture continuam explícitos.

| Suíte em `tests/live` | Casos | Escopo efetivo | Limite |
| --- | ---: | --- | --- |
| `test_npc_agency_live.py` | 3 | Fluxo oficial: agência após conversas paralelas, observações próprias e perguntas off sem avanços. | [Três casos aprovados](../../evidencias/2026-11-17-agencia-npcs/relatorio.md); consulta off reavaliada após refinamento de linguagem, 33 chamadas no total. [Casos e limites](agencia-live.md). |
| `test_contextual_difficulty_live.py` | 10 | Fluxo oficial: três conversas com referências de memória e sete tarefas contextuais; CDs fixas ficam no código. | [Dez casos aprovados nas execuções medidas](../../evidencias/2026-11-17-dificuldade-contextual/relatorio.md), três falhas iniciais preservadas; [critérios e limites](dificuldade-live.md). |
| `test_memory_evidence_links_live.py` | 3 | Fluxo compartilhado na dungeon: frase real, vários interesses por alegação e repetição sem outra rolagem. | Três casos com execuções aprovadas; original reavaliado após ajuste de categoria/fonte. [Falha preservada e limites](../../evidencias/2026-11-17-vinculos-memoria/relatorio.md). |
| `test_social_disposition_live.py` | 7 | Fluxo compartilhado desde abordagem audível: perfis, alinhamentos, recompensas e informação relevante. | Corrupto completo aprovado após correção; cinco casos simples satisfazem os critérios corrigidos em revisão offline da medição; memória incompleta. [Falhas e limites](../../evidencias/2026-11-17-disposicao-social/relatorio.md). |
| `test_npc_knowledge_live.py` | 4 | Fluxo compartilhado em salas genéricas: memórias iniciais, ignorância, lembrança desatualizada e relato retomado com fonte. | [Quatro aprovações na revisão medida](../../evidencias/2026-11-17-conhecimento-npcs/relatorio.md); refinamentos finais locais não reavaliados com IA. Prosa exige revisão humana. |
| `test_npc_turn_completion.py` | 2 | Fluxo compartilhado em corredor genérico: passar turno, aproximação limitada, ataque ao alcançar e pergunta off. | Distante aprovado antes do último ajuste de instruções; próximo aprovado após correção, com falha anterior preservada. [Medição e limites](../../evidencias/2026-11-16-conclusao-turnos-npc/relatorio.md). |
| `test_npc_perception.py` | 13 | Fluxo compartilhado em salas genéricas: sentidos, ruídos, Hide, passiva, Search, sono e narração. | Preparação/critérios validados offline; sem execução paga registrada. Revisão semântica do texto é humana. |
| `test_parley.py` | 4 | Fluxo compartilhado desde o corredor: abertura, detecção, resposta social/ataque, NPCs e narração. | Validação offline; sem medição paga deste incremento. Julgamento e texto reais ainda variam. |
| `test_contextual_movement.py` | 8 | Fluxo compartilhado desde situação preparada: abertura, mensagem, Mundo, NPCs e narração. | Não é partida inteira desde a cela inicial; escolhas não previstas tornam execução inconclusiva. |
| `test_dungeon_interactions.py` | 3 | Adaptadores e motor em fluxo parcial. | Mantém sequência manual, sem toda coordenação de NPCs e retomadas. |
| `test_openai_movement.py` | 7 | Adaptadores e primitivas. | Cinco casos executam somente a primeira etapa; sem decisão do Mundo. |
| `test_semantic_interpretation.py` | 11 | Contrato do interpretador. | Avalia plano sem executá-lo; zero correções é variante explícita. |
| `test_interpretation_experiment.py` | 6 | Experimento de contexto/primeira resposta. | Não executa efeitos. |
| `test_schema_order.py` | 3 | Experimento de ordem de propriedades. | Variante antiga é controle; não verifica o fluxo do jogo. |

Os oito casos contextuais usam o catálogo e `open_situation`, também acessíveis
na janela com `--situation ID`. Somente mensagens, escolhas, orçamento e critérios
independentes continuam nas fixtures dos testes. A preparação determinística
compartilhada não é uma interpretação live das ações usadas para montar o arranjo.

As suítes de comparação de contexto e ordem de esquema importam o módulo
`trama.analysis.interpretation` e leem as fixtures de interpretação, sem executar
scripts de POCs. Seus artefatos declaram `scope=interpreter_contract`. A migração
de dependências preserva o escopo parcial, as variantes e os critérios anteriores.

A coleta offline pode conferir quantidades sem consultar serviços:

```bash
poetry run pytest tests/live --collect-only -q
```

A execução segue a [política obrigatória](politica-live-tests.md) e as
[instruções locais](../../../tests/live/README.md). Contagens de chamadas dependem da
configuração e dos caminhos alcançados; limites da suíte contextual estão em
[movimento contextual live](movimento-contextual-live.md).

## Evidência real preservada

O [experimento de 16/11/2026](../../evidencias/2026-11-16-movimento-contextual/relatorio.md)
executou os oito casos contextuais uma vez cada, com 33 chamadas ao modelo
padrão da aplicação naquela data. Os critérios mecânicos passaram; a revisão
narrativa registrou ressalvas. As outras suítes não foram executadas naquela
bateria e não recebem aprovação por ela.

Essa evidência é datada, não uma medição contínua ou garantia de repetibilidade.
O relatório e o manifesto conservam configuração e proveniência; os logs brutos
permanecem locais e não acompanham um clone do repositório.

O [inventário de preservação](../../evidencias/2026-11-16-preservacao-das-analises/relatorio.md)
relaciona os arquivos e seus hashes, inclusive o lote exploratório anterior e a
comparação de esquema. A conferência offline preserva erros e ressalvas; não é
nova avaliação do modelo ou certificação do código atual.

## Cobertura local e lacunas

Os [testes locais](testes-locais.md) verificam regras, carregadores, contratos,
UI, fluxo, reações e falhas sem pagar chamadas. Os
[controles de regressão](deteccao-de-regressoes.md) demonstram critérios que
reprovam ausência de aproximação, ataque após Surto, conclusão de NPC,
oportunidade e deslocamento narrado sem efeito.

A [conversa antes do combate](conversa-live.md) tem quatro situações jogáveis e
critérios independentes validados offline, incluindo rejeição da aproximação
indevida. A regra geral também é testada sem dungeon; a criação dos casos não
constitui evidência de aprovação por modelo real.

Surto seguido de ataque é prova local, sem novo caso pago na suíte contextual.
A revisão genérica de toda verdade narrativa ainda não é automatizada. Há
cenários locais de falha, reinício e pausa que não têm avaliação live dedicada.
As demais suítes live conservam os limites parciais declarados acima.

## Manutenção

Atualize esta matriz quando mudar o trecho efetivamente percorrido por uma
suíte. Acrescente novas medições como evidências datadas, preservando resultados
desfavoráveis. A
[auditoria histórica](../../roadmaps/implementados/2026-11-16-live-tests-compartilhados/auditoria-historica.md)
registra a migração; não é a fonte principal da cobertura corrente.

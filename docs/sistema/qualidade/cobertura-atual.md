# Cobertura atual e evidências

Tier 3 · [Qualidade](README.md) · [Visão geral](../../../README.md)

## O que esta matriz representa

A classificação abaixo descreve os caminhos implementados das suítes live,
separando escopo de teste de resultado observado. A composição de serviços e o
carregador são compartilhados; isso não transforma uma sequência parcial em
fluxo completo. Os dados e as escolhas de cada fixture continuam explícitos.

| Suíte em `tests/live` | Casos | Escopo efetivo | Limite |
| --- | ---: | --- | --- |
| `test_conversation_focus_live.py::test_live_conversation_focus` | 3 | Fluxo oficial do conselho: abertura, saudação/gesto ou proposta, resposta executada de Voss e consulta off. | [Três casos com execução aprovada](../../evidencias/2026-11-19-foco-conversa/relatorio.md); falha anterior de estado ativo preservada e correção reavaliada em tentativa adicional autorizada. [Casos e orçamento](foco-conversa-live.md). |
| `test_conversation_focus_live.py::test_live_conversation_punctuation` | 3 | Mesmo fluxo com duas falas citadas, intervenção narrativa, aspas tipográficas, condição e negação de prazo. | Reprodução da autorização real e controles locais aprovados; sem nova medição paga. [Casos e orçamento](pontuacao-conversa-live.md). |
| `test_gestural_communication_live.py` | 4 | Fluxo oficial: sinal bloqueado, aceno recebido e piscadelas próxima/distante com passiva contextual. | Preparações e oráculos offline; sem medição paga. [Casos e limites](gestos-live.md). |
| `test_passage_inspection_live.py` | 4 | Fluxo oficial: conferência silenciosa, porta trancada, observação distante e esclarecimento sem ação. | [Quatro casos aprovados](../../evidencias/2026-11-17-inspecao-passagens/relatorio.md), 11 chamadas; refinamentos finais verificados localmente. [Casos e limites](inspecao-live.md). |
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

O estado próprio da conversa tem verificação offline pelo fluxo oficial com
transporte fixo: pendências, propostas, versões, privacidade, audição, ciclo de
vida e reinício. A auditoria de contextos usa contribuições reais pelo motor.
Essas verificações não medem interpretação ou negociação de um modelo real;
não há aprovação live atribuída ao passo 2 por sua implementação.

O passo 3 tem conferência offline pelo mesmo fluxo e transporte fixo para notas
por opção/termo, revisão, repetição, limites, referências e privacidade. A
auditoria inclui opiniões calculadas para proposta, alternativa e expectativa
sem acordo. Isso verifica os impactos fornecidos, sem medir a qualidade do
julgamento semântico de um modelo real ou ampliar o escopo das medições live
acima. Veja [opiniões por opção](../aplicacao/opinioes-por-opcao.md).

O passo 4 tem conferência pelo runner e adaptadores com transporte fixo para
conversa comum, notas antes da escolha, pendência ignorada, contraproposta
estruturada, recusa sem violência, escuta limitada, off, fechamento, privacidade,
duplicatas e falhas. Controles incluem avaliação desatualizada durante uma
resposta pendente e retirada de outro participante da fila após fechamento
percebido. Não há nova medição live ou aprovação da semântica de um modelo real.
Veja [intenções dos NPCs](../aplicacao/intencoes-dos-npcs.md).

O passo 5 tem conferência offline de relações iniciais direcionais: confiança
e afeto independentes, extremos e compensação, base neutra preservada, ausência
de reciprocidade, referências, fontes sem pontuação duplicada, consequências
independentes, novas conversas, off e reset. O fluxo oficial com transporte fixo
compara inimigo confiável e amigo pouco confiável e permite recusa franca mesmo
com nota favorável. A auditoria de contexto executa o caso de memória resumida
na relação. Não há medição nova de um modelo real.

O passo 6 tem conferência offline pelo runner oficial para promessa, aceitação,
ação de porta observada após o compromisso, atualização única com antes/depois,
arquivamento e retomada em outra conversa, privacidade, off e reinício. Controles
fixos também verificam dez cumprimentos sem pontos e evidência não percebida.
Regressões locais preservam suspeita, confirmação e correção com história,
recomposição nos limites, rejeição de prova de outro dono ou relato como fato
confirmado e lote inválido sem alteração parcial. As amostras dos contratos
cobrem os novos contextos. Isso não mede a pertinência semântica do diretor real;
a política e o recorte estão em [evolução das relações](../aplicacao/evolucao-das-relacoes.md).

O passo 7 acrescenta regressões pelo runner para revelação pertinente feita por
outro NPC, informação irrelevante, fala não ouvida, revisão de quem já agiu,
recontagem sem nova rodada, suspensão/retomada com pergunta preservada e reação
sem mensagem do jogador. O deslocamento de investigação é executado e conferido.
Controles parciais com ataque real distinguem ferido visto de agressor identificado;
ruído percebido não recebe autoria oculta. Também se verifica interrupção por
combate sem fala fabricada, iniciativa/turno, off, reinício e estímulos da preparação
sem reapresentação. Contratos incluem a fase privada de revisão e sua posse de
evidências. A adequação da prioridade escolhida pelo modelo real não foi medida;
os limites estão em [acontecimentos e prioridades](../aplicacao/acontecimentos-e-prioridades.md).

O passo 8 tem situações jogáveis de amiga e garoto pelo catálogo comum.
Regressões pela composição/runner com escolhas fixas conferem escuta consecutiva,
acolhimento seguido de espera, ausência de renovação por silêncio/off ou pergunta
ignorada, conselho com abertura, mudança de foco/objetivo, fechamento e nova
conversa. Conferem também orientação oferecida após uma necessidade declarada,
despedida com deslocamento real e rejeição de destino inválido antes da fala.
Níveis não crescem por agradecimento; a moeda é memória inicial, sem transferência
de saldo. A CLI e o reinício usam os mesmos dados e preparação. As amostras dos
contratos alcançam os novos contextos; não houve nova medição semântica com IA
real. Recortes e critérios estão em [conversas casuais](../simulador/conversas-casuais.md).

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

## Vínculos qualitativos — passo 9

`tests/integration/test_relationship_bonds.py` usa situações oficiais e runner
com decisões fixas para amizade sem atração, afeto com confiança reduzida, recusa
escolhida pelo jogador, manutenção de sentimento não correspondido, privacidade,
off, reinício e recusa mesmo com opção favorável. Controles parciais verificam
formação, manutenção/ruptura, sequência de evidências novas, lotes inválidos,
fontes próprias, cuidado observado nas duas direções, idade adulta explícita,
limite não ouvido, declaração literal e repetição sem aquisição artificial.

A CLI compartilha a preparação e as quatro variações do catálogo. As amostras
dos contratos observam vínculos, história e declarações realmente executadas.
Classificações de cuidado e escolhas de resposta são fixas nos testes: não
comprovam julgamento semântico, reciprocidade ou qualidade de um modelo real.
Não houve nova medição paga. Veja [política](../aplicacao/vinculos-afetivos.md)
e [avaliação manual](../simulador/vinculos-afetivos.md).

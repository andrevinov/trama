# Aplicação e coordenação da partida

Tier 2 · [Visão geral do Trama](../../../README.md) ·
[Regras](../regras/README.md) · [IA](../ia/README.md) ·
[Interfaces](../interfaces/README.md)

A aplicação conecta as intenções do jogador, as respostas do Mundo e as regras
ao estado da partida. Ela determina a ordem do processamento, mantém a conversa
e publica os resultados que serão narrados e apresentados.

## Responsabilidade e fronteiras

O coordenador compartilhado conduz abertura, mensagens, turnos de NPCs,
oportunidades, narração e reinício. Ele solicita serviços por contratos de
aplicação; os adaptadores concretos são ligados pela composição da partida.

A janela e a execução sem janela agendam os pedidos escolhidos pelo mesmo
coordenador. O trabalho externo recebe uma fotografia do contexto; a aplicação
valida e aplica o resultado na thread dona do fluxo. Identificadores permitem
recusar entregas antigas ou duplicadas.

## Partes desta área

| Parte | Responsabilidade | Código de referência |
| --- | --- | --- |
| Fluxo | Escolher a próxima etapa e controlar conclusão, falha ou espera por entrada. | [game_flow.py](../../../src/trama/application/game_flow.py) |
| Sessão e encontro | Manter estado, participantes e recursos; executar operações determinísticas. | [session.py](../../../src/trama/application/session.py), [encounter.py](../../../src/trama/application/encounter.py) |
| Conversa e modos | Separar canais, manter histórico, executar planos ordenados e registrar seus resultados. | [conversation.py](../../../src/trama/application/conversation.py), [dialogue.py](../../../src/trama/application/dialogue.py), [modes.py](../../../src/trama/application/modes.py) |
| Estado da conversa | Preservar foco, pendências e versões de propostas segundo as comunicações percebidas. | [Estado e contratos](estado-da-conversa.md), [conversation_state.py](../../../src/trama/conversation_state.py) |
| Planos e validação | Representar intenções e conferir estrutura, referências e origens declaradas. | [intents.py](../../../src/trama/application/intents.py), [authorization.py](../../../src/trama/application/authorization.py) |
| Preparação espacial | Consultar requisitos de uma ação e planejar a aproximação necessária. | [preparation.py](../../../src/trama/application/preparation.py), [routing.py](../../../src/trama/application/routing.py) |
| Deslocamento e reações | Executar percursos com verificações por passo, oportunidades e retomadas. | [travel.py](../../../src/trama/application/travel.py) |
| Percepção por NPC | Avaliar sentidos, ruídos, ocultação, sono e busca; publicar acontecimentos antes das respostas. | [perception.py](../../../src/trama/application/perception.py), [contratos de sentidos](../../../src/trama/perception.py) |
| Memórias dos personagens | Registrar crenças com origem, adquirir por sentidos/fala e selecionar contexto relevante. | [Conhecimento dos NPCs](conhecimento-dos-npcs.md), [knowledge.py](../../../src/trama/knowledge.py) |
| Disposição social | Avaliar alinhamento, persona e memórias por pedido; resolver Influence e limitar a concessão. | [Disposição social](disposicao-social.md), [social.py](../../../src/trama/social.py) |
| Relações iniciais | Manter confiança e afeto direcionais por sessão e pontuar sua pertinência sem duplicar memória. | [Relações iniciais](relacoes-iniciais.md), [relationships.py](../../../src/trama/relationships.py) |
| Vínculos qualitativos | Validar amizade, atração, paixão e amor com fontes próprias e limites declarados, sem reciprocidade imposta. | [Vínculos afetivos](vinculos-afetivos.md), [bonds.py](../../../src/trama/application/bonds.py) |
| Opiniões privadas | Avaliar propostas e alternativas por termo, preservar motivos e reutilizar bases equivalentes sem dado. | [Opiniões por opção](opinioes-por-opcao.md), [opinions.py](../../../src/trama/opinions.py) |
| Dificuldade contextual | Separar CDs fixas de julgamento de tarefas incertas, validar fatos e resolver dados. | [Avaliação de dificuldade](avaliacao-de-dificuldade.md), [difficulty.py](../../../src/trama/difficulty.py) |
| Intenções em exploração | Decidir após os cálculos em conversas comuns, com objetivos, percepção e espera limitada. | [Intenções dos NPCs](intencoes-dos-npcs.md), [agency.py](../../../src/trama/application/agency.py) |
| Execução do Mundo | Validar e aplicar propostas de respostas e ações de NPCs. | [world.py](../../../src/trama/application/world.py), [world_resolution.py](../../../src/trama/application/world_resolution.py) |
| Contextos e projeções | Preparar informação para IA, mapa e fichas, incluindo disponibilidade de ações. | [context.py](../../../src/trama/application/context.py), [context_contracts.py](../../../src/trama/application/context_contracts.py), [sheets.py](../../../src/trama/application/sheets.py), [sheet_options.py](../../../src/trama/application/sheet_options.py) |
| Impedimentos | Registrar causa, progresso e partes que não foram executadas. | [failures.py](../../../src/trama/application/failures.py) |
| Composição | Reunir cenário, serviços e fluxo numa partida utilizável. | [bootstrap.py](../../../src/trama/bootstrap.py) |

## Como as partes trabalham juntas

Uma ação proposta passa pela validação antes da consulta ao Mundo. Na execução,
cada etapa verifica suas condições atuais; uma etapa anterior pode habilitar a
seguinte. Quando necessário e autorizado, a preparação espacial usa os mesmos
percursos e reações do movimento explícito. A ação é revalidada após a caminhada.

Um impedimento preserva os efeitos já aplicados e interrompe a continuação.
Uma abordagem preserva as posições e abre espaço para resposta ainda no modo
narrado. Se houver iniciativa de NPC, o fluxo solicita sua decisão e resolve o turno.
Uma oportunidade que exige escolha pausa o processamento e conserva a parte
ainda não executada para a retomada.

O relatório registra o que ocorreu, enquanto o estado do fluxo indica se a
interação terminou, falhou ou aguarda entrada. Uma ação fisicamente bloqueada
pode ter sua explicação entregue com sucesso. Falha de narração também não
desfaz nem repete operações anteriores.

## Relações com outras áreas

- [Regras](../regras/README.md) e [Mundo](../mundo/README.md) fornecem cálculos,
  geometria e dados para execução e percepção.
- A [IA](../ia/README.md) implementa os serviços de interpretação, decisão e
  narração. Seus contextos são produzidos pela aplicação a partir do estado real.
- As [Interfaces](../interfaces/README.md) traduzem entradas e apresentam
  resultados. A agenda de execução pode variar, mantendo a mesma coordenação.
- O [Simulador](../simulador/README.md) acrescenta dados e adjudicação de cenário
  sobre as operações existentes.
- A [Observabilidade](../observabilidade/README.md) acompanha etapas, chamadas e
  operações; a [Qualidade](../qualidade/README.md) verifica efeitos e fronteiras.

## Documentos de tier 3

| Assunto | Referência de tier 3 |
| --- | --- |
| Interpretação semântica e validação de planos | [planos-e-validacao](planos-e-validacao.md) |
| Conversa antes do combate | [abordagem e Influence](conversa-antes-do-combate.md) |
| Fluxo do jogo e modos | [fluxo-do-jogo](fluxo-do-jogo.md) |
| Movimento contextual e preparação espacial | [movimento-contextual](movimento-contextual.md) |
| Comunicação visual dirigida | [comunicacao-gestual](comunicacao-gestual.md) |
| Inspeção sem abertura de portas e grades | [inspecao-de-passagens](inspecao-de-passagens.md) |
| Execução das respostas do Mundo | [execucao-do-mundo](execucao-do-mundo.md) |
| Resultados, impedimentos e memória mecânica | [resultados-e-impedimentos](resultados-e-impedimentos.md) |
| Composição e ciclo de vida da partida | [composicao](composicao.md) |
| Sessão, conversa e histórico | [sessoes-e-conversa](sessoes-e-conversa.md) |
| Foco, pendências e propostas versionadas | [estado-da-conversa](estado-da-conversa.md) |
| Opiniões privadas e contribuições por termo | [opinioes-por-opcao](opinioes-por-opcao.md) |
| Confiança, afeto e fontes das relações iniciais | [relacoes-iniciais](relacoes-iniciais.md) |
| Evolução por episódios percebidos e memória dos encontros | [evolucao-das-relacoes](evolucao-das-relacoes.md) |
| Formação, manutenção e ruptura de amizade e romance | [vinculos-afetivos](vinculos-afetivos.md) |
| Reconsideração por acontecimentos, interrupção e retomada | [acontecimentos-e-prioridades](acontecimentos-e-prioridades.md) |

A memória da sessão e da conversa é mantida em processo. A entrada validada de
histórico não é um mecanismo geral de salvar e carregar partidas. APIs e limites detalhados estão nas referências de tier 3.

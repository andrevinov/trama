# Qualidade e validação

Tier 2 · [Visão geral do Trama](../../../README.md) ·
[Aplicação](../aplicacao/README.md) · [IA](../ia/README.md) ·
[Observabilidade](../observabilidade/README.md)

Esta área reúne a estratégia de testes, a avaliação dos modelos reais e a
manutenção dos contratos e da documentação. É uma responsabilidade transversal
do desenvolvimento, apoiada nas mesmas estruturas que a aplicação utiliza.

## Responsabilidade e fronteiras

Compartilhar implementação evita que testes de fluxo completo conduzam uma
versão paralela do jogo. Os testes continuam responsáveis por entradas,
condições iniciais, controle de aleatoriedade, observação e critérios esperados.
Essas expectativas precisam ser independentes dos resultados que estão avaliando.

Testes locais verificam regras e integração sem serviços externos. Live tests
avaliam caminhos declarados com serviços reais, preservando configuração e
evidências. Um contrato parcial ou experimento de provedor deve ser identificado
como tal; sua aprovação não comprova o fluxo completo de uma partida.

## Partes desta área

| Parte | O que verifica ou orienta | Referência |
| --- | --- | --- |
| Testes unitários | Regras e componentes isolados com entradas e resultados controlados. | [tests/unit](../../../tests/unit) |
| Integração local | Componentes reais em conjunto, incluindo UI sem tela e transporte simulado quando necessário. | [tests/integration](../../../tests/integration) |
| Live tests | Comportamentos com serviços reais e critérios declarados por suíte. | [tests/live](../../../tests/live/README.md) |
| Disposição social | Alinhamento, persona, memória relevante e concessões limitadas na conversa. | [Bateria social](disposicao-live.md) |
| Vínculos de memória | Um fato com consequências para vários interesses, contado uma vez. | [Três regressões live](vinculos-memoria-live.md) |
| Conclusão de NPCs | Movimento limitado, continuação de ações, recuperação e devolução do controle. | [Turnos de NPCs](turnos-npc-live.md) |
| Conhecimento dos NPCs | Origem, desconhecimento, informação antiga e transmissão de relatos. | [Conhecimento live](conhecimento-live.md) |
| Análise parcial de interpretação | Comparar variantes do adaptador com expectativas independentes, sem executar ações do jogo. | [Análise de interpretação](analise-de-interpretacao.md) |
| Preparação de situações | Construção de estados reproduzíveis por operações públicas e verificação de pré-condições. | [Preparação reproduzível](preparacao-de-cenarios.md), [fixtures contextuais](../../../tests/fixtures/contextual_movement/README.md) |
| Contratos de contexto | Revisão de mudanças nos dados, instruções e esquemas construídos pela aplicação. | [Contratos e procedimento de revisão](../ia/contextos-e-contratos.md) |
| Detecção de regressões | Demonstrar que os critérios reprovam efeitos ausentes ou divergentes. | [Controles positivos e negativos](deteccao-de-regressoes.md) |
| Evidências | Relacionar observações, configuração, estado e resultados às execuções avaliadas. | [Artefatos e classificação de resultados](movimento-contextual-live.md#evidências-e-classificação) |
| Documentação | Manter uma referência por assunto, com navegação entre visão geral, módulos e detalhes. | [Convenções da hierarquia](../../../README.md#como-vamos-construir-e-documentar) |

## Política dos live tests

Antes de criar, alterar ou executar um teste live, leia obrigatoriamente a
[política dos live tests](politica-live-tests.md), conforme o
[AGENTS.md](../../../AGENTS.md). A suíte padrão continua independente de rede,
credenciais e modelos. Criar um caso não autoriza executar chamadas pagas.

Um experimento real declara antecipadamente escopo, configuração, repetições e
limites. Falhas e inconclusivos são preservados, sem substituição por respostas
conhecidas ou repetição até passar. A mesma composição, o carregador, os contextos
e o coordenador do simulador conduzem o trecho que se apresenta como fluxo completo.

Condições iniciais podem ser preparadas deterministicamente e validadas antes
de consultar o modelo. Essa preparação não avalia como a IA chegaria àquela
situação desde o início. Rolagens controladas não substituem as regras que as usam.

## Cobertura e limites da confiança

Os casos de movimento contextual usam abertura e envio pelo runner compartilhado,
incluindo decisões de NPCs e narração. As outras suítes live mantêm coberturas
parciais ou experimentais. A [cobertura atual](cobertura-atual.md) distingue o escopo implementado das
[evidências de execução](../../evidencias/README.md).

Comparar janela e runner ajuda a verificar integração; ambos também precisam
satisfazer expectativas independentes. Caso contrário, podem compartilhar o
mesmo erro. Os controles negativos verificam que a ausência de movimento, ataque,
conclusão de NPC ou oportunidade pode reprovar mesmo com resposta formalmente válida.

Asserções de estado e recursos não certificam toda narração. Afirmações sobre
posição, segredos ou vantagens precisam de avaliação apropriada do texto. O
[relatório do experimento contextual](../../evidencias/2026-11-16-movimento-contextual/relatorio.md)
preserva essa distinção. Uma execução por situação não mede repetibilidade.

## Relações com outras áreas

- As [Regras](../regras/README.md) oferecem cálculos com aleatoriedade injetável;
  o [Mundo](../mundo/README.md) oferece dados e validadores reais de cenários.
- A [Aplicação](../aplicacao/README.md) fornece entradas públicas e o fluxo que
  deve ser compartilhado pelos consumidores avaliados.
- A [IA](../ia/README.md) tem contratos e configurações observáveis. A
  verificação offline de referência detecta mudanças, mas não gera os pedidos live.
- As [Interfaces](../interfaces/README.md) têm verificações próprias de desenho,
  entrada e agendamento; testes sem janela não demonstram renderização do Pygame.
- O [Simulador](../simulador/README.md) fornece cenários reais; a
  [Observabilidade](../observabilidade/README.md) permite auditar a execução.

## Documentos de tier 3

| Assunto | Referência de tier 3 |
| --- | --- |
| Dificuldades contextuais e memórias live | [Casos, critérios e orçamento](dificuldade-live.md) |
| Política dos live tests | [politica-live-tests](politica-live-tests.md) |
| Preparação reproduzível de situações | [preparacao-de-cenarios](preparacao-de-cenarios.md) |
| Análise parcial do contrato de interpretação | [analise-de-interpretacao](analise-de-interpretacao.md) |
| Percepção de NPCs live | [Sentidos, casos e orçamento](percepcao-live.md) |
| Conversa antes do combate live | [Casos, critérios e orçamento](conversa-live.md) |
| Movimento contextual pelo fluxo compartilhado | [movimento-contextual-live](movimento-contextual-live.md) |
| Demonstração offline de detecção de regressões | [deteccao-de-regressoes](deteccao-de-regressoes.md) |
| Testes locais e fronteiras | [testes-locais](testes-locais.md) |
| Cobertura atual e evidências | [cobertura-atual](cobertura-atual.md) |
| Manutenção da hierarquia documental | [documentacao](documentacao.md) |

Os índices descrevem o funcionamento atual. O plano e a cronologia da implementação ficam no
[arquivo de roadmaps](../../roadmaps/README.md); resultados observados ficam em
[evidências](../../evidencias/README.md).

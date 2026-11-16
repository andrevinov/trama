# Observabilidade e investigação

Tier 2 · [Visão geral do Trama](../../../README.md) ·
[Aplicação](../aplicacao/README.md) · [IA](../ia/README.md) ·
[Qualidade](../qualidade/README.md)

A observabilidade permite acompanhar o que o jogador pediu, o que foi proposto,
o que passou na validação e quais efeitos foram realmente aplicados. Eventos
correlacionados ligam a conversa, as operações do motor e as chamadas à IA.

## Responsabilidade e fronteiras

Cada módulo produz eventos com `logging` da biblioteca padrão. Um envelope comum
identifica origem, instante e contexto; os dados específicos preservam o que é
relevante para movimento, ataque, teste, poder ou chamada de serviço.

A configuração de destinos, formatação, rotação e correlação fica centralizada.
As ferramentas de leitura consomem os eventos sem executar regras. Usar os
componentes como biblioteca não deve configurar arquivos ou o logger raiz
automaticamente.

## Partes desta área

| Parte | Responsabilidade | Referência |
| --- | --- | --- |
| Produção de eventos | Registrar entradas, resultados, propostas, confirmações e falhas nos módulos que os conhecem. | [Contrato e uso por módulos](logs.md#uso-por-módulos) |
| Envelope e destinos | Formatar JSONL, correlacionar escopos e configurar arquivos e rotação. | [observability.py](../../../src/trama/observability.py) |
| Instrumentação de IA | Registrar pedidos, respostas, duração, configuração e uso informado pelo provedor. | [openai_json.py](../../../src/trama/infrastructure/openai_json.py), [openai_services.py](../../../src/trama/infrastructure/openai_services.py) |
| Análise com lnav | Mostrar eventos, chamadas e erros, com prévias e acesso ao conteúdo completo. | [Pacote e comandos](investigacao-com-lnav.md) |
| Evidências de avaliação | Preservar logs e resultados dos experimentos, associados à configuração e ao caso. | [Fluxo contextual e evidências](../qualidade/movimento-contextual-live.md#evidências-e-classificação) |

## O que os registros demonstram

Um plano proposto, uma operação autorizada e um efeito aplicado são etapas
distintas. Investigar uma falha exige acompanhar essa sequência até o relatório
e o estado final. JSON válido ou um evento de orçamento calculado, isoladamente,
não demonstram que uma ação aconteceu.

O modo normal registra conversa, operações, resultados, erros e consumo de IA
informado. Debug acrescenta pedidos completos, respostas e detalhes técnicos.
As decisões observáveis são as saídas do modelo; os logs não expõem seu raciocínio
interno. Também não há chamadas extras à IA para produzir logs.

Consumo ausente permanece desconhecido. Cache e raciocínio são detalhamentos
dos contadores, não parcelas para somar novamente ao total. Uma rejeição de
resposta pode ter consumo registrado, mesmo sem produzir efeito no jogo.

## Relações com outras áreas

- As [Regras](../regras/README.md) registram cálculos e rolagens; a
  [Aplicação](../aplicacao/README.md) registra execução e mudanças na sessão.
- A [IA](../ia/README.md) tem seus parâmetros, pedidos e respostas ligados à
  interação e às operações correspondentes.
- As [Interfaces](../interfaces/README.md) registram entradas e falhas de
  agendamento; a correlação acompanha os pedidos entre threads.
- O [Simulador](../simulador/README.md) configura o diagnóstico da execução;
  consultas e desenho de frames não geram logs a cada acesso.
- A [Qualidade](../qualidade/README.md) usa essas evidências para conferir o
  caminho real de cada caso, preservando também resultados desfavoráveis.

## Documentos de tier 3

| Assunto | Referência de tier 3 |
| --- | --- |
| Logs estruturados | [logs](logs.md) |
| Formato do Trama para lnav | [investigacao-com-lnav](investigacao-com-lnav.md) |

Os arquivos brutos de `logs/` são locais e ignorados pelo Git. Relatórios
versionáveis podem registrar conclusões, proveniência e hashes; sua existência
não implica que os logs locais acompanhem um clone do repositório.

# IA: interpretação, decisão e narração

Tier 2 · [Visão geral do Trama](../../../README.md) ·
[Aplicação](../aplicacao/README.md) · [Qualidade](../qualidade/README.md)

A IA participa do jogo em três papéis separados: interpretar o que o jogador
pediu, propor respostas do Mundo e narrar os fatos produzidos. Cada papel recebe
contexto próprio e devolve uma resposta estruturada pelo contrato correspondente.

## Papéis e fronteiras

| Papel | O que recebe e devolve | Contrato e implementação |
| --- | --- | --- |
| Interpretador do jogador | Recebe o pedido on e o contexto de capacidades e alvos conhecidos; propõe etapas e sua relação com o texto do jogador. | [intents.py](../../../src/trama/application/intents.py), [openai_intent_interpreter.py](../../../src/trama/infrastructure/openai_intent_interpreter.py) |
| Diretor do Mundo | Recebe estado do Mundo e proposta do jogador, ou a situação do NPC ativo; propõe respostas, testes e ações de NPCs. | [world.py](../../../src/trama/application/world.py), [openai_world_director.py](../../../src/trama/infrastructure/openai_world_director.py) |
| Narrador | Recebe estado, percepção, histórico e resultados executados; devolve descrição on e explicações off. Também atende abertura e perguntas exclusivamente off. | [dialogue.py](../../../src/trama/application/dialogue.py), [openai_narrator.py](../../../src/trama/infrastructure/openai_narrator.py) |

A [Aplicação](../aplicacao/README.md) escolhe quando consultar cada papel e
valida suas respostas. As [Regras](../regras/README.md) calculam movimento,
rolagens e efeitos. Uma proposta de ataque ainda não é um ataque realizado;
uma frase narrada também não altera o estado da partida.

A interpretação semântica continua sendo da IA. O validador determinístico
confere estrutura, referências e consistência das origens declaradas; ele não
reinterpreta o português para provar que a classificação semântica está correta.
Os critérios de avaliação precisam considerar essa diferença.

## Contextos e informação permitida

A aplicação constrói projeções por fase a partir da sessão, do histórico e dos
relatórios reais. Os contratos ficam em
[context_contracts.py](../../../src/trama/application/context_contracts.py); a
projeção mínima do interpretador é preparada por
[interpretation_context.py](../../../src/trama/application/interpretation_context.py).

O interpretador recebe capacidades e referências úteis à intenção, sem histórico
off ou estado completo secreto do Mundo. O diretor recebe o contexto completo
para decidir respostas. O narrador recebe fatos executados e percepção, além do
Mundo completo para coerência; suas instruções exigem preservar segredos e
descrever somente o que cabe ao conhecimento do jogador.

Os contratos distinguem interpretação, resposta do Mundo, turno de NPC e
narração inicial, de resultado ou exclusivamente off. A verificação de seus
dados não certifica toda afirmação produzida em linguagem natural. A
[Qualidade](../qualidade/README.md) combina asserções mecânicas e revisão narrativa.

## Integração e configuração

Os adaptadores usam o SDK oficial Python da OpenAI, autenticado por variável
de ambiente, e a Responses API com JSON Schema. O transporte comum está em
[openai_json.py](../../../src/trama/infrastructure/openai_json.py).

A configuração e a criação dos serviços ficam em
[openai_config.py](../../../src/trama/infrastructure/openai_config.py) e
[openai_services.py](../../../src/trama/infrastructure/openai_services.py).
O simulador e os testes resolvem os padrões pela mesma composição. Variantes de
modelo, contexto ou esquema usadas em experimentos são identificadas nas evidências.

Correção de interpretação e repetição de transporte são mecanismos distintos.
Um limite de chamadas pode ser compartilhado pelos adaptadores por
[call_budget.py](../../../src/trama/infrastructure/call_budget.py); ele limita
despachos ao SDK e não é um teto monetário. Parâmetros e condições detalhadas
pertencem à referência de configuração.

## Relações com outras áreas

- A [Aplicação](../aplicacao/README.md) produz contextos, agenda os serviços e
  aplica resultados; ela depende dos contratos dos papéis.
- O [Mundo](../mundo/README.md) fornece geometria e percepção. A informação
  conhecida para navegação não equivale à visão atual de um objeto ou criatura.
- O [Simulador](../simulador/README.md) pode adjudicar respostas determinísticas
  de exploração. O diretor é orientado a respeitar esse recorte e evitar duplicá-las.
- As [Interfaces](../interfaces/README.md) recebem as falas finais pelo fluxo;
  a integração com o provedor permanece na infraestrutura.
- A [Observabilidade](../observabilidade/README.md) registra pedidos, respostas,
  decisões observáveis, validações e uso informado pelo serviço.

## Documentos de tier 3

| Assunto | Referência de tier 3 |
| --- | --- |
| Contratos de contexto da IA | [contextos-e-contratos](contextos-e-contratos.md) |
| Integração OpenAI e configuração dos serviços | [integracao-openai](integracao-openai.md) |
| Interpretação da intenção do jogador | [interpretacao-do-jogador](interpretacao-do-jogador.md) |
| Decisão do Mundo e turnos de NPCs | [decisao-do-mundo](decisao-do-mundo.md) |
| Narração, canais e fatos executados | [narracao](narracao.md) |

As respostas reais podem variar. JSON válido e coerência declarativa são
condições verificáveis, mas a fidelidade à intenção e aos fatos também precisa
ser avaliada nos comportamentos e textos observados.

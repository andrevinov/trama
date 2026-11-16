# Narração, canais e fatos executados

Tier 3 · [IA](README.md) · [Visão geral](../../../README.md)

## Contrato e fases

Código: [dialogue.py](../../../src/trama/application/dialogue.py),
[openai_narrator.py](../../../src/trama/infrastructure/openai_narrator.py).
O narrador recebe contexto da aplicação e devolve `NarratorReply` com `on` e
`off`. As fases são abertura, resposta de resultado e resposta exclusivamente
off; sua definição está nos [contratos](contextos-e-contratos.md).

A abertura descreve local, estado e percepção. A resposta de resultado descreve
os efeitos e as interações realizados, e explica dúvidas ou interrupções.
Perguntas exclusivamente off não autorizam fala on ou nova ação física.

## Fonte dos fatos

`execution` contém eventos, reações, progresso, impedimentos e etapas não
executadas. O resumo `player_movement` informa ocorrência, distância e origem/
destino reais. `previous_execution` conserva a tentativa anterior e sua situação
final. Consulte [resultados](../aplicacao/resultados-e-impedimentos.md).

Uma proposta de caminhada não basta para narrar deslocamento. Uma busca impedida
não revela seu conteúdo; coletar um item não pode deixá-lo novamente disponível
no chão. Falar ou observar podem ser interações narráveis sem mudança mecânica.
Sem progresso ou interação realizada, um impedimento recebe explicação em off.

O narrador conhece o Mundo completo para coerência e recebe `perception` com os
fatos apropriados. Deve preservar NPCs ocultos, itens não descobertos e identidade
secreta do prisioneiro. A visibilidade da UI é calculada pelo código; obediência
às instruções em texto precisa de avaliação própria.

## Regras e falhas

Explicações usam `verified_rules` e as referências implementadas. O modelo deve
pedir base quando uma mecânica não está definida no projeto, sem criar uma regra
para uma edição diferente. Valores e impedimentos devem corresponder ao registro.

A aplicação acrescenta deterministicamente explicação de parada quando necessário.
A fala entregue, incluindo essa complementação, é registrada nos logs.
Falha do narrador não desfaz nem repete uma operação já executada; o fluxo
preserva resultado e apresenta a indisponibilidade.

## Verificação e limites

As regressões em [test_dialogue.py](../../../tests/unit/test_dialogue.py) e
[test_game_flow.py](../../../tests/integration/test_game_flow.py) verificam contratos e
preservação dos efeitos. A [detecção de regressões](../qualidade/deteccao-de-regressoes.md)
mostra que texto de movimento não substitui posição e percurso.
O [experimento contextual](../../evidencias/2026-11-16-movimento-contextual/relatorio.md)
registra problemas semânticos que a aprovação mecânica não certifica, incluindo
regras em on e adjetivos que podem sugerir vantagem inexistente.

# Movimento terrestre e unidades

Tier 3 · [Regras](README.md) · [Visão geral](../../../README.md)

## Contratos e cálculo

Código: [movement.py](../../../src/trama/movement.py), [distances.py](../../../src/trama/distances.py).
`MovementState` contém posição, velocidade, gasto, Dash e saldos especiais.
`MovementRequest` fornece um percurso de casas adjacentes; `MovementResult`
devolve o estado resultante, percurso aceito, custo, proteção e motivo de parada.
`step_cost` valida um passo; `apply_movement` resolve o prefixo legal do percurso.

Cada passo entra em uma casa adjacente. Casas bloqueadas, saída do mapa e
corte de quina de obstáculo impedem o passo. Diagonais custam uma casa, sem
alternância de custo. Terreno difícil dobra o custo da casa de destino.
O cálculo usa `Decimal`; pixels pertencem à apresentação.

## Cenário e unidades

A unidade padrão é o metro. Uma casa corresponde a 1,5 m; terreno difícil
custa 3 m. A conversão de entrada usa a convenção de D&D: 5 pés correspondem
a 1,5 m. Entrada sem unidade é interpretada como metros.

O domínio usa `Position(x, y)` em base zero. A tela e os contextos de IA
apresentam coluna e linha em base um. Norte fica para cima, linhas crescem
para baixo e colunas para a direita. Essa mudança de representação não altera
as distâncias.

Uma distância como 5 m corresponde a três casas inteiras, 4,5 m, e um resto
de 0,5 m explicado ao jogador. A tradução de segmentos e destinos para percurso
é da [aplicação](../aplicacao/movimento-contextual.md), não do cálculo de passo.

## Saldo e interrupção

Em combate, o próximo passo só acontece se puder ser pago. Dash acrescenta
velocidade ao orçamento quando autorizado e disponível; a aplicação controla
o gasto de ação e os usos adicionais. Movimento protegido de Campeão tem saldo
próprio e é consumido antes do normal.

`turn_based=False` ignora apenas o limite por turno: obstáculos continuam
válidos. O [modo narrado](../aplicacao/fluxo-do-jogo.md#modos) usa
esse caminho, sem conceder travessia de paredes ou portas fechadas.

Um impedimento registra `stop_reason`, `stop_code` e `blocked_position`, mantendo
o trecho aceito. Reações e ocupantes são coordenados durante o deslocamento por
[TravelExecutor](../../../src/trama/application/travel.py). O gatilho de oportunidade
não faz parte do core de movimento.

## Referências e limites

Referências adotadas: PHB 2024, Playing the Game, movimento/grade e Dash
(pp. 24–25), e DMG 2024, Diagonals (p. 45). Usa-se a diagonal simples do PHB;
a alternativa de custos alternados do DMG não foi ativada. O recorte não resolve
salto, escalada, voo, natação, montarias ou um motor geral de condições.

Os limites de segmentos e distância são validados em
[intents.py](../../../src/trama/application/intents.py). A aproximação implícita pertence
à aplicação; ela não amplia a velocidade nem autoriza Dash ou abrir barreiras.

## Verificação e relações

[Testes unitários](../../../tests/unit) verificam custo, saldo e prefixos; as regressões
[integradas de movimento contextual](../../../tests/integration/test_contextual_movement.py)
verificam a ligação com a ação. Consulte [mapas](../mundo/mapas-e-passagens.md),
[reações](reacoes.md) e [impedimentos](../aplicacao/resultados-e-impedimentos.md).

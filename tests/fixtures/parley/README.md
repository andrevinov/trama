# Casos de abordagem e conversa

`cases.json` contém somente mensagens, expectativas e limites do experimento.
Preparação, estado inicial e dados pertencem às quatro situações jogáveis do
[catálogo da aplicação](../../../src/trama/scenarios/situations.json).
Os critérios e a execução ficam em `tests/live/test_parley.py`, usando o runner
real. Nenhum contexto, esquema ou resposta de modelo é congelado aqui.

Consulte [escopo, critérios, autorização e orçamento](../../../docs/sistema/qualidade/conversa-live.md)
antes de executar a bateria. Há quatro casos e uma repetição de cada: abordagem
distante, persuasão bem-sucedida, persuasão falha e escolha explícita de ataque.

# Casos de percepção por NPC

`cases.json` guarda mensagens, expectativas e teto de chamadas dos 13 casos.
Os perfis sensoriais, mapa, posições, dados e preparação estão nas situações do
[catálogo da aplicação](../../../src/trama/scenarios/situations.json), sobre
`perception_rooms.json`. A mesma situação pode ser aberta na janela e reiniciada.

Os [live tests](../../live/test_npc_perception.py) usam `open_situation` e o runner
oficial. Os critérios observam efeitos e estados, sem recalcular o esperado pelo
mesmo algoritmo. Não há cópias de schemas, prompts ou respostas nestas fixtures.
Consulte [escopo, critérios, autorização e orçamento](../../../docs/sistema/qualidade/percepcao-live.md).

# Aproximação e ataques de oportunidade

Tier 3 · [Regras](README.md) · [Visão geral](../../../README.md)

## Destinos que são criaturas

As criaturas visíveis têm `id`, `name` e `number` no contexto do interpretador.
`number` é a identificação mostrada no mapa e permanece a mesma ao ocultar ou
revelar criaturas. A interpretação usa o id existente, não inventa um destino.

`move(target_id="guard_1")` busca o menor custo até uma casa livre, adjacente e
com linha de visão para o Guarda 1. Nunca entra no espaço ocupado por ele.
Se já estiver adjacente, não gasta movimento. O destino é recalculado com a
posição atual da criatura; um alvo oculto não pode ser usado para navegar.
O modo por turnos mantém o limite de deslocamento, e uma aproximação incompleta
impede o ataque seguinte. A IA não recebe autorização para atacar só por caminhar.

O pedido observado `Eu vou até o guarda 1 e o ataco.` corresponde a aproximação
e ataque separados. A interpretação semântica resolve o pronome `o`; o validador
confere origens declaradas e referências, sem analisar verbos ou pronomes.

## Regra e implementação

Referência: [D&D Basic Rules 2024, Playing the Game — Opportunity Attacks e
Reactions](https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game#OpportunityAttacks).

Sair do alcance de um adversário que vê a criatura pode provocar um ataque
corpo a corpo antes da saída. Ele usa uma reação, recuperada no início do
próximo turno de quem atacou. Entrar ou permanecer no alcance não provoca.
Movimento protegido por uma regra específica não provoca; teleporte e movimento
sem uso de movimento/ação/bônus/reação também não provocam. Desengajar protege
o deslocamento, mas ainda não é uma operação deste jogo.

O gatilho em `reactions.py` é independente de fichas, combate, Pygame e IA.
`application/travel.py` coordena os passos, verifica visão e reação disponível,
e usa `Encounter.attack(..., opportunity=True)`. O core de movimento permanece
independente de combate. Um passo inválido ou sem saldo não provoca.

O ataque reaproveita as regras existentes de dano, crítico e maestrias. Se
reduzir o alvo a 0 PV, o passo não acontece. Slow pode reduzir o saldo antes
dele; a aplicação verifica novamente o movimento. Os resultados entram no
relatório e nos logs antes da narração. Os trechos anteriores permanecem feitos.

## Escolha e limites do cenário

- Guardas hostis usam automaticamente oportunidades legais, na ordem do cenário
  quando vários podem reagir ao mesmo passo. Essa é uma política da demonstração,
  não uma obrigação imposta pela regra de D&D.
- O personagem confirma cada oportunidade. O jogo pausa antes do passo e mostra
  **Atacar (reação)** e **Deixar passar** no painel de turno. Recusar não gasta a
  reação. A continuação preserva os passos e ações anteriores, sem nova chamada
  de interpretação ou decisão do Mundo para repetir o que já estava aprovado.
- `GameSession.auto_opportunity=True` permite uso automático somente quando o
  controlador o autorizar explicitamente. O padrão é confirmação.
- O ataque usa a primeira arma equipada na ficha, ou ataque desarmado quando
  essa arma não estiver utilizável. Não há seletor de arma para a reação neste
  incremento. O equipamento atual não distingue arma guardada de empunhada.
- As criaturas atuais são Humanas com visão normal e alcance corpo a corpo de
  1,5 m. Não há alcance estendido, teleporte, movimento forçado, Desengajar,
  Preparar, talentos adicionais ou testes de morte neste incremento.
- A integração aplica os gatilhos durante conflito com iniciativa; não cria
  ataques automáticos enquanto o jogo estiver no modo narrado.
- O movimento imediato de Campeão após crítico usa o saldo protegido existente
  e não provoca oportunidade. Um movimento imediato fora do turno, após um
  crítico de reação, ainda não tem uma etapa de escolha própria na interface.

Eventos `reaction.opportunity_triggered`, `reaction.opportunity_resolved` e
`reaction.player_decided` registram atores, transição, escolha, rolagens e efeitos.
Consultas da ficha não gastam reação nem executam ataques. Preparar continua
identificado como indisponível.

As regressões em `tests/integration/test_approach_creature.py`,
`test_opportunity_attacks.py` e `test_movement_window.py` usam planos fixos, dados
controlados e renderização local; não exigem API, credenciais ou chamadas pagas.

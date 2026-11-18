# Inspeção de portas e grades

Tier 3 · [Aplicação](README.md) · [Visão geral](../../../README.md)

## Operação e limites

`InspectionIntent` em [intents.py](../../../src/trama/application/intents.py)
representa `inspect_passage`, disponível em qualquer cenário com passagens.
`GameSession` valida e executa; a dungeon usa a mesma implementação.

| Método | Alcance e custo | Informação |
| --- | --- | --- |
| `visual` | Posição atual, passagem visível; sem aproximação ou interação. | Aberta/fechada e trancamento previamente conhecido. Fechadura desconhecida continua com `locked=null`. |
| `mechanism` | Alcance de interação com linha de visão; aproximação contextual apenas por `allow_approach`. | Conferência cuidadosa do mecanismo simples e acessível, sem abrir ou destrancar. |

“Eu checo se a Cela 4 está trancada, sem fazer barulho” referencia `gate_4`,
com método `mechanism` e `volume=quiet`. Não é investigação do cômodo, entrada,
tentativa de abrir, uso de chave ou novo Hide. Apenas olhar, explicitamente,
usa `visual`, `volume=normal`, `allow_approach=false`. Ausência de alvo identificável
exige esclarecimento; o interpretador não escolhe uma passagem arbitrária.

O relatório registra alvo, método, volume (nulo na observação), `is_open`,
`locked`, resumo e `physical_change=false`. Conferir conta como interação
realizada/progresso, ainda que não altere a porta. O narrador usa esses fatos,
sem completar abertura, destrancamento ou testes.

## Decisão de mestre e referência de D&D

As [regras básicas de 2024, testes de atributo e interação com objetos](https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game)
reservam testes para resultados incertos com possibilidade de falha significativa.
Não há uma CD universal de “ver se está trancada”.

Neste incremento, **decisão explícita do Trama**: conferir um mecanismo simples
e acessível é determinístico. Consome a interação gratuita em combate, ou a ação
se a interação já foi usada, pela política de objetos existente. Fora de combate
não consome recursos de turno. Apenas olhar não consome interação nem avança a
rotina da dungeon.

`Passage.lock_checkable` é um booleano do cenário, padrão `true` para os mecanismos
simples existentes. `false` significa que essa conferência sem abertura não pode
revelar o estado: ele continua desconhecido, sem inventar teste ou CD. Não há
detecção de armadilhas, arrombamento, análise de mecanismo complexo ou resolução
de fechadura mágica neste recorte. Não se acrescenta chamada à IA para esses
resultados determinísticos.

## Furtividade, som e informação

Conferir com `volume=quiet` emite um ruído discreto pelo motor de percepção
existente. Preserva o total atual de Furtividade; uma detecção real ainda pode
encerrar a ocultação. Não garante silêncio nem invisibilidade. Emissão normal
encerra Hide como os outros ruídos normais. Barreiras auditivas usam a avaliação
contextual já existente na decisão do Mundo, sem chamada separada de dificuldade.

O estado examinado é uma lembrança do jogador e também entra em seu conhecimento
com fonte de observação. NPCs não aprendem o resultado pelo simples fato de ver
a conferência. Mudanças ocultas não atualizam essa lembrança automaticamente.
O mapa do interpretador e as etiquetas da interface usam a lembrança; o mapa de
mestre preserva a verdade. Reiniciar apaga a inspeção.

## Esclarecimentos sem efeitos

Um plano composto somente por pedido de esclarecimento não consulta o Mundo,
não emite som, não altera recursos, não acompanha intenções dos NPCs e não avança
rotinas. A resposta chega à narração com `clarification_required`.
Em planos mistos, etapas reais anteriores continuam sendo executadas; a dúvida
encerra o plano, sem executar reações propostas para a etapa de esclarecimento.

## Verificação

[Regressões locais](../../../tests/integration/test_passage_inspection.py) cobrem
efeitos, alcance, custo, escuridão, memória, reinício, furtividade e esclarecimentos.
Os [quatro live tests](../qualidade/inspecao-live.md) avaliam interpretação e narração
reais, com critérios e autorização próprios.

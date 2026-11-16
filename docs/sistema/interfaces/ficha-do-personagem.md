# Ficha e opções disponíveis

Tier 3 · [Interfaces](README.md) · [Visão geral](../../../README.md)

## Fichas e escolhas do cenário

A guia **Ficha** mostra um resumo de PV, CA, velocidade e classe, com três seções:

- **Agora — O que posso fazer:** cartões de movimento, ataque, Retomar o Fôlego,
  Surto de Ação, portas, Dash, interação e encerramento de turno. Cada um indica
  disponibilidade, condição ou impedimento atual. Preparar aparece sem execução.
- **Recursos — Fora do turno e recuperação:** reação, Inspiração Heroica, Mente
  Tática, usos com recuperação por descanso e itens mágicos. Oportunidades usam
  a reação e pedem confirmação quando surgem. Mente Tática e descansos ainda não têm comandos; o cenário não registra efeitos
  de itens mágicos. A ficha distingue essas limitações de um recurso gasto.
- **Dados:** atributos, salvaguardas, perícias, equipamento, maestrias e traços.

Clique no cabeçalho de um cartão para expandir/recolher detalhes de uso, custo,
momento, recuperação e exemplos. Role sobre o painel para continuar a leitura.
A consulta não altera o jogo e pode ser feita enquanto uma resposta está em
andamento. As ações são solicitadas pela conversa. A projeção é calculada pela
aplicação, sem SDK ou Pygame; a interface apenas apresenta o resultado. Esta
mudança não adiciona novas ações de combate, itens ou regras de descanso.

## Projeções e verificação

[sheet_options.py](../../../src/trama/application/sheet_options.py) calcula custos,
recuperação e disponibilidade. [sheets.py](../../../src/trama/application/sheets.py)
publica dados e resumos; [character_panel.py](../../../src/trama/ui/character_panel.py)
organiza a apresentação. Consulta não executa efeito. PV/CA/equipamento vêm da
ficha atual: a dungeon começa sem itens, diferentemente do mapa legado.

O painel de inimigos é filtrado pela visão e conserva identificação. Preparar
aparece sem execução; ausência de implementação é diferente de ação gasta.
Não há efeitos de itens mágicos registrados neste cenário. As regressões em
[test_movement_window.py](../../../tests/integration/test_movement_window.py)
e [tests/unit](../../../tests/unit) verificam projeção, consulta e desenho.

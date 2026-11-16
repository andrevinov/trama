# Simulador — fuga da dungeon

[Visão do módulo](../../docs/sistema/simulador/README.md) ·
[Cenário e adjudicação](../../docs/sistema/simulador/fuga-da-dungeon.md)

## Objetivo e escopo

Exercitar exploração, conversa, percepção, portas, itens e combate no mesmo
fluxo da aplicação. O cenário está em [dungeon.json](dungeon.json): quatro celas,
corredor iluminado, um guarda, banheiro e saída. O jogador é Guerreiro Humano 3,
Campeão/Defesa, em trapos e sem itens, começando ao ouvir sua cela abrir sozinha.

## Preparação e execução

Na raiz, com Python 3.14, Poetry, ambiente gráfico e `OPENAI_API_KEY` exportada:

```bash
poetry install
poetry run python pocs/simulador/run.py --debug
```

`TRAMA_OPENAI_MODEL` seleciona o modelo. Sem chave, a janela serve para
visualização. Abertura, mensagens, turnos de NPCs e reinício podem fazer chamadas
pagas. Veja [opções de execução](../../docs/sistema/simulador/execucao.md).

## Exemplos e critérios de sucesso

- A abertura descreve o visível e a grade inicial aberta, sem NPC próximo.
- `Caminho até a grade da Cela 4 e tento abri-la.` aproxima e tenta a interação.
- `Investigo a cela.` entra se necessário e permitido; descoberta não é coleta.
- `Pego a espada longa.` aproxima do item conhecido e altera o inventário real.
- A roupa da limpeza não aumenta CA; a chave altera a fechadura de verdade.
- Disfarce, ruído e respostas do guarda produzem testes e fatos registrados.
- Há caminhos de fuga por interação, furtividade, distração ou combate conforme
  as condições resolvidas. O mapa e a conversa devem refletir o mesmo estado.
- Perguntas entre colchetes não executam ações; reinício restaura a situação.

## Simplificações e referências

As CDs e a rotina do banheiro são decisões deste cenário. O prisioneiro tem
auxílio de ilusão específico, sem motor completo de magias ou turno próprio.
As tochas justificam iluminação normal, sem propagação dinâmica. Inventário
cobre os itens necessários à aventura. Consulte [regras, fontes e limites](../../docs/sistema/simulador/fuga-da-dungeon.md)
e [objetos fixados](../../docs/sistema/mundo/objetos.md).

## Regressões

```bash
poetry run pytest tests/integration/test_dungeon_simulator.py tests/integration/test_interaction_preparation.py tests/integration/test_contextual_movement.py
poetry run pytest
```

Usam o cenário e as estruturas reais, com dados controlados e transporte
simulado quando necessário. Para avaliações reais, leia a
[política live](../../docs/sistema/qualidade/politica-live-tests.md) e as
[instruções dos testes](../../tests/live/README.md).

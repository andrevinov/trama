# Cenários de regressão

[Simulador](../../../docs/sistema/simulador/README.md) ·
[Carregamento de cenários](../../../docs/sistema/simulador/carregamento-de-cenarios.md) ·
[Política dos live tests](../../../docs/sistema/qualidade/politica-live-tests.md)

Estes arquivos preservam os mapas anteriores como dados compartilhados pelas
regressões locais, avaliações live parciais e análises de interpretação.
Todos são construídos pelo carregador real em `application/scenarios.py`, com
os mesmos validadores de mapa, fichas, passagens e objetos da aplicação.

| Arquivo | Situação preservada | Origem |
| --- | --- | --- |
| [simple_grid.json](simple_grid.json) | Grade 10×10, início interno (4,4), dois obstáculos e terreno difícil; Guerreiro equipado. | Antigo `pocs/movimento/scenario.json`. |
| [legacy_cell_and_guards.json](legacy_cell_and_guards.json) | Cela, corredor de 10,5 m e Sala dos Guardas em grade 19×11; início interno (3,5), três guardas e Guerreiro equipado. | Antigo `pocs/movimento/cela_guardas.json`. |

As coordenadas do JSON começam em zero. Os dois arquivos foram movidos sem
alterar seus bytes, geometria, fichas, equipamentos ou estados de passagem.
O cenário jogável atual é a
[dungeon do pacote](../../../src/trama/scenarios/dungeon_escape.json), cuja fonte
fica na aplicação, separada destes mapas de regressão.

## Uso pelo mesmo simulador

Na raiz, após `poetry install`:

```bash
poetry run trama-simulator --scenario tests/fixtures/scenarios/simple_grid.json
poetry run trama-simulator --scenario tests/fixtures/scenarios/legacy_cell_and_guards.json
```

Os arquivos são dados de teste do repositório, não recursos distribuídos com
o pacote. Os caminhos explícitos são relativos ao diretório atual. Interagir
com IA exige configuração e pode fazer chamadas pagas; usar outro mapa não
cria uma implementação diferente da engine.

## Critérios e verificação

No mapa Cela/Guardas, o personagem começa na coluna 4, linha 6, com a grade
aberta e a porta fechada. Os exemplos preservados incluem:

- `Ando 5 m para a direita.` percorre casas inteiras, 4,5 m, explicando a fração.
- `Caminho até a porta e abro.` aproxima e interage quando as condições permitem.
- Abrir/fechar a porta revela/oculta os guardas conforme a visão real.
- `Uso Surto de Ação e ataco o Guarda 1.` solicita duas etapas em ordem.
- Perguntas off preservam estado; uma falha de narração preserva efeitos já executados.
- As guias de ficha/inimigos consultam estado sem gastar recursos.

O corredor originalmente solicitado com 10 m usa sete casas, 10,5 m. Metros,
diagonais simples e casas inteiras seguem as regras de
[movimento](../../../docs/sistema/regras/movimento.md). Visão humana básica,
portas e alcance de interação têm os limites descritos em
[visão](../../../docs/sistema/mundo/visao-e-percepcao.md) e
[ações](../../../docs/sistema/regras/acoes.md); não há propagação dinâmica de luz.
O recorte marcial e as referências ficam em
[personagens](../../../docs/sistema/regras/personagens.md) e
[combate](../../../docs/sistema/regras/combate.md). Esses critérios não certificam
o fluxo completo das suítes live parciais.

[test_scenario_loading.py](../../integration/test_scenario_loading.py) confere
dimensões, posição, participantes, armadura e equipamento dos cenários reais.
As demais regressões controlam entradas e dados, preservando as regras reais.
Esperados são independentes do resultado calculado, e a classificação de cada
suíte continua explícita na [cobertura atual](../../../docs/sistema/qualidade/cobertura-atual.md).

```bash
poetry run pytest tests/integration/test_scenario_loading.py
poetry run python tools/context_contracts.py --check
```

Alterar ou acrescentar um mapa deve passar pelos construtores existentes.
Preservar uma situação como fixture congela seus dados, não uma cópia antiga
do motor, dos prompts ou dos contextos. As medições históricas conservam seus
nomes de origem para preservar a proveniência.

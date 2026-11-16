# Simulador e cenários

Tier 2 · [Visão geral do Trama](../../../README.md) ·
[Aplicação](../aplicacao/README.md) · [Mundo](../mundo/README.md) ·
[Interfaces](../interfaces/README.md)

O simulador é a entrada jogável usada para exercitar a engine como um todo.
Ele reúne um cenário concreto, os serviços de IA, o fluxo compartilhado e a
interface, permitindo observar exploração, interação, percepção e combate.

## Responsabilidade e fronteiras

A composição usa o mesmo carregamento e os mesmos validadores disponíveis aos
demais consumidores da aplicação. Cenário e variações são dados que passam por
essas estruturas. As regras de movimento, personagens e combate são reutilizadas.

Algumas respostas pertencem à aventura: descoberta de itens, CDs, rotina do
guarda e auxílio do prisioneiro. A sessão específica coordena esses acontecimentos
sobre a base existente. Eles não constituem um motor geral de inventário,
disfarces, rotina de NPCs ou magia.

## Partes desta área

| Parte | Responsabilidade | Código ou dados de referência |
| --- | --- | --- |
| Entrada do simulador | O comando `trama-simulator` lê opções, configura logs e entrega a partida à janela. | [simulator.py](../../../src/trama/simulator.py), [registro do comando](../../../pyproject.toml) |
| Composição da partida | Reunir sessão, serviços e fluxo; disponibilizar a agenda sem janela. | [bootstrap.py](../../../src/trama/bootstrap.py) |
| Carregamento de cenários | Ler dados, selecionar o tipo de sessão e delegar aos construtores e validadores reais. | [scenarios.py](../../../src/trama/application/scenarios.py) |
| Situações reproduzíveis | Preparar estados intermediários por operações reais, rolagens e pré-condições; reutilizar ao reiniciar. | [situations.py](../../../src/trama/application/situations.py), [catálogo](../../../src/trama/scenarios/situations.json) |
| Adjudicação da dungeon | Manter estado e resolver interações e respostas específicas da fuga. | [dungeon.py](../../../src/trama/application/dungeon.py) |
| Cenário atual | Definir arquitetura, participantes, objetos e condições iniciais da aventura. | [dungeon_escape.json](../../../src/trama/scenarios/dungeon_escape.json) |
| Cenários de regressão | Preservar os mapas anteriores como dados para os mesmos construtores. | [Fixtures de cenários](../../../tests/fixtures/scenarios/README.md) |
| Análises parciais | Comparar aspectos da interpretação, com escopo parcial identificado. | [Análise de interpretação](../qualidade/analise-de-interpretacao.md) |

## O cenário atual

A fuga começa com um Guerreiro Humano de nível 3 em trapos, sem itens, ouvindo
sua cela abrir magicamente. Quatro celas se conectam a um corredor iluminado,
uma sala com um guarda, banheiro e saída. Outro prisioneiro participa da história.

O cenário permite experimentar busca e coleta, portas e chaves, disfarce,
furtividade, resgate e combate. Itens descobertos, carregados e vestidos são
estados distintos. A fuga usa fatos e testes registrados pelo motor; narrar uma
solução não a executa.

Na exploração, parte das respostas é adjudicada pelo código específico da
dungeon. O diretor do Mundo recebe orientação para respeitar esse comportamento.
No combate, a IA propõe ações do guarda, e o executor valida e resolve seus efeitos.
O roteiro completo, seus segredos e as decisões de mestre ficam na referência
do cenário.

## Relações com outras áreas

- O [Mundo](../mundo/README.md) fornece mapa, objetos, passagens e visão; as
  [Regras](../regras/README.md) resolvem os cálculos reutilizáveis.
- A [Aplicação](../aplicacao/README.md) coordena a conversa e o estado da
  partida; a dungeon acrescenta suas operações e requisitos espaciais.
- A [IA](../ia/README.md) interpreta as capacidades disponíveis no cenário e
  narra os fatos. Decisões narrativas continuam sujeitas à execução determinística.
- As [Interfaces](../interfaces/README.md) recebem projeções do estado para
  mapa, fichas e conversa. O desenho não consulta o estado privado da aventura.
- A [Qualidade](../qualidade/README.md) prepara situações sobre o mesmo cenário
  e carregador. Isso compartilha implementação, mantendo expectativas próprias.

## Uso e documentos de tier 3

A execução oficial usa `poetry run trama-simulator`, após instalar o projeto.
O cenário padrão acompanha o pacote e o executável instalado funciona também
fora da raiz do repositório. A única entrada jogável é `trama-simulator`, também
disponível por `python -m trama.simulator`, com a mesma implementação.
`--situation ID` abre uma situação do catálogo compartilhado com os oito casos
live contextuais. A seleção é alternativa a `--scenario`; veja os identificadores
no [formato de cenários](carregamento-de-cenarios.md#situações-reproduzíveis).
Configuração de serviços, controles e formas de diagnóstico têm suas próprias
referências. Abertura, mensagens e reinício podem chamar a API real.

| Assunto | Referência de tier 3 |
| --- | --- |
| Fuga da dungeon: cenário e adjudicação | [fuga-da-dungeon](fuga-da-dungeon.md) |
| Executar e diagnosticar o simulador | [execucao](execucao.md) |
| Carregamento e formato de cenários | [carregamento-de-cenarios](carregamento-de-cenarios.md) |

O cenário jogável fica em `src/trama/scenarios/`; os mapas anteriores ficam em
`tests/fixtures/scenarios/` e podem ser abertos pelo mesmo comando com `--scenario`.
Análises parciais usam o módulo importável em `src/trama/analysis/` e ferramentas
em `tools/`; suas entradas e critérios ficam nas fixtures correspondentes.
Os detalhes gerais do motor permanecem nos índices relacionados.

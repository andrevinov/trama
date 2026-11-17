# Representação do Mundo

Tier 2 · [Visão geral do Trama](../../../README.md) ·
[Regras](../regras/README.md) · [Aplicação](../aplicacao/README.md)

Esta área representa o espaço e seus elementos: lugares, passagens, objetos,
criaturas posicionadas e condições de visibilidade. Ela fornece a base espacial
para a execução das ações e para aquilo que a interface e o personagem percebem.

## Responsabilidade e fronteiras

O mapa descreve arquitetura e obstáculos; a visão calcula o que pode ser visto
nas condições implementadas. Uma criatura posicionada tem identidade e presença
no espaço. Seu comportamento é decidido e executado em outras partes do sistema.

O Mundo como participante da narrativa é mais amplo que essa representação:
inclui decisões da IA, regras e respostas específicas da aventura. Este índice
trata de como seus elementos espaciais são modelados e consultados.

## Partes desta área

| Parte | O que representa ou calcula | Código de referência |
| --- | --- | --- |
| Grade e posições | Coordenadas, limites, terreno e relações espaciais básicas. | [spatial.py](../../../src/trama/spatial.py) |
| Lugares e passagens | Áreas nomeadas, conexões e estados de portas e grades. | [scene.py](../../../src/trama/scene.py) |
| Objetos | Posição, fixação e efeitos independentes sobre movimento e visão. | [scene.py](../../../src/trama/scene.py) |
| Criaturas posicionadas | Identificação e localização dos participantes no mapa. | [creatures.py](../../../src/trama/creatures.py) |
| Visão | Linha de visão, campo de visão e obscurecimento no recorte atual. | [vision.py](../../../src/trama/vision.py) |

As medidas usam metros. As coordenadas do domínio e dos arquivos de cenário
começam em zero; as colunas e linhas apresentadas ao jogador e à IA começam em
um. A aplicação produz as projeções apropriadas a cada consumidor.

## Relações com outras áreas

- As [Regras](../regras/README.md) usam a grade para calcular deslocamentos. A
  [Aplicação](../aplicacao/README.md) acrescenta ocupação, busca de caminhos,
  alcance e requisitos espaciais antes de aplicar as ações.
- O [Simulador](../simulador/README.md) fornece os dados de cenário e usa os
  construtores e validadores compartilhados para formar uma sessão.
- As [Interfaces](../interfaces/README.md) desenham projeções da partida;
  colisão, navegação e visão são calculadas antes da apresentação.
- A [IA](../ia/README.md) recebe informações selecionadas pela aplicação para
  cada papel. A arquitetura conhecida para navegação e o campo de visão atual
  são informações distintas.

Um objeto fixado à parede pode compartilhar uma casa de piso sem bloqueá-la.
Fixação, bloqueio de movimento e bloqueio de visão são propriedades separadas.
Planejamento de caminhos e execução devem consultar os mesmos obstáculos.

## Percepção e conhecimento

A visão filtra criaturas e elementos visíveis nas projeções do jogador. A sessão
também pode guardar itens conhecidos ou carregados que não estão no campo de
visão. A construção desses contextos pertence à aplicação.

Os personagens também têm [memórias contextualizadas](../aplicacao/conhecimento-dos-npcs.md):
uma localização lembrada ou relatada não é a posição oculta atual de um objeto.
Percepção e comunicação alimentam essas memórias pelas operações da aplicação.

O diretor do Mundo e o narrador podem receber estado completo para manter
coerência. Isso não autoriza revelar segredos: a narração deve respeitar os fatos
perceptíveis e as descobertas registradas. A avaliação dos textos pela
[Qualidade](../qualidade/README.md) complementa os filtros determinísticos.

## Alcance e detalhamento existente

O mapa atual é uma grade com lugares nomeados e objetos estáticos. A visão
implementa o observador normal e os obstáculos documentados. As tochas da dungeon
justificam sua iluminação; ainda não há propagação dinâmica de luz. Inventário
coletável e descobertas têm adjudicação específica no cenário.

| Assunto | Referência de tier 3 |
| --- | --- |
| Objetos, fixação e bloqueios | [objetos](objetos.md) |
| Mapas, áreas e passagens | [mapas-e-passagens](mapas-e-passagens.md) |
| Criaturas posicionadas e identificação | [criaturas](criaturas.md) |
| Visão, luz e percepção | [visao-e-percepcao](visao-e-percepcao.md) |

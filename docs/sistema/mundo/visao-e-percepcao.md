# Visão, luz e percepção

Tier 3 · [Mundo](README.md) · [Visão geral](../../../README.md)

## Portas, visão e guardas

Código: [vision.py](../../../src/trama/vision.py), [scene.py](../../../src/trama/scene.py).
O observador básico é um Humano de visão normal, sem visão no escuro.
`field_of_view` recebe grade, origem, casas opacas, luz fraca (`dim`) e
escuridão (`dark`). Devolve `Visibility.visible` e `lightly_obscured`.
Iluminação e opacidade precisam estar dentro do mapa; `dim` e `dark` não se sobrepõem.

O campo cobre 360 graus, sem orientação persistente ou distância artificial.
Luz fraca permite ver com obscurecimento leve. Casas escuras ficam fora da
visão desse observador e também bloqueiam a visão além delas no cálculo atual.
Criaturas não são tratadas como paredes opacas.

## Linha de visão e aproximação geométrica

`line_of_sight` amostra quatro cantos da origem e nove pontos do destino.
Uma linha livre entre amostras permite visão; tocar quina de obstáculo também
pode bloquear um raio. A superfície de um obstáculo pode ser vista sem revelar
as casas atrás dele. Essa amostragem é uma aproximação explícita da geometria.

`Scene.opaque` combina paredes, portas fechadas e objetos opacos. Grades são
transparentes mesmo fechadas; um objeto opaco na mesma casa continua bloqueando.
Fixação à parede não torna um objeto opaco: seus [efeitos](objetos.md) são explícitos.

## Percepção, conhecimento e narração

A aplicação usa a visão para produzir criaturas, objetos e lugares percebidos.
Conhecer um nome arquitetônico para navegação não significa enxergar seu interior.
Itens descobertos ou carregados podem ser conhecidos sem visão atual.

Testes de Percepção e audição pertencem à resolução de regras e às decisões
específicas do cenário. O algoritmo geométrico não rola testes, resolve furtividade
ou cria regras de ouvir através de paredes. A narração recebe uma projeção de
[percepção e contratos](../ia/contextos-e-contratos.md), além do estado
de mestre, e deve preservar os segredos.

## Referências e limites

PHB 2024, Vision and Light; DMG 2024, p. 45, Line of Sight. A dungeon usa
iluminação normal justificada por tochas; não há propagação dinâmica de luz,
combustível ou sentidos especiais implementados. Dizer que fica de frente para
uma sala é detalhe narrativo, sem alterar cone de visão ou orçamento.

## Verificação

[Tests unitários](../../../tests/unit) verificam geometria e iluminação; a
[interface](../../../tests/integration/test_movement_window.py) verifica os marcadores
filtrados. Consulte [contextos](../ia/contextos-e-contratos.md) para
os limites de informação e [mapas](mapas-e-passagens.md) para a arquitetura.

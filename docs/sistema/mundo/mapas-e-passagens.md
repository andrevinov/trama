# Mapas, áreas e passagens

Tier 3 · [Mundo](README.md) · [Visão geral](../../../README.md)

## Modelos e validação

Código: [spatial.py](../../../src/trama/spatial.py), [scene.py](../../../src/trama/scene.py).
`Position` contém inteiros `x/y`. `Grid` contém dimensões positivas, casas
bloqueadas e terreno difícil, sem sobreposição entre esses dois conjuntos.
Coordenadas internas começam em zero; a [apresentação em metros e base um](../regras/movimento.md#cenário-e-unidades)
é uma projeção da aplicação.

`Area` define lugar retangular, identidade, nome e descrição. `Passage` conecta
duas áreas por uma casa e contém tipo (`door` ou `gate`), aberto e trancado.
Uma passagem aberta não pode estar trancada. `Scene` exige ids únicos entre
áreas/passagens/objetos, áreas não sobrepostas dentro do mapa e passagem
adjacente às duas áreas conectadas.

`Passage.lock_checkable`, booleano com padrão `true`, declara se o mecanismo
simples permite conferir o trancamento sem abrir a passagem. `false` mantém o
resultado desconhecido nessa interação. É um recorte do Trama; veja
[inspeção de passagens](../aplicacao/inspecao-de-passagens.md).

## Construção e grades derivadas

`Scene.from_data` transforma as áreas em piso, acrescenta casas de passagens
abertas e considera o restante bloqueado. `Scene.grid` conserva terreno e
passagens; `movement_grid` acrescenta bloqueios dos [objetos](objetos.md).
A sessão usa essa grade de movimento e acrescenta sua política de ocupantes.

`open_passages_grid` permite prever rota arquitetônica por passagens,
preservando bloqueios de objetos. Essa previsão não abre portas de verdade.
A [execução](../aplicacao/movimento-contextual.md) para na barreira
real e não atravessa nem destranca automaticamente.

`with_passage` devolve uma cena com estado e bloqueio consistentes, mantendo
os efeitos dos objetos. O cálculo de opacidade é independente da passagem:
grade fechada impede movimento, mas permite ver; porta fechada é opaca.

## Destinos nomeados

`area_at` identifica a área da posição; uma casa de passagem pode não pertencer
a um cômodo. `destination_cells` fornece posições válidas para aproximar-se
por nome/id: entrar em área, parar junto de passagem ou alcançar objeto.
A busca de menor custo está em [routing.py](../../../src/trama/application/routing.py).

A casa livre de uma porta aberta pode ser ocupada. Uma criatura não pode
terminar o movimento em espaço ocupado só porque a conexão está aberta.
A [sessão](../aplicacao/sessoes-e-conversa.md) revalida essa condição.

## Formato e verificação

Os dados são carregados pela [entrada compartilhada de cenários](../simulador/carregamento-de-cenarios.md).
Referências: PHB 2024, movimento em grade; os nomes, dimensões e alcance
operacional das passagens são decisões dos cenários. As regressões em
[test_scenario_loading.py](../../../tests/integration/test_scenario_loading.py) e
[tests/unit](../../../tests/unit) verificam construção e restrições. Consulte também
[criaturas](criaturas.md) e [visão](visao-e-percepcao.md).

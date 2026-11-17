# Visão, luz e percepção

Tier 3 · [Mundo](README.md) · [Visão geral](../../../README.md)

## Capacidades de cada NPC

[`perception.py`](../../../src/trama/perception.py) define `Senses`, `Observer` e
`Noise`. Cada criatura tem sentidos próprios: visão habilitada, alcance visual
opcional, audição, alcance auditivo, visão no escuro, bônus de Percepção,
vantagem/desvantagem, sono, limiar de despertar e estado de busca deliberada.
O bônus padrão de um combatente vem de sua ficha; um perfil pode declará-lo
explicitamente. `Observer` representa NPCs sem ficha de classe ou turno de combate,
como o prisioneiro. Seus sentidos não exigem uma ficha fictícia de Guerreiro.

[`application/perception.py`](../../../src/trama/application/perception.py)
avalia essas capacidades usando o estado real. O cenário decide a resposta ao
acontecimento: conversar, investigar, pedir ajuda ou reconhecer um disfarce.
O prisioneiro acordar e o guarda ouvir uma voz não dependem de CDs ou distâncias
codificadas no roteiro da dungeon.

## Portas, luz e visão

Código: [vision.py](../../../src/trama/vision.py), [scene.py](../../../src/trama/scene.py).
O campo de visão do jogador continua sendo humano normal, sem visão no escuro.
`field_of_view` recebe grade, origem, casas opacas, luz fraca (`dim`) e
escuridão (`dark`); devolve `Visibility.visible` e `lightly_obscured`.
Iluminação e opacidade precisam estar dentro do mapa; `dim` e `dark` não se sobrepõem.

A visão cobre 360 graus, sem orientação persistente. NPCs podem ter limite visual
em metros; `null` é ausência de limite artificial dentro do mapa, não uma distância
universal de D&D. Visão no escuro permite ver casas escuras dentro de seu alcance.
Paredes e portas fechadas bloqueiam visão; grades são transparentes. Criaturas
não são paredes opacas. Fixação à parede não altera os [efeitos de um objeto](objetos.md).

`line_of_sight` amostra quatro cantos da origem e nove pontos do destino. Uma
linha livre entre amostras permite visão; tocar quina de obstáculo também pode
bloquear um raio. Ver a superfície não revela as casas atrás dela. Esta é uma
aproximação explícita da geometria, preservada no novo avaliador de NPCs.

## Audição e decisões explícitas do Trama

A tabela Audible Distance do DMG 2024 usa `2d6 × 5/10/50 pés`, conforme o ruído.
O Trama usa **7 como referência fixa de 2d6**, evitando sorteios repetidos para
alcance. O alcance normal configurável do observador recebe estes fatores:

| Emissão | Fator | Alcance humano padrão |
| --- | ---: | ---: |
| Discreta (`quiet`) | 0,5 | 10,5 m |
| Normal (`normal`) | 1 | 21 m |
| Alta (`loud`) | 5 | 105 m |

Para **fala normal com contato visual mútuo atual**, o Trama aplica margem de
50% ao alcance auditivo do ouvinte: **31,5 m** no humano padrão. É uma decisão
de condução solicitada pelo usuário, não outra regra de D&D. Vale para falas do
jogador e de NPCs, inclusive transmissão de informação e resposta social.
O estímulo marca `speech=true`; passos, portas e outros ruídos não recebem a
margem. Sussurros, gritos, despertar de adormecidos e capacidades auditivas
desabilitadas conservam seus limites. Ambos precisam enxergar-se pelas condições
atuais de visão, luz e alcance; percepção antiga não basta. O percurso acústico
continua limitado: paredes e portas não são ignoradas pelo contato de conversa.

São parâmetros de condução do Trama, não círculos auditivos universais impostos
pelo livro. Uma emissão fora do alcance não gera teste. O som segue um menor
caminho geométrico pelo espaço arquitetônico, contornando paredes; cada porta
fechada acrescenta **6 m de atenuação equivalente**. Grades não recebem esse
acréscimo. Sem percurso arquitetônico, não há audição. Ocupantes, terreno difícil
e objetos de mobília não fecham o ar da casa nesta aproximação.

No fluxo com IA, alcance indica possibilidade de ouvir. Portas no percurso
recebem [avaliação contextual](../aplicacao/avaliacao-de-dificuldade.md) por volume
e finalidade: perceber o som ou compreender palavras. O resultado pode exigir
Percepção passiva (10+bônus, ±5 por vantagem/desvantagem) ou impedir audição.
Não há penalidade universal automática para toda porta; descrições opcionais
de passagens fornecem fatos como espessura e frestas. A política é reutilizada
enquanto esses fatos persistirem. Despertar continua usando o limiar próprio
do adormecido; não recebe uma rolagem nova.

Não há simulação de decibéis, materiais, ecos ou escolha de rota de menor
atenuação entre várias rotas geométricas. A distância é de grade, com diagonais
legais de 1,5 m. Uma porta fechada pode impedir visão e permitir audição.

## Detecção, furtividade e busca

Visão desimpedida ou som evidente ao alcance produzem detecção sem dados. O
resultado distingue `heard` (som, sem posição conhecida), `located` (fonte
localizada) e `seen` (contato visual). O registro conserva conhecimento anterior;
`visible=false` diferencia lembrança de visão atual. Ouvir não identifica por si
só a aparência da fonte nem permite enxergar através da porta.

`hide` usa Destreza (Furtividade), CD 15, com condições para ocultação/cobertura
e ausência de visão inimiga. Cota de malha impõe desvantagem. Sucesso guarda o
total como CD de detecção; uma tentativa falha não cria ocultação. Em combate,
Hide consome a ação. Neste recorte `sneak` executa Hide se necessário e o mesmo
movimento até um destino conhecido; reutiliza a ocultação vigente. Não permite
movimentação silenciosa desacoplada de Hide em qualquer terreno aberto.

Para um estímulo discreto de uma criatura oculta, o motor compara o total de
Furtividade com a Percepção passiva de cada observador: `10 + bônus`, ajustado em
+5/−5 por vantagem/desvantagem, que se cancelam. Usar passiva para atenção
rotineira é a condução adotada pelo Trama; as regras deixam seu uso ao mestre.
A exposição visual evidente encerra a ocultação: Hide não é tratado como magia
de invisibilidade ao atravessar um espaço aberto diante do adversário.

Uma busca deliberada usa `WorldAction(search, target_id='player')`: rola
Sabedoria (Percepção) contra o total **real** de Furtividade, com sentidos e
recursos atuais. A busca pode localizar por som sem ver. Search em combate usa a
ação do NPC; um observador sem ficha não ganha turno de combate. A mesma busca
falha não é rerrolada gratuitamente: nova posição, porta, emissão relevante,
ocultação ou turno pode alterar a situação. Passos por si sós não disparam
rolagens ativas. `searching=true` informa ao Mundo uma intenção deliberada de
busca, que ele pode propor após a ação do jogador; não é uma rolagem automática.

O campo legado `WorldReaction.check` permanece para contratos anteriores.
Ele delega à mesma busca: presença evidente é automática, impossibilidade sensorial
não rola dados, e ocultação usa a CD real, sem aceitar a CD proposta como substituta.
Os novos fluxos de presença usam o motor e `search`.

## Sono, acontecimentos e respostas

Um NPC dormindo não faz Search nem usa percepção visual normal. O despertar
por som usa sua audição e `wake_range_meters`, padrão 9 m para emissão normal,
com os mesmos fatores e obstáculos. Esse limiar é uma decisão explícita do
Trama, não um teste de Percepção de uma criatura inconsciente. Sons discretos
podem não alcançá-lo; som alto, chamada deliberada ou contato físico podem acordá-lo.

O motor reavalia após cada passo real, fala e alteração de porta; `look` consulta
a situação atual sem conceder Search. `speak/challenge` têm volume estruturado;
o Python não extrai intensidade por palavras do texto. Emissão normal/alta do
jogador encerra Hide; uma passagem operada enquanto oculto usa volume discreto.

`on_perception` recebe os acontecimentos já validados. Na dungeon, um pedido de
ajuda audível pode levar o guarda a investigar; despertar durante a libertação
permite um agradecimento discreto. O som da ilusão passa pela mesma audição antes
de Study/distração. Esses comportamentos de resposta pertencem ao cenário. A
[abordagem e conversa](../aplicacao/conversa-antes-do-combate.md) e a preservação
do ponto de detecção continuam sendo regras comuns. NPCs comuns podem apenas
observar; o perfil `response=challenge` oferece uma abordagem visual a combatentes.
Observadores sem ficha têm respostas de cenário/Mundo, sem esse contrato social.

## Contextos, referências e verificação

`world.perception` publica perfis, estado de sono, ocultação, conhecimento e última
busca; `world.lighting` descreve a iluminação. A interpretação recebe apenas
`sensing` (ocultação própria e possibilidade de Hide), além da percepção já
filtrada. Informação interna do NPC não se torna conhecimento do jogador.
Narração e perguntas off seguem os [contratos de contexto](../ia/contextos-e-contratos.md).
Reiniciar restaura sentidos/posições iniciais e remove detecções, sono interrompido,
ocultação e buscas. A versão dos estímulos evita tentativas repetidas sem mudança.

Referências: PHB 2024, [Hide, Search, Passive Perception e Unconscious](https://www.dndbeyond.com/sources/dnd/br-2024/rules-glossary),
[armaduras](https://www.dndbeyond.com/sources/dnd/br-2024/equipment), DMG 2024,
[Perception and Encounters / Audible Distance](https://roll20.net/compendium/dnd5e/Rules:Running%20Exploration?expansion=33359),
e p. 45, Line of Sight. Alcances fixos, atenuação, despertar, cobertura discretizada
e exposição evidente acima são decisões/simplificações declaradas do Trama.

`tests/unit/test_perception_rules.py` e `tests/integration/test_perception.py`
verificam contratos, geometria, bônus, passiva, busca, orçamento, sono e reinício.
Os [13 casos live](../qualidade/percepcao-live.md) reutilizam situações e o runner
oficial. Não implementam todos os sentidos especiais, esconder objetos, detecção
recíproca de NPCs ocultos ou um motor geral de condições. Audição é por emissão;
percepção visual deste incremento avalia os NPCs em relação ao jogador.

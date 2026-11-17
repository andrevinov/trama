# Conversa antes do combate

Tier 3 · [Aplicação](README.md) · [Visão geral](../../../README.md)

## Objetivo e decisão de condução

Uma abordagem verbal pode interromper a exploração sem iniciar combate. O NPC
exige uma resposta no ponto em que percebe o personagem; o jogador pode conversar
ou escolher lutar. Esta condução foi solicitada pelo usuário em 16/11/2026 e vale
para o Trama, independentemente de cenário. Ouvir, reconhecer alguém, conversar e
atacar são acontecimentos distintos. A audição usa a [capacidade sensorial de cada NPC](../mundo/visao-e-percepcao.md);
o cenário decide sua reação ao som percebido.

As referências de D&D 2024 são [Influence](https://www.dndbeyond.com/sources/dnd/br-2024/rules-glossary#InfluenceAction)
e [iniciativa e turnos](https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game#Combat).
A oportunidade de responder e a escalada de uma recusa/falha nesta abordagem são
**decisões do Trama**: as regras de Influence não determinam que toda falha social
cause combate, nem que todo encontro precise começar com conversa.

## Estado e execução compartilhados

`GameSession.offer_parley` registra NPC, exigência, posições do jogador e do NPC
em base 1 na projeção, e `status=pending`. Continua em `narrated`, sem iniciativa,
consumo de ação ou ataque. `WorldAction(parley)` oferece essa mesma operação aos
adaptadores; seu texto é a fala audível. Ela interrompe o restante do plano,
inclusive aproximações e ataques propostos na mesma resposta.

`TravelExecutor` examina a origem e cada passo do deslocamento narrado de NPCs.
Ao detectar o jogador, um NPC que vai interpelá-lo para ali; o restante do caminho
não é aplicado. A execução geral de abertura de porta por NPC também examina a
nova visibilidade antes de continuar. A dungeon usa o mesmo executor na sua
investigação/rotina e examina a porta antes de avançar pelo corredor. Disfarce,
distração e a justificativa do encontro continuam sendo julgados pelo Mundo ou
pelo cenário; não são reinventados pela geometria.

Com conversa pendente, o NPC aguarda e operações físicas do jogador são impedidas
até uma resposta ou decisão de combate. Olhar, falar e perguntar em off não movem
ninguém. Uma pergunta simples em jogo pode receber resposta sem resolver a
abordagem. Uma pergunta exclusivamente off não consulta o Mundo, não rola dados e
não avança rotinas. O fluxo termina a interação normalmente e recebe a próxima
mensagem pelo mesmo runner/janela; não há entrada de simulador alternativa.

## Julgamento e Influence

O interpretador traduz a fala em `speak` ou `challenge`. O Mundo julga o pedido,
sem decidir o resultado dos dados, por `WorldAction(influence)` após essa fala
(`after_squares=null`). O executor recusa esse julgamento antes da fala ou numa
etapa sem comunicação ou cuja fala não foi ouvida pelo NPC. O pedido contém
[avaliação de alinhamento, persona e memórias](disposicao-social.md), perícia,
atitude e concessão delimitada. O código calcula a disposição:

| Disposição | Resolução |
| --- | --- |
| `willing` | Aceitação sem teste. |
| `unwilling` | Recusa sem teste; mantém a abordagem, sem iniciativa automática. |
| `hesitant` | Python rola a perícia pertinente: Persuasão, Enganação, Intimidação ou Atuação. |

Na hesitação, a CD é o maior entre 15 e a Inteligência do NPC, conforme o padrão
de Influence de 2024. Atitude Friendly dá vantagem; Hostile dá desvantagem;
Indifferent não modifica. O booleano `Creature.hostile` identifica adversários de
combate e não determina sozinho a atitude social. A IA deve justificar seu
julgamento a partir da conversa e dos fatos, sem inferir sucesso da intenção.
Não há gasto automático de Inspiração ou Mente Tática.

Aceitar ouvir registra `listening` e conserva custódia e posições. Recusa/falha
mantém `pending`, sem combate por si só. O código escolhe a fala condicional
correspondente ao resultado; não concede liberdade por uma simples escuta.
O mesmo pedido reutiliza o resultado, salvo informação nova relevante à persona.
Isso não altera ficha/facção nem proíbe iniciativa por uma ação hostil posterior.

Um ataque declarado pelo jogador segue o fluxo existente de iniciativa antes da
aproximação contextual. O jogador pode abrir mão da conversa. Resistência ou fuga
explícita também pode justificar `start_conflict` pelo Mundo antes da caminhada.
O NPC que vencer só recebe movimento, ação e recursos normais de seu turno.

## Limites e validação

Este incremento mantém uma conversa pendente por vez, com um NPC interlocutor.
Não implementa negociação entre grupos, reputação, relógio social, idiomas,
Influence de animais, captura, concessões de inventário ou um catálogo geral de
acordos. O resultado executável coberto é escuta limitada; não concede efeitos
materiais só porque uma fala os pediu. Alinhamento, interesses e memórias
informam a disposição segundo a política numérica explícita do Trama.

Reiniciar remove a abordagem e acordos locais; perguntas off e falhas de narração
preservam o estado. Os contextos das seis fases incluem `parley`, nulo quando não
há registro. Eventos `game.parley_started` e `game.influence_resolved` preservam
posições, disposição, perícia, CD, dados, resultado e concessão quando aplicável.

`tests/integration/test_parley.py` testa a regra numa sessão genérica, sem dungeon,
com dados controlados. A regressão da dungeon verifica a parada junto à porta.
`test_parley_live_scenarios.py` valida preparações e critérios pelo runner real,
inclusive a rejeição da posição do bug original. Os [quatro live tests](../qualidade/conversa-live.md)
avaliam interpretação, Mundo e narração reais; sua criação e coleta não constituem
uma execução de modelo nem garantem sua redação.

# Disposição social dos NPCs

Tier 3 · [Aplicação](README.md) · [Conversa antes do combate](conversa-antes-do-combate.md)

## Regra de referência e decisão do Trama

O PHB 2024 descreve os nove [alinhamentos](https://www.dndbeyond.com/sources/dnd/br-2024/creating-a-character#Step4ChooseanAlignment)
pelos eixos ordem/autonomia e cuidado/exploração. São tendências de conduta;
indivíduos variam. Leal não significa obedecer a qualquer autoridade; mau não
significa necessariamente sádico. Criaturas sem capacidade de escolhas morais
podem ser sem alinhamento. O recorte implementa os valores de perfil, não regras
de idiomas, moralidade de animais, mudança de alinhamento ou efeitos mágicos.

[Influence](https://www.dndbeyond.com/sources/dnd/br-2024/rules-glossary#InfluenceAction)
dispensa dado para disposto/indisposto; hesitante resolve teste apropriado de
Carisma, CD maior entre 15 e INT. Friendly dá vantagem, Hostile desvantagem.
Fracasso não determina violência. Goals/fears podem informar as respostas na
[interação social](https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game#SocialInteraction).

**A soma, os pesos, os limites e a reavaliação abaixo são política do Trama,
solicitada pelo usuário em 17/11/2026; não são uma fórmula oficial de D&D.**

## Perfil e avaliação por pedido

Cada NPC aceita `social` nos dados de cenário: `alignment` e `persona`, com nome,
papel, história curta e até oito interesses. Cada interesse contém `id`, descrição,
peso de 1 a 4 e âncoras opcionais `evidence_topics`/`evidence_predicates`. Ausência
de perfil usa neutralidade e interesse genérico em integridade; é um padrão de
compatibilidade, não uma caracterização deduzida do cenário.

O guarda padrão da dungeon é neutro e mau e costuma aceitar propinas: ganho
financeiro (peso 4), aparência de cumprimento do dever (1), salário e família
(2), integridade e proteção contra represálias (2). A suspeita de filiação nobre
continua sendo uma memória incerta. A persona não confirma essa suspeita.
As situações reproduzíveis conservam seus perfis próprios, incluindo o guarda
profissional, o corrupto e o sádico, para avaliar comportamentos distintos.

O Mundo propõe um `assessment` estruturado dentro de `influence`, após fala
efetivamente ouvida pelo interlocutor. Ele identifica pedido, alvo, condições e
impactos sem escolher pesos, disposição final ou resultado do dado:

| Componente | Cálculo determinístico |
| --- | --- |
| Alinhamento | Produto dos dois eixos do NPC pelos dois eixos do pedido; cada eixo vale -1, 0 ou +1. Soma entre -2 e +2. |
| Persona | Cada interesse avaliado exatamente uma vez: favorece +1, ameaça -1, indiferente 0, multiplicado pelo peso cadastrado. Soma limitada a ±6. |
| Memórias | Até seis vínculos de crenças próprias a interesses com âncora pertinente. Agrupados por Claim exata: observação/hábito pesa 2; relato/inferência pesa 1. Soma final limitada a ±3. |

Total ≥3: disposto (`willing`); ≤-3: indisposto (`unwilling`); demais: hesitante
(`hesitant`). No último caso, o código executa Influence. Informação relatada
pode afetar a cautela sem ser tomada como verdade; não há confirmação de identidade
nem teste automático de Enganação só porque o jogador declarou um fato.

Um fato pode ter consequências para vários interesses: parentesco nobre pode
afetar tanto segurança quanto emprego. O pedido mantém uma entrada por par
`Claim/interest_id`; o cálculo agrupa todas as entradas da mesma Claim. Soma
seus efeitos e limita o resultado a -1/0/+1 antes de aplicar o peso da fonte.
Dois vínculos positivos de um relato valem **+1**, não +2; +1 e -1 se compensam.
O relatório publica uma contribuição por fato em `memory_effects`, com todos os
vínculos e justificativas em `impacts`. Duplicar o mesmo par ainda é erro, com
diagnóstico específico. Esta compensação é política do Trama, não regra de D&D.
No guarda da dungeon, o interesse em conservar o emprego aceita parentesco como
âncora, em razão do medo já registrado de represálias de um nobre.

O diretor classifica efeitos semânticos e explica cada um. O código exige ids,
fontes e pesos válidos, mas não prova a correção de todas as interpretações.
Por exemplo, ouvir mantendo custódia não deve ser classificado como abandonar
o emprego. Os live tests avaliam casos claros dessa interpretação.

## Resposta e nova informação

`accepted_reply` e `refused_reply` são propostas condicionais na mesma chamada.
O código escolhe exclusivamente a correspondente ao resultado e emite a fala
real. Não é necessária outra chamada de IA para o NPC conhecer o resultado.
Recusa deixa `parley.pending`; aceitação de escuta registra `parley.listening`
com concessão e limites. Ambos aguardam a próxima decisão do jogador.

Aceitar ouvir não torna o guarda um aliado, não remove custódia, não autoriza
movimento, não entrega chave e não abre portas. Pedido impossível não recebe
sucesso só porque saiu um número alto. Uma decisão explícita de violência ou
fuga segue o fluxo de iniciativa existente, separada do resultado social.

A primeira avaliação é obrigatória. A chave de reutilização combina NPC, tipo de
pedido e alvo; em `listen` o interlocutor é o jogador, independentemente de o
modelo referenciar o ouvinte ou o falante. Reformular, trocar perícia ou repetir
informação não muda a decisão nem permite outra rolagem. Nova crença própria,
citada com impacto não nulo e vínculo válido a um interesse, permite reavaliar.
O registro de fatos conhecidos evita que uma memória antiga, ignorada no primeiro
pedido, seja apresentada como informação nova depois.

Cor da roupa sem vínculo com os interesses não reabre negociação. Promessa nova
de ouro importa a interesse financeiro; alegação de nobreza importa a quem teme
represálias. Fontes e Claims exatas são preservadas; equivalência semântica entre
alegações arbitrárias ainda depende da classificação da IA, não há deduplicação
geral de paráfrases de fatos. Não implementamos o relógio de 24 horas de Influence:
o mesmo pedido sem mudança relevante reutiliza o resultado durante a sessão.

## Estado, contexto e limites

`social.py` contém tipos e cálculo puro. `application/disposition.py` mantém
decisões por sessão, fontes e reutilização. O carregador aplica perfis também
a observadores; reinício limpa decisões e restaura perfis. Ainda há somente uma
abordagem ativa, sem reputação coletiva ou persistência entre partidas.

`world.social` entrega perfis dos NPCs selecionados e até oito decisões ao Mundo.
O narrador não recebe esses perfis nem os fundamentos privados no relatório
atual/anterior: recebe a fala escolhida e o resultado público. Logs e fotografias
de diagnóstico preservam a avaliação completa para auditoria.

O esquema distingue `listen`, `release`, `access` e `information` para avaliar
pedidos diferentes. O incremento cobre concessão executável de **escuta** e
registro de condições; não introduz executor genérico de acordos físicos.
Aceitar outra categoria não transfere dinheiro, liberdade, portas ou objetos;
seus efeitos precisam das operações validadas existentes. Os live tests avaliam
somente a escuta, sem prometer cobertura dessas concessões futuras.

Os testes novos são `test_social_disposition.py`, `test_social_judgment.py` e
`test_social_live_scenarios.py`; a [bateria live](../qualidade/disposicao-live.md)
inclui sete perfis/situações e critérios independentes.

A [bateria de vínculos de memória](../qualidade/vinculos-memoria-live.md) acrescenta
três regressões da negociação com o guarda, incluindo a frase real rejeitada.

## Avaliação de opções

O cálculo dos fatores é compartilhado com as
[opiniões por opção e por termo](opinioes-por-opcao.md). Elas avaliam propostas
percebidas, alternativas privadas e expectativas sem acordo, com compensação
entre termos e sem resolver Influence. O cache e as concessões por pedido
continuam seguindo o contrato acima.

As [relações iniciais](relacoes-iniciais.md) acrescentam R somente às avaliações
de opções e ao contexto individual de decisão. Não alteram a fórmula, CDs ou
reutilização de pedidos Influence descritos acima. Memórias resumidas por uma
relação aplicada não pontuam outra vez no mesmo aspecto da opção.

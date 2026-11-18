# Comunicação por gestos

Tier 3 · [Aplicação](README.md) · [Visão geral](../../../README.md)

## Intenção e recepção

`GestureIntent` (`gesture`) é uma operação geral: destinatário conhecido em
`target_id`, movimento observável em `text`, intenção privada em `message` e
`subtle` para piscadela ou sinal discreto. Não usa uma lista de verbos no Python:
o interpretador identifica a intenção, incluindo sinais, acenos, mímica e
assentimentos dirigidos a alguém. Postura sem comunicação continua detalhe.

O motor não aproxima o personagem nem converte o gesto em fala. Valida a visão
do **destinatário**: paredes, portas, iluminação, alcance, cegueira e sono.
Sem contato visual, retorna `gesture_not_visible` com motivo concreto, sem
recepção, resposta ao gesto ou outros efeitos. Uma fala anterior no mesmo plano
continua realizada; o impedimento visual não a desfaz.

`communication_targets` contém identidades vistas/ouvidas pelo jogador, incluindo
conhecidas fora de visão, sem revelar suas posições ocultas. Assim, o interpretador
pode propor um sinal ao prisioneiro conhecido e o motor explicar por que não chega,
em vez de simplesmente apagá-lo do plano.

## Sinais claros e sutis

As [regras de 2024](https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game)
permitem comunicação por manifestações breves e gestos durante o turno.
Comunicação prolongada ou persuasão pode exigir ação. O Trama implementa aqui
gestos breves, sem custo de ação, interação ou movimento; não exige teste para
todo aceno. Um apelo ao interlocutor de uma abordagem pode usar o Influence já
existente, com sua disposição, CD e rolagem reais.

Decisão explícita de mestre do Trama: sinal claro é notado por quem enxerga o
emissor. Para gestos sutis, a decisão do Mundo já existente recebe um pedido
`visual_signal`, com movimento exterior, distância, luz e sentidos de cada
observador capaz de ver. Nenhuma chamada separada é criada para dificuldade.
O Mundo escolhe automático, impossível ou CD contextual; o motor compara a CD
com **Percepção passiva**, com os ajustes de vantagem/desvantagem e luz fraca.
Não há nova rolagem de Hide nem Search gratuito. Sem IA, a preparação usa CD15
como recorte declarado; isso não é uma CD universal de D&D para piscadelas.

Isso avalia **notar** o movimento. Ver uma piscadela não equivale a compreender
uma mensagem complexa, aceitar um pedido ou deixar de notá-lo como testemunha.
`subtle=true` não garante segredo. Não há língua de sinais, código previamente
combinado nem sistema geral de dissimulação gestual neste incremento.

## Registro e resposta do NPC

O evento contém `received`, `seen_by`, `heard_by=[]`, `understood=null` e o
movimento visível. Não emite ruído. A intenção privada não entra na memória ou
nas observações individuais dos NPCs. O destinatário pode inferir algo a partir
do gesto e do que realmente ouviu antes; não lê a intenção do jogador.
O gesto pode expor um personagem oculto à visão real de NPCs.

O Mundo pode responder depois da etapa, com fala ou espera fundamentada.
Se omitir a decisão sobre o destinatário que recebeu o gesto, o fluxo agenda
uma resposta pontual em `npc_agency`, mesmo sem abordagem ativa ou ficha de
Guerreiro. Essa intenção `one_shot` encerra após a decisão, sem iniciar uma
rotina permanente do NPC. Uma resposta já executada na etapa não é repetida.
O contexto individual só contém observações e conhecimentos próprios.

Compreensão e cooperação continuam decisões do NPC: ele pode pedir explicação,
recusar, falar ou escolher o silêncio. Não confirma como verdadeiro um relato
que desconhece nem recebe movimento, ataque, itens ou abertura de grade gratuitos.

## Verificação e limites

As regressões em `tests/integration/test_gestural_communication.py` cobrem a
geometria original, sentidos, luz, passiva, custos, fontes de conhecimento,
respostas e omissões do Mundo. Os [quatro live tests](../qualidade/gestos-live.md)
usam o runner oficial, com preparação e critérios independentes.

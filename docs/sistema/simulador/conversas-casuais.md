# Conversas casuais

Tier 3 · [Simulador](README.md) · [Intenções dos NPCs](../aplicacao/intencoes-dos-npcs.md)

O passo 8 exercita a conversa fora do conselho militar, com o mesmo carregador,
`GameFlow`, diretor, regras e janela. Os cenários são dados; não há decisão
específica por nome de NPC, frase certa ou árvore de diálogo.

## Abrir e reiniciar

Na raiz do projeto, com ambiente instalado e os serviços configurados como no
[simulador oficial](execucao.md):

```bash
poetry run trama-simulator --situation conversa-com-amiga --debug
poetry run trama-simulator --situation encontro-com-garoto --debug
```

Cada situação prepara somente um cumprimento falado pelo jogador, efetivamente
ouvido pelo interlocutor. Isso estabelece participação antes da abertura, sem
escolher a resposta do NPC, sentimentos do jogador ou um assunto obrigatório.
A abertura continua sendo narração; uma ação em jogo, inclusive aguardar, dá
ocasião à iniciativa do interlocutor. Off não faz a conversa avançar.

Reiniciar usa a mesma preparação, restaura posições, níveis e memórias iniciais
e descarta objetivos da conversa anterior. As situações têm sequência de dados
vazia: o fluxo casual esperado não exige testes. Uma operação que demande dados
fora desse recorte pode ser recusada pelo roteiro de rolagens.

Os arquivos `friendly_conversation.json` e `street_boy_conversation.json`, em
`src/trama/scenarios/`, também podem ser carregados por `--scenario`. Nesse caso
não há o cumprimento preparado pelo catálogo; inicie o contato com uma fala ao
NPC. A dungeon e o conselho continuam disponíveis pelos comandos anteriores.

## Lia, uma amiga

Lia está no jardim da vizinhança. O cenário declara uma história anterior de
amizade e relações iniciais de confiança 2 e afeto 3. O passo 9 registra essa
amizade como vínculo qualitativo com fontes de cuidado anterior, sem atração ou
sentimentos impostos ao jogador. Lia e o jogador são adultos declarados nesse
cenário. Os [critérios próprios dos vínculos](../aplicacao/vinculos-afetivos.md)
não convertem amizade ou pontuação alta em romance.

Sua persona valoriza companhia, autonomia e seus próprios limites. Pode ouvir,
perguntar, aconselhar quando houver abertura ou encerrar. Não existe uma resposta
obrigatória ao relato. O papel da IA continua sendo escolher uma interpretação
e iniciativa coerentes, usando o conhecimento próprio do NPC.

Comece com “só precisava contar isso a alguém”. Continue contando algo sem pedir
uma solução; depois, se desejar, peça uma ideia e encerre. Confira se a escuta
continua possível sem criar proposta, contrapartida, aceitação ou Influence.
Um acolhimento falado seguido de espera é permitido. Ouvir não exige que a IA
invente uma emoção, diagnóstico ou necessidade que o jogador não declarou.

Nova fala dirigida ou continuação da conversa a dois pode renovar a escuta, mesmo
sem pergunta formal anterior. Isso não renova uma espera por pergunta, pedido ou
objeção explícita ainda ignorada. Off, conversa com terceiros e apenas aguardar
não restauram a permissão de esperar. Não há espera renovada por frame.

Foco pode surgir e mudar com trechos das falas. O objetivo privado do NPC pode
mudar de escutar para sugerir algo, ou se esgotar. Ao encerrar, o acompanhamento
termina; foco e objetivo anteriores ficam como história, sem obrigação ativa.
Outro cumprimento pode iniciar uma nova conversa com objetivo próprio.

## Davi, um garoto da rua

Davi está na praça pequena. A moeda de cobre foi entregue **antes da abertura**,
por episódio inicial declarado em sua memória, sem serviço ou dívida combinados.
Não foi acrescentada operação de dar moeda ou motor de economia. Falar, agradecer
ou encerrar não transfere valor nem altera um saldo atual.

A confiança e o afeto iniciais são 1 e 1, com fonte nesse gesto anterior. O episódio
já está incorporado na relação: agradecê-lo não concede outro bônus. Davi conhece
o caminho do poço pela alameda norte, informação que pode compartilhar por fala
como memória própria. O poço fica além do trecho do mapa; dizer o caminho não
move o jogador até ele.

Após abrir a situação, experimente aguardar. O garoto pode agradecer e seguir
seus afazeres, sem pedido explícito de cada iniciativa. Em outra execução, diga
que está procurando o poço, sem pedir uma negociação: ele pode oferecer a
orientação conhecida. Isso não o obriga a acompanhar o jogador ou aceitar ordens.

Se decidir sair, a iniciativa `leave` usa despedida com encerramento e depois
`move` para um destino livre visto em outra área. A posição muda pelo executor
real, respeitando geometria e ocupação. Davi continua no mapa na alameda; não
desaparece nem é teleportado. Se a movimentação falhar, só o trecho efetivamente
executado pode ser narrado. Encerrar por `close` continua sendo possível sem sair.

Para usar o deslocamento existente, Davi tem ficha mecânica mínima de nível 1,
sem armas e não hostil. É simplificação do cenário, não regra etária ou bloco de
estatísticas oficial de D&D. Lia usa o papel de observadora sem ficha e pode
encerrar por fala, mas não recebe movimento de Guerreiro.

## Contexto, efeitos e limites

Participação é registrada a partir da comunicação executada, inclusive durante
a preparação compartilhada das situações. O coordenador continua responsável
por oferecer oportunidades e agendar decisões; registrar participação não faz
chamada à IA ou executa iniciativa silenciosamente.

A memória selecionada para o NPC considera seu objetivo, local atual e até três
comunicações recentes realmente compreendidas. Palavras inaudíveis e consultas
off não entram na busca. Os limites de seleção por dono continuam seis memórias
e 3.500 caracteres. Relações, planos e motivos privados não são copiados para a
narração ou o conhecimento do interlocutor.

`observations.departure_targets` publica no contexto privado até oito destinos:
um ponto livre e visto por outra área. A validação recalcula essa lista antes da
execução. Sem destino ofertado, sem ficha ou sob abordagem/custódia pendente, a
saída física não é liberada. Não há ataques gratuitos, acompanhamento automático,
transferência de moedas ou cura por palavras.

## Critérios de avaliação

As regressões offline usam as situações e a composição/runner reais, com decisões
fixas. Conferem escuta consecutiva, acolhimento seguido de espera, pergunta
ignorada sem renovação, conselho com abertura, mudança de foco/objetivo,
encerramento e novo encontro. Também verificam orientação compartilhada, saída
com posição/distância reais, rejeição de deslocamento inválido antes da despedida,
privacidade, off, reinício, ausência de dados, propostas e pontuação por falas.

As frases e escolhas fixas ficam em `tests/fixtures/casual_conversations.json`;
os fluxos em `tests/integration/test_casual_conversations.py`. Os contratos de IA
incluem amostras dessas situações. Isso valida efeitos e limites para as escolhas
fornecidas, sem comprovar a qualidade ou repetibilidade de um modelo real.

Na avaliação manual, registre o que foi dito, o que o NPC percebeu, a iniciativa
escolhida e o efeito executado. Compare escuta com conselho imposto, orientação
espontânea com obrigação de serviço, e despedida falada com deslocamento real.
Consulte `agency.choice_validated`, `agency.intent_updated` e
`world.action_completed` nos logs, preservando as evidências de cada execução.

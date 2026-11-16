# Janela Pygame e entrada do jogador

Tier 3 · [Interfaces](README.md) · [Visão geral](../../../README.md)

## Integração com a janela

`MovementWindow` cria um `GameFlow` com a sessão e os adaptadores recebidos pelo
simulador. Abertura, envio de texto, escolha de oportunidade e reinício delegam,
respectivamente, a `start`, `submit`, `choose_opportunity` e `reset` do fluxo.
Sessão, conversa, relatório, etapa, pendência e erro são projeções de leitura
desse mesmo objeto, sem cópias mutáveis na janela.

A UI agenda cada `pending_request.id` uma vez em uma thread. O worker executa
apenas `request.run()` e coloca `(id, resultado)` na fila. `poll`, na thread
principal, entrega esse par a `flow.receive` e agenda o próximo pedido que o
próprio fluxo produzir. Não inspeciona o tipo de plano para decidir a sequência,
não constrói contextos e não executa ações ou turnos por conta própria.

A identificação continua válida quando há resultados duplicados ou atrasados:
o fluxo ignora o que já não corresponde ao pedido atual. Uma falha ao criar o
worker também é entregue ao fluxo, evitando deixar a janela pendente sem uma
thread que possa responder. Os botões de envio/reinício permanecem bloqueados
durante chamadas, enquanto navegação das abas e consultas da ficha continuam
disponíveis. Entrada inválida mantém o texto para edição; resposta ou falha
reposiciona a conversa para mostrar o retorno.

Reiniciar restaura o estado pelo fluxo e limpa o estado visual da ficha e da
rolagem. Resultados já em trânsito não substituem a abertura da nova partida.
A apresentação continua consultando mapa, visão, ficha e inimigos pelas APIs
de leitura existentes. O comando para executar o simulador não mudou.

Os eventos de entrada permanecem em `ui.*`; decisão de próxima etapa e falhas
de processamento/provedor ficam em `game_flow.*`. A correlação acompanha os
pedidos externos e a execução local, sem gerar logs a cada frame.

`tests/integration/test_window_game_flow.py` verifica delegação pela UI real,
despacho único, threads, reset e respostas antigas, falha de agendamento e
conversa off durante oportunidade. Compara também relatórios e contextos do
caminho da janela com a entrada direta do fluxo, ignorando apenas o id aleatório
da execução e mantendo expectativas independentes de posição. Os testes
anteriores de desenho, turnos, erros e ficha continuam como regressões; planos
não são mais injetados na fila da janela para contornar a entrada do jogador.

## Controles

- **Enter** ou **Enviar**: enviar a mensagem; **Shift+Enter**: nova linha.
- **Roda do mouse / PgUp / PgDn**: percorrer a conversa, sem truncar mensagens.
  Sobre a ficha, a roda percorre o conteúdo da ficha.
- **Jogo / Ficha / Inimigos**: alternar o painel esquerdo. A conversa permanece
  visível; é possível consultar as guias enquanto uma resposta está pendente.
- Na **Ficha**, **Agora / Recursos / Dados** selecionam a seção; clique no
  cabeçalho de um cartão para abrir ou fechar os detalhes. Esses cliques só consultam.
- Ao surgir uma oportunidade do personagem, **Atacar (reação)** ou **Deixar
  passar** decide a resposta e retoma o movimento do NPC. Os botões aparecem no
  painel de turno; não é necessário enviar outro pedido à IA para essa escolha.
- Setas, Home, End, Backspace e Delete editam o texto. Ctrl+A seleciona tudo;
  Ctrl+V cola, preservando novas linhas. Limite: **2000 caracteres**.
- A exploração começa no **modo narrado**, sem limite por turno. Não há botões
  de iniciar combate ou novo turno. Um confronto entra naturalmente no **modo
  por turnos**; `Encerro meu turno` passa a vez e a IA resolve os guardas.
- Em combate, `fico parado`, `não faço nada` ou `aguardo`, como declaração de
  passar a vez sem outra ação, também encerram o turno. Na exploração são espera
  narrativa. Permanecer parado durante outra ação não a encerra antecipadamente.
- **Reiniciar** restaura posição, passagens, fichas, recursos e conversa, e solicita outra
  descrição inicial ao narrador. **Esc** fecha a janela.
- Durante uma chamada, envio, edição e mudanças de turno aguardam a resposta;
  desenho, fechamento e rolagem da conversa continuam funcionando.

# Situações congeladas de movimento contextual

`cases.json` contém somente frases do jogador, estágio inicial, sequência de
dados e critério de resultado dos oito casos. Não contém instruções de sistema,
esquemas de resposta, respostas simuladas de IA ou regras alternativas.

O construtor em `tests/live/test_contextual_movement.py` carrega a mesma dungeon
usada pelo simulador e usa suas operações reais para preparar as posições,
descobertas, inventário e disfarce. O início de combate, o saldo de 1,5 m e o
estado do banheiro são precondições congeladas de casos específicos. As CDs e
os resultados continuam sendo calculados pela aplicação.

`investigation_history.json` preserva as mensagens reais anteriores à falha de
16/11/2026. Sua origem está identificada no próprio arquivo. Esse histórico é
repassado pelos construtores de contexto da aplicação, sem um prompt de sistema
especial para o teste. O pedido atual é acrescentado por `Conversation.prepare`.

As rolagens fixam tipo e valor de cada dado. Uma rolagem extra ou de tipo errado
falha explicitamente: não se deve trocar os valores para acomodar uma ação que
a IA acrescentou sem pedido. Nenhuma sequência de respostas da IA é fornecida
aos testes live.

A checagem local em `tests/integration/test_contextual_live_scenarios.py` verifica
se os estados podem ser preparados e se os critérios detectam a falha original.
Ela verifica o aparato de teste; não substitui a execução dos oito testes live.

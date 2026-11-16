# Interpretação da intenção do jogador

Tier 3 · [IA](README.md) · [Visão geral](../../../README.md)

## Entrada, saída e responsável

Código: [openai_intent_interpreter.py](../../../src/trama/infrastructure/openai_intent_interpreter.py).
O interpretador recebe somente o pedido on atual e a projeção de
[contexto de interpretação](contextos-e-contratos.md). Essa projeção inclui
capacidades, recursos, posição, alvos conhecidos, armas equipadas, último ataque
e histórico on recente.

Ele retorna `ActionPlan`, com etapas e trechos de origem classificados.
A definição dos campos e exemplos de planos compostos está em
[planos e validação](../aplicacao/planos-e-validacao.md#contrato-da-interpretação).
A interpretação não move o personagem, rola dados ou decide as respostas do Mundo.

## Como interpreta

As instruções reais do adaptador apresentam os modos e as operações suportadas.
O pedido inclui o contexto atual; a Responses API gera JSON segundo o esquema
estrito. A ordem `operation-first` põe a operação antes dos campos específicos
da variante. O Python desserializa e valida estrutura, referências e coerência
declarativa dos trechos, sem manter uma lista paralela de verbos em português.

Uma inconsistência declarativa admite a correção configurada, com pedido
original e motivo objetivo. Formato inválido e falha de rede não são essa
correção. A [configuração comum](integracao-openai.md) define os limites reais;
os logs preservam cada tentativa. Não se substitui um plano rejeitado por um
plano conhecido escrito no teste.

## Intenções compostas e contexto

“Uso Surto de Ação para atacar novamente” pede poder e ataque, na ordem.
“Fico parado”, como decisão de passar a vez em combate, pede fim do turno;
permanecer parado durante outro poder não encerra a vez antecipadamente.
Perguntas, citações e negações são classificadas sem autorizar gasto.

Um ataque ou uma interação pode permitir aproximação contextual. A IA identifica
restrições, como “sem sair do lugar”, mas é a aplicação que calcula e executa
a [aproximação](../aplicacao/movimento-contextual.md). “Guarda 1”
é resolvido pelo número/id conhecido; “o guarda anterior” usa o último ataque
real, sem trocar silenciosamente um alvo indisponível.

## Limites e avaliação

Trechos literais e classificações coerentes não provam que o modelo entendeu
a frase. A qualidade da interpretação é avaliada por expectativas independentes
e pelos efeitos executados. Consulte a
[política live](../qualidade/politica-live-tests.md).

A [POC de interpretação](../../../pocs/interpretacao/README.md) mede variantes sem
executar planos. Seus resultados datados ficam nas evidências históricas e
não são garantia de desempenho do contrato atual. Mudanças de instruções ou
esquema passam pela [revisão de contratos](contextos-e-contratos.md#como-revisar-uma-mudança).

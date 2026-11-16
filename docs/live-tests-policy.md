# Política dos live tests

## Leitura e finalidade

Leia este documento antes de criar, alterar ou executar testes live. O objetivo é
avaliar a aplicação que o jogador utiliza, com os mesmos fluxos, regras, mapas,
contextos e adaptadores. O [plano de adoção](live-tests-plan.md) descreve a migração
do código atual; esta política não significa que essa migração já aconteceu.

“Usar 100% das estruturas da aplicação” significa compartilhar a implementação do
comportamento avaliado. Os testes continuam responsáveis por entradas, condições
iniciais, controle da aleatoriedade, observação e resultados esperados. Esses
critérios precisam ser independentes da implementação para detectar seus erros.

Passar testes live é evidência limitada aos casos e às execuções observadas.
Modelos reais podem variar mesmo com condições iguais. Compartilhar o código
remove divergências entre teste e aplicação, mas não garante todas as respostas
em produção nem elimina falhas compartilhadas.

## Fonte única da execução

Para testes de fluxo completo:

- Use a mesma entrada pública de aplicação que o simulador utiliza para abrir a
  partida, enviar mensagens, responder a reações pendentes e reiniciar.
- Carregue cenários pelo carregador da aplicação. Se houver construção de mapas,
  use o mesmo construtor e os mesmos validadores usados pelo simulador.
- Use as configurações e a composição reais de interpretador, diretor do Mundo,
  narrador e SDK, com o mesmo processo de resolução de modelo e parâmetros.
- Deixe a aplicação decidir quais etapas executar e em que ordem: perguntas off,
  ações, validação, correção de interpretação, movimento contextual, respostas do
  Mundo, turnos de NPCs, oportunidades e narração.
- Construa instruções, esquemas e contextos durante a execução, pelas funções da
  aplicação. O teste não monta uma versão alternativa dos dados enviados à IA.
- Observe o resultado da execução real. Não substitua uma falha por um plano
  conhecido, não pule uma etapa e não repita uma chamada até obter sucesso.

Um teste sem janela pode cobrir o fluxo completo do jogo. Pygame, eventos do
mouse, renderização e agendamento de threads têm validação própria. A execução
sem interface deve compartilhar a coordenação do jogo; dispensar a janela não
autoriza escrever uma coordenação equivalente dentro de `tests/`.

## O que pode ser fixado

A implementação atual da preparação e do histórico validado está descrita em
[preparação reproduzível](live-test-preparation.md), com os limites ainda não
migrados para o coordenador.

| Pode pertencer ao teste | Condição |
| --- | --- |
| Cenário e variações declaradas | Dados passam pelo carregador, estruturas e validadores da aplicação; sem construtor de mapa exclusivo do teste. |
| Mensagens do jogador e escolhas de reação | São entradas, inclusive frases reais que já causaram falhas. |
| Rolagens | Injetadas pelo contrato de dados da aplicação; registrar tipo, ordem e valor, sem trocar a resolução das regras. |
| Estado intermediário | Preparado por operações públicas reais e validado antes da interação avaliada; não atribuir diretamente estado privado para fabricar o resultado. |
| Histórico de uma sessão real | Reproduzido pelo mecanismo compartilhado de histórico; identificar que é uma regressão com histórico congelado. |
| Expectativas e invariantes | Independentes do resultado retornado e sem exigir uma redação literal única. |
| Limites do experimento | Modelo efetivo, repetições, custo máximo e ponto de término ficam explícitos. |

Durante a preparação, operações determinísticas podem evitar chamadas pagas para
chegar a uma situação conhecida. Isso não testa a interpretação da preparação.
A interação avaliada deve passar pelo fluxo real completo declarado para o caso.
Não mova helpers exclusivos de teste para `src/` apenas para aparentar reúso:
uma estrutura compartilhada precisa servir ao caminho utilizado pela aplicação.

Não congele como entrada do modelo: prompt de sistema alternativo, contexto
pré-redigido, esquema copiado, disponibilidade de ações calculada pelo teste,
resposta de IA substituta ou resultado de regras calculado fora do motor.

## Contexto e mudanças de contrato

Cada fase deve declarar quais dados recebe e a origem desses dados: interpretação
do Jogador, decisão do Mundo, turno de NPC e narração inicial/de resultado/off.
Separe estado completo do Mundo de percepção do Jogador e preserve os segredos.
As projeções utilizadas pelo teste devem ser as mesmas da aplicação.

Adicionar ou remover um campo precisa alcançar os testes automaticamente pela
construção do contexto atual. Não mantenha uma cópia antiga para fazê-los passar.
Uma mudança legítima pode preservar todos os comportamentos esperados; não é
necessário que qualquer campo novo quebre um caso comportamental.

Para impedir alterações silenciosas, execute a
[verificação offline dos contratos](ai-contexts.md):
`poetry run python tools/context_contracts.py --check`. Ela compara campos,
instruções e esquemas atuais com a referência revisada, sem usá-la para montar
pedidos. O pytest padrão também faz essa comparação. Uma diferença exige revisão
explícita e justificativa em `--update --reason`, sem atualização automática em
testes/CI. Isso distingue “o contrato mudou” de “o comportamento regrediu”.

## Critérios que podem reprovar a aplicação

Escreva antes da chamada quais efeitos devem acontecer e quais são proibidos:
posição, percurso, alcance, recursos, portas, inventário, alvos, iniciativa,
reações, interrupções e fatos disponíveis à narração, conforme o caso.

Não calcule o esperado chamando novamente a mesma função que produziu o resultado.
Não aceite apenas “a IA retornou JSON válido”. Para uma ação executada, confira
o estado e o relatório; para uma ação impedida, confira causa e progresso parcial.
Narração não vazia também não prova coerência: declare quais fatos precisam ser
verificados automaticamente e quais dependem de revisão humana do texto salvo.

Avalie equivalência de comportamento, permitindo planos legais diferentes e
redações diferentes. Um caso interrompido por erro de serviço, orçamento de
chamadas ou decisão pendente não conta como fluxo completo bem-sucedido, salvo
quando esse for exatamente o ponto de término declarado do teste.

## Escopo e evidências

A [composição compartilhada dos serviços](service-composition.md) registra a
configuração efetiva. Use-a para criar os adaptadores; declare diferenças
experimentais em vez de recompor parâmetros silenciosamente dentro do teste.

Identifique cada suíte como fluxo completo, contrato de adaptador ou experimento
de provedor. Testes isolados continuam úteis, mas não são apresentados como
garantia do fluxo completo. Experimentos com prompts/modelos alternativos devem
ser explícitos e não integram a evidência de equivalência com o simulador padrão.

Preserve, inclusive em falhas: identificação e configuração efetiva da execução,
cenário/variação, entrada, histórico relevante, rolagens, pedidos efetivamente
enviados, respostas, planos, relatórios, estado antes/depois, tokens e erros. Use os
logs da aplicação e seus identificadores de correlação. Não registre credenciais.

Use `@pytest.mark.live`, mantenha a suíte padrão offline e exija a autorização de
execução prevista no cenário. Criar ou alterar um teste não autoriza chamadas
pagas. Defina limites e repetições antes de executar; reporte tentativas, falhas,
resultados inconclusivos e sucessos sem descartar execuções desfavoráveis.

## Revisão antes de acrescentar um caso

1. Li esta política e identifiquei o escopo do caso?
2. A entrada, carregador, construtores, fluxo, contextos e adaptadores são os
   efetivamente utilizados pela aplicação, no trecho que afirmo avaliar?
3. O teste contém somente preparação declarada, entradas, observação e critérios,
   sem regras ou coordenação alternativa do jogo?
4. As condições iniciais são válidas, e as expectativas detectariam a falha que
   motivou o caso, mesmo se a aplicação retornasse um plano formalmente válido?
5. Os limites da avaliação, as evidências e o custo estão documentados?

Na migração, documente qualquer desvio ainda presente. Não rotule um teste como
fluxo completo enquanto ele pular a coordenação utilizada pelo simulador.

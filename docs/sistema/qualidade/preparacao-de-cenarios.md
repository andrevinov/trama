# Preparação reproduzível de situações

Tier 3 · [Qualidade](README.md) · [Visão geral](../../../README.md)

As condições dos testes são preparadas com operações reais e pré-condições explícitas. A interpretação da preparação não é avaliada: planos declarados evitam chamadas pagas para chegar à situação. A mensagem avaliada passa pelo fluxo e pelo adaptador reais, com contexto produzido pela aplicação.

## Dados, execução e expectativas

O [catálogo da aplicação](../../../src/trama/scenarios/situations.json) declara
cenário/variação, planos de preparação, dados, pré-condições e histórico registrado.
A [seleção de situações](../simulador/carregamento-de-cenarios.md#situações-reproduzíveis)
permite abrir esses mesmos estados pela CLI, com `--situation ID`.

O [arranjo de movimento contextual](../../../tests/fixtures/contextual_movement/README.md)
conserva somente identificação, mensagem avaliada, escolhas, limite de chamadas e
critério de sucesso. Não há outra cópia de preparações ou condições iniciais no
teste. `build_case` permanece como atalho local para verificações dos critérios;
ele delega a preparação a `Situation`, sem interpretar ou resolver regras próprias.

O caminho efetivo da CLI e da suíte live contextual é:

1. `load_situation(id)` lê o catálogo empacotado e valida a declaração.
2. `open_situation` lê o recurso de cenário e aplica as variações declaradas.
3. A composição compartilhada chama `build_session`, com os validadores reais e
   um `ScriptedRoller` estrito, sem substituir resolução de regras.
4. O `GameFlow` executa a preparação injetada por `Situation.initialize`: planos
   declarados passam por `Conversation.execute`.
5. A aplicação confere status, efeitos exigidos, dados consumidos, ausência de
   etapas/escolhas pendentes e todas as pré-condições. Uma falha impede a abertura.
6. Janela ou `game.runner.start` pede a descrição inicial. O fluxo acrescenta o
   histórico registrado após a resposta concluída, preservando sua janela recente.
7. A mensagem avaliada passa por `game.runner.submit`; a aplicação coordena a
   interação e o teste observa efeitos e compara critérios independentes.

Reiniciar pelo fluxo limpa a sessão e a conversa, repõe os dados e refaz a mesma
preparação. O histórico registrado não se acumula entre reinícios. Sem situação
selecionada, o simulador segue usando a dungeon inicial e rolagens aleatórias.

As pré-condições incluem posição em base 1, área, modo, saldo de movimento,
descoberta/inventário/equipamento, roupa/disfarce, portas, iniciativa, recursos e
ausência de oportunidade pendente. Mudanças no motor podem invalidar o arranjo.
A abertura da situação deve falhar nessa etapa, antes de consultar um modelo.

No caso de saldo de movimento, o jogador caminha 7,5 m no turno vigente e volta
à mesma posição. No caso de oportunidade, revelar a espada provoca um teste real
do guarda e o início do conflito. Não há atribuição de `session.state`,
`guard_alert` ou `disguise` pelo teste. Os logs registram as operações e os dados
que produziram esses estados.

## Histórico registrado

`DialogueMessage.from_data` aceita `role`, `on` e `off` opcional. Os papéis são
`player` e `narrator`; canais precisam ser texto, a mensagem não pode ser vazia
e a fala do jogador respeita o limite de 2000 caracteres. Campos adicionais e
papéis de instrução de sistema são rejeitados. Não há reinterpretação de
colchetes: os canais já registrados são preservados literalmente.

`Conversation.extend_history(messages)` valida o lote inteiro antes de
acrescentá-lo. `prepare`, `finish` e `failure` usam essa mesma entrada. Exemplo,
com a conversa já construída/preparada e o registro lido do arquivo:

```python
from trama.application.dialogue import DialogueMessage

messages = [DialogueMessage.from_data(m) for m in record['messages']]
conversation.extend_history(messages)
```

A operação acrescenta mensagens; não substitui o histórico, não executa as
ações descritas e não restaura posição, recursos ou relatórios. A memória mecânica
produzida pela preparação permanece intacta. Perguntas off continuam fora da
interpretação e disponíveis na narração. A fonte do histórico deve ser registrada
na fixture.

Importar texto registrado não garante sua veracidade narrativa. A procedência
precisa ser revisada e o estado real é conferido separadamente pelas
pré-condições. Não se deve fabricar uma fala do narrador para facilitar um teste.
O caso de grade fechada da suíte de interações usa somente os fatos mecânicos
da preparação; a frase de narrador inventada anteriormente foi removida.

Não foi criado um sistema geral de save/load ou um mecanismo para ignorar regras.
O histórico congelado identifica uma regressão específica, não uma conversa
integralmente gerada ao vivo desde o início.

## Verificação e limites

```bash
poetry run pytest tests/integration/test_simulator_situations.py tests/integration/test_contextual_live_scenarios.py tests/integration/test_conversation_history.py tests/unit/test_dialogue.py -q
```

As regressões locais verificam os oito arranjos na CLI e sem janela, reinício,
dados inválidos/inesperados,
pré-condições impossíveis, omissão da caminhada/abertura, investigação mal-sucedida
e preservação dos canais/memória. Um teste de fronteira proíbe atribuições
diretas aos campos de estado/histórico nos arquivos live atuais.

Os oito casos contextuais e os quatro de [conversa](conversa-live.md) usam a
composição e o runner compartilhados. As demais
suítes mantêm os limites descritos na [cobertura atual](cobertura-atual.md).
Preparação reproduzível não garante uma resposta determinística do modelo.

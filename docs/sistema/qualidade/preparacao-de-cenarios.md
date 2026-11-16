# Preparação reproduzível de situações

Tier 3 · [Qualidade](README.md) · [Visão geral](../../../README.md)

As condições dos testes são preparadas com operações reais e pré-condições explícitas. A interpretação da preparação não é avaliada: planos declarados evitam chamadas pagas para chegar à situação. A mensagem avaliada passa pelo fluxo e pelo adaptador reais, com contexto produzido pela aplicação.

## Dados, execução e expectativas

O [arranjo de movimento contextual](../../../tests/fixtures/contextual_movement/README.md)
tem cenário/variação, preparações, dados, mensagem e pré-condições declaradas.
`build_case` é um helper de teste: lê esses dados, instancia as intenções da
aplicação, chama operações públicas e compara observações com expectativas.
Não constrói outro mapa nem implementa outra resolução de jogo. Não foi movido
para `src/` para aparentar compartilhamento.

O caminho efetivo é:

1. Ler o cenário real e aplicar variações declaradas aos dados.
2. Usar `application.scenarios.build_session` e seus validadores reais.
3. Injetar dados pelo contrato `Roller`, sem substituir testes de habilidade,
   resolução de ataque ou iniciativa.
4. Executar planos declarados por `Conversation.execute`.
5. Conferir status, etapas pendentes, efeitos de preparação e ausência de escolhas
   não declaradas. O início de conflito pode ser um término esperado específico;
   outros impedimentos não são ignorados.
6. Conferir a quantidade de dados de preparação e as pré-condições explícitas.
7. No caminho live migrado, pedir a abertura por `game.runner.start` e depois
   acrescentar o histórico registrado pela entrada validada, quando houver.
8. Enviar a mensagem avaliada por `game.runner.submit` e observar o resultado,
   preservando os critérios. O arranjo local isolado pode apenas preparar o estado.

As pré-condições incluem posição em base 1, área, modo, saldo de movimento,
descoberta/inventário/equipamento, roupa/disfarce, portas, iniciativa, recursos e
ausência de oportunidade pendente. Mudanças no motor podem invalidar o arranjo.
O teste deve falhar nessa etapa, antes de consultar um modelo.

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
poetry run pytest tests/integration/test_contextual_live_scenarios.py tests/integration/test_conversation_history.py tests/unit/test_dialogue.py -q
```

As regressões locais verificam os oito arranjos, dados inválidos/inesperados,
pré-condições impossíveis, omissão da caminhada/abertura, investigação mal-sucedida
e preservação dos canais/memória. Um teste de fronteira proíbe atribuições
diretas aos campos de estado/histórico nos arquivos live atuais.

Os oito casos contextuais usam a composição e o runner compartilhados. As demais
suítes mantêm os limites descritos na [cobertura atual](cobertura-atual.md).
Preparação reproduzível não garante uma resposta determinística do modelo.

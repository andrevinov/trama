# Interpretação semântica e validação de planos

A IA interpreta a linguagem do Jogador. O Python valida estrutura, referências,
consistência das origens declaradas e regras do jogo. Não há lista de verbos,
conectivos ou expressões em português no autorizador.

## Contrato da interpretação

O interpretador retorna `request_parts` e `steps`. Cada trecho contém:

- `text`: trecho literal do pedido on atual;
- `kind`: execute, question, negated, quoted, narrative_detail, unsupported,
  conditional ou unclear;
- `operations`: operações solicitadas nesse trecho, na ordem;
- `step_indices`: etapas correspondentes, com índices a partir de zero.

Uma origem pode solicitar várias etapas. Por exemplo:

```json
{
  "request_parts": [{
    "text": "Uso Surto de Ação para atacar novamente",
    "kind": "execute",
    "operations": ["action_surge", "attack"],
    "step_indices": [0, 1]
  }],
  "steps": [
    {"operation": "action_surge", "target_id": null, "weapon": "greatsword", "use_inspiration": false},
    {"operation": "attack", "target_id": "guard_1", "weapon": "greatsword", "use_inspiration": false}
  ]
}
```

`dash` e `inspiration` aparecem em operations quando modificam uma etapa.
Perguntas, negações, citações e detalhes narrativos não vinculam etapas nem
operações. Um plano pode ter zero etapas se registrar somente esses trechos.
Uma intenção não realizável termina em `clarify`, representada pelo formato de
esclarecimento já existente. Etapas suportadas anteriores podem ser preservadas.

No turno vigente do Jogador, declarar inatividade (“fico parado”, “não faço nada”,
“aguardo”) pode expressar passar a vez: a interpretação retorna `execute` com
`end_turn`, mesmo havendo recursos livres. Não é classificado como negação nem
mero detalhe narrativo. A mensagem inteira determina a intenção: postura durante
um poder não encerra; uma ação seguida de “não faço mais nada” encerra depois dela.
Perguntas, citações e negações de encerrar a vez não autorizam essa operação.
No modo narrado, permanecer/aguardar usa `wait`, sem turnos. Isso é uma decisão
de interação solicitada pelo usuário, sem gramática de verbos no Python.

“Fico de frente para a sala” é `narrative_detail`, sem ação mecânica, orientação
persistente ou custo. “Volto”, “retorno” e outras paráfrases são interpretadas
pelo modelo. Coordenadas explícitas são traduzidas em segmentos a partir da
posição atual; ocupar uma porta aberta é permitido quando o espaço está livre.

## Validação e execução

1. O parser verifica os campos, tipos, operações e limites do contrato.
2. O validador verifica que os trechos pertencem ao on atual, que cada etapa
   possui uma origem na ordem e que as operações declaradas correspondem ao
   plano, incluindo modificadores. Off e histórico não são fontes de execução.
3. Antes de consultar o Mundo, verifica ids de lugares/passagens e criaturas
   visíveis. Perguntas e trechos não executáveis não podem gastar recursos.
4. Uma inconsistência declarativa permite no máximo uma correção pela IA, com
   o pedido original e motivo objetivo. Formato inválido e erros de rede não
   disparam essa correção. Persistindo o erro, o plano não produz efeitos.
5. Na execução, cada etapa verifica alcance, visão, movimento, iniciativa, ação,
   bônus e usos conforme as regras existentes. Uma ação anterior pode habilitar
   a seguinte: Surto de Ação concede o orçamento antes do ataque. Um impedimento
   real interrompe o restante, preservando efeitos já aplicados.
6. Perguntas reconhecidas em on seguem em `execution.questions` para resposta
   off do narrador; um plano sem etapas não consulta o Mundo. Posturas seguem
   em `execution.narrative_details`, sem autorizar alterações mecânicas.

A janela e a conversa verificam as origens também para adaptadores alternativos.
Esses adaptadores devem fornecer RequestPart no ActionPlan. O uso direto de
GameSession continua uma API determinística de confiança, sem exigir texto ou
metadados de IA. O parser aceita planos antigos somente na API local de leitura;
a integração OpenAI exige as origens do novo contrato.

## Referências e contexto

`last_attack` vem do último ataque efetivamente resolvido pelo motor, inclusive
um erro na rolagem. Contém alvo, arma, rodada e tipo de ataque; o contexto informa
se o alvo continua vivo e visível. Tentativas rejeitadas não o substituem, e
reiniciar limpa a referência. A IA usa esses dados em “ataco o guarda anterior”,
sem trocar silenciosamente um alvo morto ou oculto por outro.

O contexto mínimo inclui posição, unidades, destinos, criaturas visíveis com
números, catálogo de comandos, armas equipadas, recursos de turno e até seis
mensagens on. A projeção conserva os dados quando aplicada novamente. O Mundo
mantém o contexto completo e recebe também a origem declarada das etapas.

## Limites e evidências

A classificação semântica e a escolha de operações continuam sendo propostas da
IA. Encontrar um trecho literal não prova que houve consentimento: uma IA pode
classificar erroneamente uma negação como pedido e produzir campos coerentes
entre si. O validador não promete reconhecer esse erro sem interpretar linguagem.
As instruções proíbem acrescentar gastos e ações; as regressões avaliam perguntas,
negações, discurso relatado e pedidos compostos. Não há segunda chamada obrigatória
para reinterpretar toda mensagem, nem nova confirmação para poderes claramente
solicitados.

Os testes locais usam interpretações fixas para verificar validação e efeitos;
não demonstram que o modelo real sempre produzirá o plano correto. Os testes live
opcionais avaliam a interpretação com critérios independentes, sem executar o
plano, e exigem autorização explícita para chamadas pagas.

Logs preservados: `ai.decision`, `player.plan_authorized`,
`player.plan_authorization_rejected`, `ai.plan_correction_requested` e
`ai.plan_authorization_failed`. `player.request_sources` registra os trechos e
classificações em DEBUG; a validação é identificada como `declarative`.


## Movimento contextual

Portas, ataques e interações de cenário incluem `allow_approach`. Exemplo:

```json
{"operation": "open", "target_id": "gate_1", "allow_approach": true}
```

O alvo continua exigindo um id existente e o conhecimento apropriado do
Jogador. `allow_approach=false` impede a aplicação de preparar movimento para a ação; o interpretador o usa
quando há uma restrição explícita de ficar no lugar. O core ainda exige alcance
para alterar uma porta. Passagens já no estado pedido não exigem movimento.

As origens continuam apontando para as etapas solicitadas, sem fabricar trechos
que autorizem microetapas. A ação autoriza a aproximação associada ao requisito espacial que a sua
implementação publica; o evento preparado registra sua origem em `preparation_for`. Isso não
autoriza ataques adicionais, Dash, destrancar ou abrir barreiras intermediárias. A IA continua
responsável por reconhecer a restrição no português; o Python aplica o booleano,
sem acrescentar uma lista de verbos ou fingir provar consentimento semântico.
O leitor mantém compatibilidade com os formatos anteriores, mas os esquemas
enviados ao modelo incluem a restrição explicitamente. Uma resposta `investigate`
pode autorizar entrar no cômodo; uma resposta `attack`, aproximar-se do alvo
visível. A preparação não autoriza coleta não solicitada, troca de alvo, armas
inexistentes ou poderes adicionais. O código valida recursos antes de caminhar e
revalida após o movimento. A iniciativa precede a aproximação tática de ataque.

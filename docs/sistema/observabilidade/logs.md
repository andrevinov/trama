# Logs estruturados

Tier 3 · [Observabilidade](README.md) · [Visão geral](../../../README.md)

O Trama usa `logging` da biblioteca padrão. Cada componente emite eventos com
nome estável e dados próprios; `trama.observability` configura destino, formato e
correlação. Não há dependência nova, serviço de logs ou alteração nas regras.

## Execução

```bash
# INFO: conversa, operações e resultados do jogo, consumo de IA, avisos e erros.
poetry run trama-simulator

# DEBUG: inclui prompts completos, contexto, decisões e detalhes das regras.
poetry run trama-simulator --debug

# Arquivo específico para investigar um caso.
poetry run trama-simulator --debug --log-file logs/caso-porta.jsonl

# Acompanhar o arquivo, inclusive após rotação.
tail -F logs/trama.jsonl
```

A demonstração grava JSONL no terminal (stderr) e em `logs/trama.jsonl` por
padrão. Cada linha é um objeto JSON completo, inclusive quando o conteúdo tem
quebras de linha ou traceback. O arquivo gira ao atingir aproximadamente 5 MB,
mantendo três cópias anteriores (`.1`, `.2`, `.3`). Não há limite de tamanho que
trunque o conteúdo de um evento individual.

Importar ou usar os módulos como biblioteca não abre arquivos nem configura o
logger raiz. Outra aplicação pode chamar `configure_logging` ou instalar seus
próprios handlers. A configuração padrão afeta somente `trama.*`, sem habilitar
logs HTTP de OpenAI, httpx ou outras bibliotecas.

## Formato comum

| Campo | Conteúdo |
| --- | --- |
| `schema_version` | Versão do envelope; atualmente `1` |
| `timestamp` | Data/hora UTC, ISO 8601, com milissegundos |
| `level` | DEBUG, INFO, WARNING, ERROR ou CRITICAL |
| `component` | Módulo emissor, como `trama.movement` |
| `event` | Nome estável, como `movement.resolved` |
| `session_id` | Identificador da execução da aplicação, mantido durante reinícios do cenário |
| `interaction_id` | Uma mensagem, pedido de descrição inicial ou ação por botão |
| `operation_id` | Uma operação executada pela sessão, como mover, atacar ou usar um recurso |
| `ai_call_id` | Uma chamada à IA, abrangendo transporte e validação da resposta |
| `data` | Campos específicos do evento |
| `error` | Tipo, mensagem, causas encadeadas e traceback; `null` quando não há exceção associada |

Identificadores sem escopo aplicável aparecem como `null`. Por exemplo, carregar
um cenário tem `session_id`, mas não exige uma mensagem ou uma chamada à IA.
Uma ação usa normalmente três chamadas de IA (Jogador, Mundo e narração).
Turnos de NPCs acrescentam decisões do Mundo, correlacionadas à mesma mensagem.

Exemplo, formatado aqui para leitura; no arquivo ocupa uma linha:

```json
{
  "schema_version": 1,
  "timestamp": "2026-11-13T12:00:00.123+00:00",
  "level": "DEBUG",
  "component": "trama.dice",
  "event": "dice.rolled",
  "session_id": "sessao-exemplo",
  "interaction_id": "mensagem-exemplo",
  "operation_id": "ataque-exemplo",
  "ai_call_id": null,
  "data": {"sides": 20, "result": 19},
  "error": null
}
```

Dataclasses são convertidas em objetos; tuplas/conjuntos, em listas. Valores
`Decimal` são strings para preservar precisão: `"1.5"` representa metros nos
campos `*_meters`. Posições de domínio (`x`, `y`) usam base zero. Prompts e
relatórios preservam o contrato da interface, com colunas/linhas em base um;
o log não reescreve os dados realmente enviados à API.

## Eventos disponíveis

| Componentes | Eventos e detalhes |
| --- | --- |
| Inicialização | `app.started`, `app.failed`, `app.stopped`; cenário, modo e arquivo |
| Conversa/UI | Submissão, separação on/off, plano executado, interrupção, resposta final e falhas da thread |
| Transporte da IA | `ai.request_started`, `ai.request_payload`, `ai.response_received`, `ai.response_payload`, `ai.request_failed` |
| Interpretador | `ai.plan_validated`, `ai.decision`, `ai.intent_rejected`, `ai.plan_rejected` e payloads rejeitados |
| Autorização | `player.plan_authorized`, `player.plan_authorization_rejected`, `player.plan_clarification_accepted`; operações solicitadas/propostas e estágio |
| Correção | `ai.interpretation_attempt`, `ai.plan_correction_requested`, `ai.plan_authorization_failed`; no máximo duas tentativas, com chamadas distintas |
| Narrador | `ai.narration_validated`, `ai.narration`, `ai.narration_rejected` |
| Sessão | `game.operation_started`, `game.operation_requested`, `game.operation_completed`, `game.operation_rejected`, `game.operation_failed`; estado anterior/posterior, orçamento e personagens alterados |
| Movimento e caminho | `movement.requested`, `movement.resolved`, `routing.path_found`, alternativa arquitetônica e destino inacessível; percurso, custo e impedimento |
| Unidades | `distance.converted`; valor/unidade recebidos e resultado em metros, antes da validação do movimento |
| Portas e ações | `door.resolved`, `door.unchanged`, `action.budget_calculated`; estado da porta e orçamento calculado |
| Mapa, visão e criaturas | Carregamento, mudança de passagem e recálculo da visão; sem registros por raio ou por quadro da janela |
| Personagens | `character.power_used`, `character.inspiration_used`, `character.ability_check_resolved`, `character.rest_finished`, `character.mastery_changed` |
| Sentidos dos NPCs | `perception.detected`, `perception.awakened`, `perception.hide_resolved`, `perception.search_resolved`; observador, fonte, sentido, grau de conhecimento, dados e CD reais. |
| Abordagem e Influence | `game.parley_started`, `game.influence_resolved`; interlocutor, posições, julgamento, dados, resultado social e iniciativa quando houver. |
| Mundo | Decisão separada, ações de NPCs, testes de Percepção e interrupções do Jogador |
| Combate/encontro | Iniciativa, ataque, turno, encerramento, efeitos, ação concluída e orçamento aplicado |
| Dados | `dice.rolled`, `dice.d20_resolved`, `dice.invalid_result`; faces, resultados individuais, modificador, vantagem/desvantagem e seleção |

Funções de regras calculam resultados e os registram. `action.budget_calculated`
é uma proposta de orçamento, não prova de que o estado foi aplicado. A aplicação
registra a confirmação em `encounter.action_completed` e/ou
`game.operation_completed`. Uma validação posterior pode rejeitar a operação;
nesse caso não há confirmação e aparece `game.operation_rejected`.

Eventos de progresso, resultado e textos da conversa ficam em INFO. Payloads completos da IA, rolagens
individuais e detalhes técnicos ficam em DEBUG. Rejeições previstas pelas regras
são WARNING; falhas de integração/validação da IA e erros inesperados são ERROR.
Operações interrompidas com progresso parcial registram o resultado e seu
`stop_reason`, sem transformar esse progresso em falha total.

## Investigação de um plano inválido

1. Localize `ai.plan_rejected` e copie seu `interaction_id`.
2. Veja `ai.request_payload`: contém os parâmetros enviados, incluindo
   `instructions`, `input` (prompt do jogador, contexto e histórico), modelo,
   raciocínio configurado, limite de saída e JSON Schema.
3. Veja `ai.response_payload` e `ai.rejected_plan_payload`: contêm a resposta
   original. `ai.decision` mostra o plano convertido para os contratos Python
   somente quando ele passou na validação.
4. Consulte `ai.intent_rejected.data.reason` e `ai.plan_rejected.error.causes`:
   preservam o motivo concreto e a cadeia de erros. `step_index` identifica a
   etapa, em base zero. O traceback mostra o ponto da validação.
5. Confira `game.operation_completed` para saber o que efetivamente mudou.
   Uma resposta rejeitada antes da execução não movimenta o personagem.

Exemplo de busca simples:

```bash
rg 'ai.plan_rejected|ai.intent_rejected' logs/trama.jsonl
```

Os logs passam a registrar as próximas tentativas; não recuperam a resposta de
uma chamada antiga que ocorreu antes de esta camada existir. A instrumentação
não altera o interpretador para aceitar planos que falharam na validação.

## Tokens e conteúdo da IA

`ai.response_received.data.usage` registra os contadores devolvidos pelo SDK:
`input_tokens`, `output_tokens`, `total_tokens`, `cached_input_tokens`,
`cache_write_tokens` e `reasoning_tokens`. Cache e raciocínio são detalhamentos,
não quantidades a somar novamente ao total. Também há modelo, duração,
`response_id` e identificador da requisição do provedor, quando disponíveis.

O consumo é registrado antes de rejeitar uma resposta incompleta ou um plano
inválido. Se o provedor não devolver um contador, ele fica `null`; uma falha de
rede sem resposta não implica zero tokens consumidos. Não há estimativa de
preço ou de tokens. As decisões observáveis são as saídas estruturadas da API;
o raciocínio interno do modelo não está disponível nesses logs.

Os eventos de conversa em INFO preservam o texto completo em `data.text`, com
`data.speaker`. DEBUG inclui adicionalmente os prompts internos e informações do mundo, inclusive dados
que não seriam visíveis ao personagem. Os arquivos em `logs/` são ignorados
pelo Git. O formatter oculta campos de credenciais conhecidos e padrões de
chave `sk-...`/Bearer; clientes, variáveis de ambiente e headers de autenticação
não são enviados ao logger. Essa ocultação não remove informações pessoais
arbitrárias que tenham sido escritas no próprio prompt.

## Uso por módulos

Para analisar os eventos como tabelas, o repositório inclui um
[formato e consultas para lnav](investigacao-com-lnav.md). O pacote fica em
`tools/lnav/`, sem dependência da engine; reconhece o envelope e oferece tabelas
de eventos, chamadas de IA e erros, preservando os dados completos.
Na tabela `|trama-events`, `preview` varia conforme o evento. Para ler a mensagem
completa ou inspecionar o JSON da linha selecionada na visão LOG, use
`|trama-detail`; `q` retorna. Também é possível informar `log_line`, por exemplo
`|trama-detail 24`, diretamente de uma tabela.

Um produtor depende apenas da biblioteca padrão:

```python
import logging

logger = logging.getLogger(__name__)
logger.info("example.operation_completed", extra={"data": {"actor_id": "player", "changed": True}})
```

Mantenha o nome do evento constante e coloque valores variáveis em `data`.
Use `exc_info=True` ou `logger.exception` dentro do tratamento de exceções para
preservar a causa. Não serialize clientes nem objetos de transporte inteiros.

A aplicação pode abrir um escopo com `log_context(interaction_id=...)` ou
`log_context(operation_id=...)`; ele é restaurado ao sair. O domínio não importa
esse mecanismo. Na janela, `copy_context()` propaga o contexto para a thread da
IA, e a leitura da fila restaura a mesma interação na thread principal.

Objetos de dados, contratos e projeções de leitura não emitem um evento para
cada acesso. Seus dados aparecem nos eventos das operações que os utilizam;
desenhar a janela não gera uma sequência contínua de logs repetidos.

A suíte local verifica envelope, rotação, correlação entre threads, redaction,
payloads enviados/recebidos, tokens ausentes e conhecidos, causas de rejeição,
rolagens, recursos e comportamento inalterado do jogo. Não usa chamadas pagas.

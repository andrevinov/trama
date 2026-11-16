# Formato do Trama para lnav

Formato JSON e consultas de leitura para lnav **0.14 ou superior**. Ficam fora
de `src/trama/`: a engine não depende do lnav e o add-on não altera os logs.

## Instalar

Na raiz do repositório:

```bash
lnav -i tools/lnav/formats/trama/trama_log.json \
        tools/lnav/formats/trama/trama_views.sql \
        tools/lnav/formats/trama/trama-events.lnav \
        tools/lnav/formats/trama/trama-ai.lnav \
        tools/lnav/formats/trama/trama-errors.lnav \
        tools/lnav/formats/trama/trama-detail.lnav
```

O instalador nativo copia os seis arquivos para `formats/installed` na
configuração do usuário. Nesta máquina: `~/.config/lnav/formats/installed/`.
Feche e reabra o lnav após instalar ou atualizar o pacote. Os formatos de Rust,
Tessitura e outros serviços não são modificados.

Para experimentar diretamente a versão do repositório, sem instalação:

```bash
lnav -I tools/lnav logs/trama.jsonl
```

## Abrir e analisar

```bash
# Visão de log com colunas alinhadas; -R inclui rotações existentes.
lnav -R logs/trama.jsonl

# Abrir diretamente a tabela de eventos.
lnav -c '|trama-events' logs/trama.jsonl
```

Na visão de log, cada linha mostra horário local, nível, módulo, evento,
interação abreviada e uma prévia do payload específico. Não há colunas fixas de
tokens ou duração nas linhas que não têm esses dados. Textos e JSONs extensos
são truncados só na apresentação; o conteúdo gravado permanece completo.
Na definição do formato, os campos usados em `line-format` ficam com
`hidden: false`. Somente payloads completos e metadados auxiliares ficam
ocultos. A validação usa também `write-screen-to`, que respeita a visibilidade
real da tela; `write-view-to` sozinho não detecta colunas ocultas.

Dentro do lnav, digite um dos comandos abaixo, incluindo `|`, e pressione Enter:

| Comando | Tabela apresentada |
| --- | --- |
| `\|trama-events` | Eventos e prévia específica: conversa, movimento, poder, ataque, teste ou chamada de IA |
| `\|trama-ai` | Uma linha por chamada de IA: modelo, tarefa, status, duração e tokens |
| `\|trama-errors` | Avisos e erros, tipo da exceção e causa mais específica |
| `\|trama-detail` | Texto completo ou JSON do evento selecionado na visão LOG |
| `\|trama-detail 24` | Texto completo ou JSON de `log_line=24`, de qualquer visão |

## Ler a conversa completa

1. Na visão **LOG**, selecione a linha da mensagem com as setas.
2. Digite **`|trama-detail`** e pressione Enter.
3. O texto abre em uma visão de texto com quebra de linha e sem truncamento.
   Use as setas/PgUp/PgDn para ler; **q** retorna à visão anterior.

Se estiver na tabela `|trama-events`, use **Shift+V** para ir da linha da tabela
ao evento original e então `|trama-detail`. Outra opção é informar o número da
primeira coluna, por exemplo **`|trama-detail 24`**. `log_line` usa base zero.

O comando preserva parágrafos, acentos e colchetes de off. Em eventos sem texto,
abre o envelope JSON completo formatado, incluindo valores específicos e
traceback. Usa `trama-detail.txt` no diretório de configuração do lnav como um
buffer de leitura, substituído ao abrir outro detalhe. O arquivo de log não é
alterado.

As novas mensagens de jogador, narrador e respostas locais são gravadas com
texto completo mesmo em **INFO**. O narrador registra a resposta final realmente
entregue, incluindo explicações off acrescentadas pelo código. Logs antigos
que só guardaram `has_on`/`has_off` não têm texto recuperável; o comando informa
essa limitação. Reinicie a demonstração para gravar mensagens com a alteração.

## Dados específicos e prévias

A coluna `preview` da tabela é calculada no add-on, sem regras de jogo:

- Conversa: começo do texto, com até 110 caracteres e reticências.
- Movimento: posições, custo em metros, movimento gasto e motivo de parada.
- Ataque: alvo, arma, d20, acerto/crítico e dano.
- Poder/teste/dado: recurso usado, PV/usos, perícia/CD/resultado ou faces/rolagem.
- IA: modelo, tarefa, status, duração e tokens **somente na chamada de IA**.
- Outros eventos: payload próprio ou causa do erro.

As colunas `detail`, `full_text`, `data` e `raw_record` da view `trama_events`
mantêm conteúdo completo. As posições de domínio do resumo usam `x/y` em base
zero; não se recalculam custos ou resultados no consumidor.

As colunas de IDs dos comandos são abreviadas em oito caracteres para facilitar
a leitura; os IDs completos permanecem nas views SQL. Use as setas para navegar
na tabela e **Shift+V** para ir à linha original indicada por `log_line`.
Repita o comando quando quiser atualizar a consulta com eventos novos.

Na visão de log, **p** abre os campos reconhecidos pelo parser, **Shift+P** abre
a visualização formatada e **o / Shift+O** percorrem mensagens da mesma
interação. `interaction_id` é o OPID do formato; `operation_id` e `ai_call_id`
continuam disponíveis para filtros específicos. Os nomes completos de evento,
os prompts e os tracebacks não são truncados nas views, mesmo que a linha
principal use colunas de largura limitada.

## Consultas SQL

Pressione `;` e use SQL. As views são carregadas automaticamente:

```sql
-- Todos os eventos de uma mensagem, usando o ID completo.
SELECT log_line, log_time, component, event, reason
FROM trama_events
WHERE interaction_id = 'cole-o-id-completo-aqui'
ORDER BY log_line;

-- Uso de IA por sessão; chamadas sem contadores continuam identificáveis.
SELECT session_id, count(*) AS calls,
       sum(total_tokens) AS reported_tokens,
       sum(total_tokens IS NULL) AS calls_without_usage
FROM trama_ai_calls
GROUP BY session_id;

-- Prompts/parâmetros efetivamente enviados e texto da resposta.
SELECT ai_call_id, json_extract(request, '$.instructions') AS instructions,
       json_extract(request, '$.input') AS input, response_text, failure_reason
FROM trama_ai_calls;

-- Validação e traceback completos de um plano rejeitado.
SELECT log_line, interaction_id, reason, causes, traceback
FROM trama_errors
WHERE event = 'ai.plan_rejected';

-- Dados específicos de movimento, sem alterar suas unidades.
SELECT log_time, operation_id,
       json_extract(data, '$.cost_meters') AS cost_meters,
       json_extract(data, '$.stop_reason') AS stop_reason
FROM trama_events
WHERE event = 'movement.resolved';
```

`trama_events.data` e `trama_events.error` preservam os objetos JSON completos.
A tabela nativa `trama_log` também fica disponível. As views extraem o envelope
original (`log_raw_text`), evitando que alinhamento ou abreviação da apresentação
mudem valores usados em consultas. `log_time` segue a conversão para horário
local configurada no formato; o timestamp UTC original continua no JSON bruto.

`trama_ai_calls` agrupa por sessão e chamada para não contar tokens novamente a
cada evento DEBUG ou erro. Uma chamada pode ter status `completed`, `error` ou
`pending`. A rejeição de um plano mantém os tokens da resposta recebida; falhas
sem resposta e contadores ausentes mantêm `NULL`, sem inventar consumo zero.
Cache e raciocínio são detalhamentos do total, não valores adicionais a somar.

Instruções e contexto completos enviados ao modelo continuam exclusivos do
modo debug; os textos da conversa ficam também em INFO:

```bash
poetry run python pocs/movimento/run.py --debug
```

O add-on não recupera conteúdo ausente de logs antigos. Sua detecção automática
é limitada a `trama*.jsonl`, suas rotações numéricas e arquivos `.jsonl` dentro
de uma pasta chamada `Trama`/`trama`. Isso evita capturar logs JSON de outros
serviços que também usam `timestamp` e `level`. Para um arquivo exportado com
outro nome fora do projeto, use um nome como `trama-caso-porta.jsonl`.

## Validar

```bash
lnav -C -I tools/lnav logs/trama.jsonl
poetry run pytest tests/integration/test_lnav_format.py -q
```

Os testes usam o binário real em modo sem interface, arquivos sintéticos e uma
configuração temporária; não instalam nada no perfil do usuário e não fazem
chamadas à IA. São ignorados quando o lnav não está instalado.

Referências oficiais: [formatos](https://docs.lnav.org/en/stable/formats.html),
[CLI e instalação](https://docs.lnav.org/en/stable/cli.html) e
[atalhos](https://docs.lnav.org/en/stable/hotkeys.html).

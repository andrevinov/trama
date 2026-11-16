-- Somente projeções de leitura: não altera o arquivo nem as regras do jogo.
-- Extraímos o envelope original para preservar null e evitar padding/truncamento
-- do log_body, que é uma representação visual do lnav.
-- Recriar somente nossas views evita definições antigas carregadas por outra
-- pasta de configuração durante uma atualização/teste do add-on.
DROP VIEW IF EXISTS lnav_db.trama_ai_calls;
DROP VIEW IF EXISTS lnav_db.trama_errors;
DROP VIEW IF EXISTS lnav_db.trama_events;
DROP VIEW IF EXISTS lnav_db.trama_event_data;
CREATE VIEW IF NOT EXISTS lnav_db.trama_event_data AS
SELECT log_line, log_time,
       upper(log_level) AS level,
       json_extract(log_raw_text, '$.component') AS component,
       json_extract(log_raw_text, '$.event') AS event,
       json_extract(log_raw_text, '$.session_id') AS session_id,
       json_extract(log_raw_text, '$.interaction_id') AS interaction_id,
       json_extract(log_raw_text, '$.operation_id') AS operation_id,
       json_extract(log_raw_text, '$.ai_call_id') AS ai_call_id,
       json_extract(log_raw_text, '$.data.duration_ms') AS duration_ms,
       json_extract(log_raw_text, '$.data.actor_id') AS actor_id,
       json_extract(log_raw_text, '$.data.target_id') AS target_id,
       coalesce(json_extract(log_raw_text, '$.error.causes[#-1].message'),
                json_extract(log_raw_text, '$.error.message'),
                json_extract(log_raw_text, '$.data.reason'),
                json_extract(log_raw_text, '$.data.stop_reason'),
                json_extract(log_raw_text, '$.data.result.stop_reason'),
                json_extract(log_raw_text, '$.data.report.stop_reason')) AS reason,
       json_extract(log_raw_text, '$.data') AS data,
       json_extract(log_raw_text, '$.error') AS error,
       log_raw_text AS raw_record
  FROM trama_log;

-- Texto completo e resumo pertencem ao consumidor: a engine não conhece lnav.
CREATE VIEW IF NOT EXISTS lnav_db.trama_events AS
WITH text_fields AS (
    SELECT *, coalesce(json_extract(data, '$.speech'), json_extract(data, '$.reply')) AS speech
      FROM trama_event_data
), texts AS (
    SELECT *, coalesce(json_extract(data, '$.text'),
        CASE WHEN speech IS NOT NULL THEN
            coalesce(json_extract(speech, '$.on'), '') ||
            CASE WHEN coalesce(json_extract(speech, '$.off'), '') != '' THEN
                CASE WHEN coalesce(json_extract(speech, '$.on'), '') != '' THEN char(10) || char(10) ELSE '' END ||
                '[' || json_extract(speech, '$.off') || ']'
            ELSE '' END
        END,
        json_extract(data, '$.output_text')) AS full_text
      FROM text_fields
), details AS (
    SELECT *, CASE
        WHEN full_text IS NOT NULL THEN full_text
        WHEN event = 'movement.resolved' THEN
            printf('%s → %s | custo=%s m | gasto no turno=%s m',
                   json_extract(data, '$.before.position'), json_extract(data, '$.after.position'),
                   json_extract(data, '$.cost_meters'), json_extract(data, '$.after.spent_meters')) ||
            CASE WHEN reason IS NOT NULL THEN ' | parou: ' || reason ELSE '' END
        WHEN event = 'combat.attack_resolved' THEN
            printf('alvo=%s | arma=%s | d20=%s | acerto=%s | crítico=%s | dano=%s',
                   json_extract(data, '$.target_id'), json_extract(data, '$.weapon'),
                   json_extract(data, '$.result.roll.dice'), json_extract(data, '$.result.hit'),
                   json_extract(data, '$.result.critical'), json_extract(data, '$.result.damage'))
        WHEN event = 'character.power_used' THEN
            printf('poder=%s | PV %s → %s | fôlego=%s | surto=%s',
                   json_extract(data, '$.power'), json_extract(data, '$.before.hp'), json_extract(data, '$.after.hp'),
                   json_extract(data, '$.after.second_wind_uses'), json_extract(data, '$.after.action_surge_uses'))
        WHEN event = 'dice.rolled' THEN printf('d%s = %s', json_extract(data, '$.sides'), json_extract(data, '$.result'))
        WHEN event = 'dice.d20_resolved' THEN
            printf('d20=%s | modificador=%s | total=%s', json_extract(data, '$.roll.dice'),
                   json_extract(data, '$.roll.modifier'), json_extract(data, '$.total'))
        WHEN event = 'character.ability_check_resolved' THEN
            printf('perícia=%s | total=%s | CD=%s | passou=%s', json_extract(data, '$.skill'),
                   json_extract(data, '$.total'), json_extract(data, '$.dc'), json_extract(data, '$.passed'))
        WHEN event = 'ai.response_received' THEN
            printf('%s | %s | status=%s | ms=%s | tokens in=%s out=%s total=%s',
                   json_extract(data, '$.task'), json_extract(data, '$.model'), json_extract(data, '$.status'),
                   duration_ms, coalesce(json_extract(data, '$.usage.input_tokens'), '?'),
                   coalesce(json_extract(data, '$.usage.output_tokens'), '?'), coalesce(json_extract(data, '$.usage.total_tokens'), '?'))
        WHEN event = 'ai.request_started' THEN
            printf('%s | modelo=%s | limite de saída=%s', json_extract(data, '$.task'),
                   json_extract(data, '$.model'), json_extract(data, '$.max_output_tokens'))
        WHEN event = 'door.resolved' THEN
            printf('operação=%s | aberta=%s', json_extract(data, '$.operation'), json_extract(data, '$.is_open'))
        WHEN json_extract(data, '$.result.event.summary') IS NOT NULL THEN json_extract(data, '$.result.event.summary')
        WHEN json_extract(data, '$.result.cost_meters') IS NOT NULL THEN
            printf('posição=%s | custo=%s m', json_extract(data, '$.movement_after.position'), json_extract(data, '$.result.cost_meters')) ||
            CASE WHEN reason IS NOT NULL THEN ' | parou: ' || reason ELSE '' END
        WHEN reason IS NOT NULL THEN reason
        WHEN event LIKE 'conversation.%' AND (json_extract(data, '$.has_on') IS NOT NULL OR json_extract(data, '$.has_off') IS NOT NULL)
            THEN 'Texto não gravado neste log antigo.'
        ELSE coalesce(data, '{}')
    END AS detail
    FROM texts
)
SELECT log_line, log_time, level, component, event, session_id, interaction_id, operation_id, ai_call_id,
       duration_ms, actor_id, target_id, reason, data, error, raw_record, full_text, detail,
       CASE WHEN length(replace(replace(detail, char(10), ' '), char(13), ' ')) > 110 THEN
           substr(replace(replace(detail, char(10), ' '), char(13), ' '), 1, 110) || '…'
       ELSE replace(replace(detail, char(10), ' '), char(13), ' ') END AS preview
  FROM details;

CREATE VIEW IF NOT EXISTS lnav_db.trama_errors AS
SELECT log_line, log_time, level, component, event,
       session_id, interaction_id, operation_id, ai_call_id, reason,
       json_extract(error, '$.type') AS error_type,
       json_extract(error, '$.causes') AS causes,
       json_extract(error, '$.traceback') AS traceback,
       data
  FROM trama_events
 WHERE level IN ('WARNING', 'ERROR', 'CRITICAL', 'FATAL');

-- Uma linha por chamada, mesmo que ela produza vários eventos DEBUG e ERROR.
-- Falha de transporte e resposta recebida sem usage continuam com tokens NULL.
CREATE VIEW IF NOT EXISTS lnav_db.trama_ai_calls AS
WITH calls AS (
    SELECT session_id, ai_call_id, min(log_line) AS log_line,
           min(log_time) AS log_time, max(interaction_id) AS interaction_id,
           max(CASE WHEN event = 'ai.request_started' THEN data END) AS request_meta,
           max(CASE WHEN event = 'ai.request_payload' THEN data END) AS request_payload,
           max(CASE WHEN event = 'ai.response_received' THEN data END) AS response_meta,
           max(CASE WHEN event = 'ai.response_payload' THEN data END) AS response_payload,
           max(CASE WHEN event = 'ai.request_failed' THEN duration_ms END) AS failure_duration_ms,
           max(CASE WHEN event IN ('ai.request_failed', 'ai.plan_rejected', 'ai.narration_rejected')
                    THEN reason END) AS failure_reason,
           max(CASE WHEN event IN ('ai.request_failed', 'ai.plan_rejected', 'ai.narration_rejected')
                    THEN 1 ELSE 0 END) AS failed
      FROM trama_events
     WHERE ai_call_id IS NOT NULL
     GROUP BY session_id, ai_call_id
    HAVING sum(event = 'ai.request_started') > 0
)
SELECT log_line, log_time, session_id, interaction_id, ai_call_id,
       coalesce(json_extract(request_meta, '$.model'), json_extract(response_meta, '$.model')) AS model,
       coalesce(json_extract(request_meta, '$.task'), json_extract(response_meta, '$.task')) AS task,
       CASE WHEN failed = 1 THEN 'error'
            WHEN response_meta IS NULL THEN 'pending'
            ELSE json_extract(response_meta, '$.status') END AS status,
       coalesce(json_extract(response_meta, '$.duration_ms'), failure_duration_ms) AS duration_ms,
       json_extract(response_meta, '$.usage.input_tokens') AS input_tokens,
       json_extract(response_meta, '$.usage.output_tokens') AS output_tokens,
       json_extract(response_meta, '$.usage.total_tokens') AS total_tokens,
       json_extract(response_meta, '$.usage.cached_input_tokens') AS cached_input_tokens,
       json_extract(response_meta, '$.usage.cache_write_tokens') AS cache_write_tokens,
       json_extract(response_meta, '$.usage.reasoning_tokens') AS reasoning_tokens,
       json_extract(response_meta, '$.response_id') AS response_id,
       json_extract(response_meta, '$.provider_request_id') AS provider_request_id,
       failure_reason,
       json_extract(request_payload, '$.request') AS request,
       json_extract(response_payload, '$.output_text') AS response_text
  FROM calls;

CREATE TABLE IF NOT EXISTS telemetry_events_v1
(
    tenant_id String,
    event_id String,
    idempotency_key String,
    asset_id String,
    agent_id String,
    source_id String,
    source_type LowCardinality(String),
    point_id String,
    point_key String,
    point_ref String,
    source_config_revision String,
    ts DateTime64(3, 'UTC'),
    ingested_at DateTime64(3, 'UTC'),
    event_type LowCardinality(String),
    observation_mode LowCardinality(String),
    value_type LowCardinality(String),
    value_float Nullable(Float64),
    value_bool Nullable(Bool),
    value_string Nullable(String),
    value_raw Nullable(String),
    quality LowCardinality(String),
    sequence UInt64
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (tenant_id, asset_id, source_id, point_key, ts, idempotency_key)
TTL toDateTime(ts) + INTERVAL 180 DAY DELETE;

CREATE TABLE IF NOT EXISTS source_config_snapshots_v1
(
    tenant_id String,
    asset_id String,
    agent_id String,
    source_id String,
    source_type LowCardinality(String),
    source_config_revision String,
    points_json String,
    ts DateTime64(3, 'UTC'),
    ingested_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (tenant_id, asset_id, agent_id, source_id, source_config_revision)
TTL toDateTime(ts) + INTERVAL 400 DAY DELETE;

CREATE TABLE IF NOT EXISTS source_connection_events_v1
(
    tenant_id String,
    asset_id String,
    agent_id String,
    source_id String,
    state LowCardinality(String),
    reason Nullable(String),
    ts DateTime64(3, 'UTC'),
    ingested_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (tenant_id, asset_id, source_id, ts)
TTL toDateTime(ts) + INTERVAL 400 DAY DELETE;

CREATE TABLE IF NOT EXISTS agent_status_events_v1
(
    tenant_id String,
    asset_id String,
    agent_id String,
    status LowCardinality(String),
    ts DateTime64(3, 'UTC'),
    ingested_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ts)
ORDER BY (tenant_id, asset_id, agent_id, ts)
TTL toDateTime(ts) + INTERVAL 400 DAY DELETE;

CREATE TABLE IF NOT EXISTS derived_events_v1
(
    tenant_id String,
    derived_event_id String,
    idempotency_key String,
    asset_id String,
    rule_or_metric_id Nullable(String),
    event_type LowCardinality(String),
    ts DateTime64(3, 'UTC'),
    produced_at DateTime64(3, 'UTC'),
    value_type LowCardinality(String),
    value_float Nullable(Float64),
    value_bool Nullable(Bool),
    value_string Nullable(String),
    source_event_ids_json String,
    attributes_json String
)
ENGINE = ReplacingMergeTree(produced_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (tenant_id, asset_id, event_type, ts, idempotency_key)
TTL toDateTime(ts) + INTERVAL 180 DAY DELETE;

CREATE TABLE IF NOT EXISTS alarm_history_events_v1
(
    tenant_id String,
    alarm_event_id String,
    alarm_id String,
    asset_id String,
    event_type LowCardinality(String),
    severity LowCardinality(String),
    state LowCardinality(String),
    operator_id Nullable(String),
    reason Nullable(String),
    ts DateTime64(3, 'UTC'),
    ingested_at DateTime64(3, 'UTC'),
    payload_json String
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (tenant_id, asset_id, alarm_id, ts, alarm_event_id)
TTL toDateTime(ts) + INTERVAL 5 YEAR DELETE;

CREATE TABLE IF NOT EXISTS kafka_telemetry_events_raw_v1
(
    payload_json String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY ingested_at;

CREATE TABLE IF NOT EXISTS kafka_source_configs_raw_v1
(
    payload_json String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY ingested_at;

CREATE TABLE IF NOT EXISTS kafka_source_connections_raw_v1
(
    payload_json String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY ingested_at;

CREATE TABLE IF NOT EXISTS kafka_agent_status_raw_v1
(
    payload_json String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY ingested_at;

CREATE TABLE IF NOT EXISTS kafka_derived_events_raw_v1
(
    payload_json String,
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY ingested_at;

CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_events_from_raw_mv_v1
TO telemetry_events_v1
AS SELECT
    JSONExtractString(payload_json, 'tenant_id') AS tenant_id,
    JSONExtractString(payload_json, 'event_id') AS event_id,
    JSONExtractString(payload_json, 'idempotency_key') AS idempotency_key,
    JSONExtractString(payload_json, 'asset_id') AS asset_id,
    JSONExtractString(payload_json, 'agent_id') AS agent_id,
    JSONExtractString(payload_json, 'source_id') AS source_id,
    JSONExtractString(payload_json, 'source_type') AS source_type,
    JSONExtractString(payload_json, 'point_id') AS point_id,
    JSONExtractString(payload_json, 'point_key') AS point_key,
    JSONExtractString(payload_json, 'point_ref') AS point_ref,
    JSONExtractString(payload_json, 'source_config_revision') AS source_config_revision,
    parseDateTime64BestEffort(JSONExtractString(payload_json, 'ts'), 3, 'UTC') AS ts,
    parseDateTime64BestEffort(JSONExtractString(payload_json, 'ingested_at'), 3, 'UTC') AS ingested_at,
    JSONExtractString(payload_json, 'event_type') AS event_type,
    JSONExtractString(payload_json, 'observation_mode') AS observation_mode,
    JSONExtractString(payload_json, 'value_type') AS value_type,
    if(value_type = 'number', JSONExtract(payload_json, 'value', 'Nullable(Float64)'), CAST(NULL, 'Nullable(Float64)')) AS value_float,
    if(value_type = 'boolean', JSONExtract(payload_json, 'value', 'Nullable(Bool)'), CAST(NULL, 'Nullable(Bool)')) AS value_bool,
    if(value_type = 'string', JSONExtract(payload_json, 'value', 'Nullable(String)'), CAST(NULL, 'Nullable(String)')) AS value_string,
    if(JSONHas(payload_json, 'value_raw'), JSONExtract(payload_json, 'value_raw', 'Nullable(String)'), CAST(NULL, 'Nullable(String)')) AS value_raw,
    JSONExtractString(payload_json, 'quality') AS quality,
    JSONExtract(payload_json, 'sequence', 'UInt64') AS sequence
FROM kafka_telemetry_events_raw_v1
WHERE throwIf(
    JSONExtractString(payload_json, 'message_type') != 'idp.telemetry.event.v1'
    OR NOT JSONHas(payload_json, 'tenant_id')
    OR NOT JSONHas(payload_json, 'event_id')
    OR NOT JSONHas(payload_json, 'idempotency_key')
    OR NOT JSONHas(payload_json, 'asset_id')
    OR NOT JSONHas(payload_json, 'agent_id')
    OR NOT JSONHas(payload_json, 'source_id')
    OR NOT JSONHas(payload_json, 'source_type')
    OR NOT JSONHas(payload_json, 'point_id')
    OR NOT JSONHas(payload_json, 'point_key')
    OR NOT JSONHas(payload_json, 'point_ref')
    OR NOT JSONHas(payload_json, 'source_config_revision')
    OR NOT JSONHas(payload_json, 'ts')
    OR NOT JSONHas(payload_json, 'ingested_at')
    OR NOT JSONHas(payload_json, 'event_type')
    OR NOT JSONHas(payload_json, 'observation_mode')
    OR NOT JSONHas(payload_json, 'value_type')
    OR NOT JSONHas(payload_json, 'value')
    OR NOT JSONHas(payload_json, 'quality')
    OR NOT JSONHas(payload_json, 'sequence')
    OR JSONExtractString(payload_json, 'tenant_id') = ''
    OR JSONExtractString(payload_json, 'event_id') = ''
    OR JSONExtractString(payload_json, 'idempotency_key') = ''
    OR JSONExtractString(payload_json, 'asset_id') = ''
    OR JSONExtractString(payload_json, 'agent_id') = ''
    OR JSONExtractString(payload_json, 'source_id') = ''
    OR JSONExtractString(payload_json, 'source_type') = ''
    OR JSONExtractString(payload_json, 'point_id') = ''
    OR JSONExtractString(payload_json, 'point_key') = ''
    OR JSONExtractString(payload_json, 'point_ref') = ''
    OR JSONExtractString(payload_json, 'source_config_revision') = ''
    OR JSONExtractString(payload_json, 'event_type') NOT IN ('telemetry.changed', 'telemetry.sample')
    OR JSONExtractString(payload_json, 'observation_mode') NOT IN ('listen', 'read_on_start', 'periodic_read')
    OR JSONExtractString(payload_json, 'value_type') NOT IN ('boolean', 'number', 'string')
    OR JSONExtractString(payload_json, 'quality') NOT IN ('good', 'uncertain', 'bad')
    OR JSONType(payload_json, 'sequence') NOT IN ('Int64', 'UInt64')
    OR JSONExtract(payload_json, 'sequence', 'Int64') < 1
    OR (
        JSONType(payload_json, 'value') != 'Null'
        AND JSONExtractString(payload_json, 'value_type') = 'number'
        AND JSONType(payload_json, 'value') NOT IN ('Int64', 'UInt64', 'Float64', 'Double')
    )
    OR (
        JSONType(payload_json, 'value') != 'Null'
        AND JSONExtractString(payload_json, 'value_type') = 'boolean'
        AND JSONType(payload_json, 'value') != 'Bool'
    )
    OR (
        JSONType(payload_json, 'value') != 'Null'
        AND JSONExtractString(payload_json, 'value_type') = 'string'
        AND JSONType(payload_json, 'value') != 'String'
    ),
    'telemetry raw payload violates idp.telemetry.event.v1 required fields'
) = 0;

CREATE MATERIALIZED VIEW IF NOT EXISTS source_config_snapshots_from_raw_mv_v1
TO source_config_snapshots_v1
AS SELECT
    JSONExtractString(payload_json, 'tenant_id') AS tenant_id,
    JSONExtractString(payload_json, 'asset_id') AS asset_id,
    JSONExtractString(payload_json, 'agent_id') AS agent_id,
    JSONExtractString(payload_json, 'source_id') AS source_id,
    JSONExtractString(payload_json, 'source_type') AS source_type,
    JSONExtractString(payload_json, 'source_config_revision') AS source_config_revision,
    JSONExtractRaw(payload_json, 'points') AS points_json,
    parseDateTime64BestEffort(JSONExtractString(payload_json, 'ts'), 3, 'UTC') AS ts,
    parseDateTime64BestEffort(JSONExtractString(payload_json, 'ingested_at'), 3, 'UTC') AS ingested_at
FROM kafka_source_configs_raw_v1
WHERE throwIf(
    JSONExtractString(payload_json, 'message_type') != 'idp.source.config.v1'
    OR NOT JSONHas(payload_json, 'tenant_id')
    OR NOT JSONHas(payload_json, 'asset_id')
    OR NOT JSONHas(payload_json, 'agent_id')
    OR NOT JSONHas(payload_json, 'source_id')
    OR NOT JSONHas(payload_json, 'source_type')
    OR NOT JSONHas(payload_json, 'source_config_revision')
    OR NOT JSONHas(payload_json, 'points')
    OR NOT JSONHas(payload_json, 'ts')
    OR NOT JSONHas(payload_json, 'ingested_at')
    OR JSONExtractString(payload_json, 'tenant_id') = ''
    OR JSONExtractString(payload_json, 'asset_id') = ''
    OR JSONExtractString(payload_json, 'agent_id') = ''
    OR JSONExtractString(payload_json, 'source_id') = ''
    OR JSONExtractString(payload_json, 'source_type') = ''
    OR JSONExtractString(payload_json, 'source_config_revision') = ''
    OR JSONType(payload_json, 'points') != 'Array',
    'source config raw payload violates idp.source.config.v1 required fields'
) = 0;

CREATE MATERIALIZED VIEW IF NOT EXISTS source_connection_events_from_raw_mv_v1
TO source_connection_events_v1
AS SELECT
    JSONExtractString(payload_json, 'tenant_id') AS tenant_id,
    JSONExtractString(payload_json, 'asset_id') AS asset_id,
    JSONExtractString(payload_json, 'agent_id') AS agent_id,
    JSONExtractString(payload_json, 'source_id') AS source_id,
    JSONExtractString(payload_json, 'state') AS state,
    if(JSONHas(payload_json, 'reason'), JSONExtract(payload_json, 'reason', 'Nullable(String)'), CAST(NULL, 'Nullable(String)')) AS reason,
    parseDateTime64BestEffort(JSONExtractString(payload_json, 'ts'), 3, 'UTC') AS ts,
    parseDateTime64BestEffort(JSONExtractString(payload_json, 'ingested_at'), 3, 'UTC') AS ingested_at
FROM kafka_source_connections_raw_v1
WHERE throwIf(
    JSONExtractString(payload_json, 'message_type') != 'idp.source.connection.v1'
    OR NOT JSONHas(payload_json, 'tenant_id')
    OR NOT JSONHas(payload_json, 'asset_id')
    OR NOT JSONHas(payload_json, 'agent_id')
    OR NOT JSONHas(payload_json, 'source_id')
    OR NOT JSONHas(payload_json, 'state')
    OR NOT JSONHas(payload_json, 'ts')
    OR NOT JSONHas(payload_json, 'ingested_at')
    OR JSONExtractString(payload_json, 'tenant_id') = ''
    OR JSONExtractString(payload_json, 'asset_id') = ''
    OR JSONExtractString(payload_json, 'agent_id') = ''
    OR JSONExtractString(payload_json, 'source_id') = ''
    OR JSONExtractString(payload_json, 'state') NOT IN ('connected', 'disconnected', 'reconnecting'),
    'source connection raw payload violates idp.source.connection.v1 required fields'
) = 0;

CREATE MATERIALIZED VIEW IF NOT EXISTS agent_status_events_from_raw_mv_v1
TO agent_status_events_v1
AS SELECT
    JSONExtractString(payload_json, 'tenant_id') AS tenant_id,
    JSONExtractString(payload_json, 'asset_id') AS asset_id,
    JSONExtractString(payload_json, 'agent_id') AS agent_id,
    JSONExtractString(payload_json, 'status') AS status,
    parseDateTime64BestEffort(JSONExtractString(payload_json, 'ts'), 3, 'UTC') AS ts,
    parseDateTime64BestEffort(JSONExtractString(payload_json, 'ingested_at'), 3, 'UTC') AS ingested_at
FROM kafka_agent_status_raw_v1
WHERE throwIf(
    JSONExtractString(payload_json, 'message_type') != 'idp.agent.status.v1'
    OR NOT JSONHas(payload_json, 'tenant_id')
    OR NOT JSONHas(payload_json, 'asset_id')
    OR NOT JSONHas(payload_json, 'agent_id')
    OR NOT JSONHas(payload_json, 'status')
    OR NOT JSONHas(payload_json, 'ts')
    OR NOT JSONHas(payload_json, 'ingested_at')
    OR JSONExtractString(payload_json, 'tenant_id') = ''
    OR JSONExtractString(payload_json, 'asset_id') = ''
    OR JSONExtractString(payload_json, 'agent_id') = ''
    OR JSONExtractString(payload_json, 'status') NOT IN ('online', 'offline'),
    'agent status raw payload violates idp.agent.status.v1 required fields'
) = 0;

CREATE MATERIALIZED VIEW IF NOT EXISTS derived_events_from_raw_mv_v1
TO derived_events_v1
AS SELECT
    JSONExtractString(payload_json, 'tenant_id') AS tenant_id,
    JSONExtractString(payload_json, 'derived_event_id') AS derived_event_id,
    JSONExtractString(payload_json, 'idempotency_key') AS idempotency_key,
    JSONExtractString(payload_json, 'asset_id') AS asset_id,
    if(JSONHas(payload_json, 'rule_or_metric_id'), JSONExtract(payload_json, 'rule_or_metric_id', 'Nullable(String)'), CAST(NULL, 'Nullable(String)')) AS rule_or_metric_id,
    JSONExtractString(payload_json, 'event_type') AS event_type,
    parseDateTime64BestEffort(JSONExtractString(payload_json, 'ts'), 3, 'UTC') AS ts,
    parseDateTime64BestEffort(JSONExtractString(payload_json, 'produced_at'), 3, 'UTC') AS produced_at,
    JSONExtractString(payload_json, 'value_type') AS value_type,
    if(value_type = 'number', JSONExtract(payload_json, 'value', 'Nullable(Float64)'), CAST(NULL, 'Nullable(Float64)')) AS value_float,
    if(value_type = 'boolean', JSONExtract(payload_json, 'value', 'Nullable(Bool)'), CAST(NULL, 'Nullable(Bool)')) AS value_bool,
    if(value_type = 'string', JSONExtract(payload_json, 'value', 'Nullable(String)'), CAST(NULL, 'Nullable(String)')) AS value_string,
    if(JSONHas(payload_json, 'source_event_ids'), JSONExtractRaw(payload_json, 'source_event_ids'), '[]') AS source_event_ids_json,
    if(JSONHas(payload_json, 'attributes'), JSONExtractRaw(payload_json, 'attributes'), '{}') AS attributes_json
FROM kafka_derived_events_raw_v1
WHERE throwIf(
    JSONExtractString(payload_json, 'message_type') != 'idp.derived.event.v1'
    OR NOT JSONHas(payload_json, 'tenant_id')
    OR NOT JSONHas(payload_json, 'derived_event_id')
    OR NOT JSONHas(payload_json, 'idempotency_key')
    OR NOT JSONHas(payload_json, 'asset_id')
    OR NOT JSONHas(payload_json, 'event_type')
    OR NOT JSONHas(payload_json, 'ts')
    OR NOT JSONHas(payload_json, 'produced_at')
    OR NOT JSONHas(payload_json, 'value_type')
    OR NOT JSONHas(payload_json, 'value')
    OR JSONExtractString(payload_json, 'tenant_id') = ''
    OR JSONExtractString(payload_json, 'derived_event_id') = ''
    OR JSONExtractString(payload_json, 'idempotency_key') = ''
    OR JSONExtractString(payload_json, 'asset_id') = ''
    OR JSONExtractString(payload_json, 'event_type') = ''
    OR JSONExtractString(payload_json, 'value_type') NOT IN ('boolean', 'number', 'string')
    OR (
        JSONHas(payload_json, 'rule_or_metric_id')
        AND JSONType(payload_json, 'rule_or_metric_id') NOT IN ('String', 'Null')
    )
    OR (
        JSONHas(payload_json, 'source_event_ids')
        AND JSONType(payload_json, 'source_event_ids') != 'Array'
    )
    OR (
        JSONHas(payload_json, 'attributes')
        AND JSONType(payload_json, 'attributes') != 'Object'
    )
    OR (
        JSONType(payload_json, 'value') != 'Null'
        AND JSONExtractString(payload_json, 'value_type') = 'number'
        AND JSONType(payload_json, 'value') NOT IN ('Int64', 'UInt64', 'Float64', 'Double')
    )
    OR (
        JSONType(payload_json, 'value') != 'Null'
        AND JSONExtractString(payload_json, 'value_type') = 'boolean'
        AND JSONType(payload_json, 'value') != 'Bool'
    )
    OR (
        JSONType(payload_json, 'value') != 'Null'
        AND JSONExtractString(payload_json, 'value_type') = 'string'
        AND JSONType(payload_json, 'value') != 'String'
    ),
    'derived event raw payload violates idp.derived.event.v1 required fields'
) = 0;

CREATE VIEW IF NOT EXISTS telemetry_events_dedup_v1
AS SELECT
    tenant_id,
    event_id,
    idempotency_key,
    asset_id,
    agent_id,
    source_id,
    source_type,
    point_id,
    point_key,
    point_ref,
    source_config_revision,
    ts,
    ingested_at,
    event_type,
    observation_mode,
    value_type,
    value_float,
    value_bool,
    value_string,
    value_raw,
    quality,
    sequence
FROM telemetry_events_v1 FINAL;

CREATE VIEW IF NOT EXISTS telemetry_latest_v1
AS SELECT
    tenant_id,
    event_id,
    idempotency_key,
    asset_id,
    agent_id,
    source_id,
    source_type,
    point_id,
    point_key,
    point_ref,
    source_config_revision,
    ts,
    ingested_at,
    event_type,
    observation_mode,
    value_type,
    value_float,
    value_bool,
    value_string,
    value_raw,
    quality,
    sequence
FROM telemetry_events_dedup_v1
ORDER BY
    tenant_id ASC,
    asset_id ASC,
    source_id ASC,
    point_key ASC,
    ts DESC,
    ingested_at DESC
LIMIT 1 BY tenant_id, asset_id, source_id, point_key;

CREATE VIEW IF NOT EXISTS telemetry_1m_v1
AS SELECT
    tenant_id,
    asset_id,
    source_id,
    point_key,
    toStartOfMinute(ts) AS bucket_start,
    argMax(agent_id, ts) AS agent_id,
    argMax(source_type, ts) AS source_type,
    argMax(point_id, ts) AS point_id,
    argMax(point_ref, ts) AS point_ref,
    argMax(source_config_revision, ts) AS source_config_revision,
    min(ts) AS first_ts,
    max(ts) AS last_ts,
    count() AS event_count,
    countIf(quality = 'good') AS good_count,
    countIf(quality = 'uncertain') AS uncertain_count,
    countIf(quality = 'bad') AS bad_count,
    countIf(value_type = 'number' AND isNotNull(value_float)) AS number_count,
    minIf(value_float, value_type = 'number' AND isNotNull(value_float)) AS value_min,
    maxIf(value_float, value_type = 'number' AND isNotNull(value_float)) AS value_max,
    avgIf(value_float, value_type = 'number' AND isNotNull(value_float)) AS value_avg,
    argMaxIf(value_float, ts, value_type = 'number' AND isNotNull(value_float)) AS value_last
FROM telemetry_events_dedup_v1
GROUP BY
    tenant_id,
    asset_id,
    source_id,
    point_key,
    bucket_start;

CREATE VIEW IF NOT EXISTS telemetry_1h_v1
AS SELECT
    tenant_id,
    asset_id,
    source_id,
    point_key,
    toStartOfHour(ts) AS bucket_start,
    argMax(agent_id, ts) AS agent_id,
    argMax(source_type, ts) AS source_type,
    argMax(point_id, ts) AS point_id,
    argMax(point_ref, ts) AS point_ref,
    argMax(source_config_revision, ts) AS source_config_revision,
    min(ts) AS first_ts,
    max(ts) AS last_ts,
    count() AS event_count,
    countIf(quality = 'good') AS good_count,
    countIf(quality = 'uncertain') AS uncertain_count,
    countIf(quality = 'bad') AS bad_count,
    countIf(value_type = 'number' AND isNotNull(value_float)) AS number_count,
    minIf(value_float, value_type = 'number' AND isNotNull(value_float)) AS value_min,
    maxIf(value_float, value_type = 'number' AND isNotNull(value_float)) AS value_max,
    avgIf(value_float, value_type = 'number' AND isNotNull(value_float)) AS value_avg,
    argMaxIf(value_float, ts, value_type = 'number' AND isNotNull(value_float)) AS value_last
FROM telemetry_events_dedup_v1
GROUP BY
    tenant_id,
    asset_id,
    source_id,
    point_key,
    bucket_start;

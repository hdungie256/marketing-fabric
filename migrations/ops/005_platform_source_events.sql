CREATE TABLE ops.source_events (
    event_id text PRIMARY KEY,
    emitted_at timestamptz NOT NULL,
    source text NOT NULL,
    keys jsonb NOT NULL,
    source_version bigint NOT NULL,
    dag_run_id text
);

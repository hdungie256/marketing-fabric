-- depends: 001_platform_runs_alerts_reconciliation

CREATE TABLE ops.metric_change_log (
    change_id bigserial PRIMARY KEY,
    run_id text NOT NULL REFERENCES ops.runs (run_id),
    event_id text,
    dataset_id text NOT NULL,
    grain_key jsonb NOT NULL,
    term_id text NOT NULL,
    old_value numeric,
    new_value numeric,
    recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX metric_change_log_event ON ops.metric_change_log (event_id);

ALTER TABLE ops.runs ADD COLUMN delta_version_before bigint;

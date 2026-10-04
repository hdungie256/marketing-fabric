CREATE TABLE ops.runs (
    run_id text PRIMARY KEY,
    job_id text NOT NULL,
    event_id text,
    scope jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('running', 'success', 'failed', 'gated')),
    started_at timestamptz NOT NULL,
    ended_at timestamptz,
    rows_in bigint,
    rows_out bigint,
    failing_step text,
    delta_version bigint
);

CREATE TABLE ops.alerts (
    alert_id bigserial PRIMARY KEY,
    run_id text NOT NULL REFERENCES ops.runs (run_id),
    job_id text NOT NULL,
    severity text NOT NULL CHECK (severity IN ('critical', 'warning')),
    message text NOT NULL,
    raised_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ops.load_reconciliation (
    load_id text NOT NULL,
    dataset_id text NOT NULL,
    run_id text NOT NULL REFERENCES ops.runs (run_id),
    source_rows bigint NOT NULL,
    raw_rows bigint NOT NULL,
    baseline_rows bigint,
    source_checksum text NOT NULL,
    raw_checksum text NOT NULL,
    passed boolean NOT NULL,
    reason text,
    checked_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (load_id, dataset_id)
);

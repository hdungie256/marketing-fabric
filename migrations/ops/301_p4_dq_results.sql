CREATE TABLE ops.dq_results (
    run_id text NOT NULL,
    dataset_id text NOT NULL,
    rule_id text NOT NULL,
    severity text NOT NULL CHECK (severity IN ('critical', 'warning')),
    passed boolean NOT NULL,
    detail text,
    score_pct numeric(5, 2) NOT NULL,
    status text NOT NULL CHECK (status IN ('Green', 'Amber', 'Red')),
    scope jsonb NOT NULL,
    checked_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, dataset_id, rule_id)
);

CREATE INDEX dq_results_dataset_checked ON ops.dq_results (dataset_id, checked_at DESC);

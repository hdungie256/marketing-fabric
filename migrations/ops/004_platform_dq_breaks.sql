CREATE TABLE ops.dq_breaks (
    dataset_id text PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now()
);

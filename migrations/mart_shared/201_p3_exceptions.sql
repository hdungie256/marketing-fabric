-- depends: 000_create_schemas
CREATE TABLE IF NOT EXISTS mart_shared.exceptions (
    exception_id text PRIMARY KEY,
    class text NOT NULL,
    natural_key text NOT NULL,
    dataset_id text NOT NULL,
    detail text,
    detected_at timestamptz NOT NULL,
    provenance text NOT NULL,
    _refreshed_at timestamptz NOT NULL,
    _run_id text NOT NULL,
    _source_version jsonb NOT NULL
);

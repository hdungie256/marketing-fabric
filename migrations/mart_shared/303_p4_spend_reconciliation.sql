-- depends: 000_create_schemas
CREATE TABLE mart_shared.spend_reconciliation (
    date date NOT NULL,
    online_spend numeric(18,2) NOT NULL,
    offline_spend numeric(18,2) NOT NULL,
    allocated numeric(18,2) NOT NULL,
    unallocated numeric(18,2) NOT NULL,
    provenance text NOT NULL,
    _refreshed_at timestamptz NOT NULL,
    _run_id text NOT NULL,
    _source_version jsonb NOT NULL,
    PRIMARY KEY (date),
    CHECK (allocated + unallocated = online_spend)
);

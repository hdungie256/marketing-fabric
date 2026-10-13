-- depends: 000_create_schemas
CREATE TABLE mart_shared.campaign_spend_allocated (
    campaign_id text NOT NULL,
    date date NOT NULL,
    allocated numeric(18,2) NOT NULL,
    provenance text NOT NULL,
    _refreshed_at timestamptz NOT NULL,
    _run_id text NOT NULL,
    _source_version jsonb NOT NULL,
    PRIMARY KEY (campaign_id, date)
);

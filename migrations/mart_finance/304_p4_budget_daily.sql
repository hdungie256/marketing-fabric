-- depends: 000_create_schemas
CREATE TABLE mart_finance.budget_daily (
    campaign_id text NOT NULL,
    date date NOT NULL,
    campaign_name text NOT NULL,
    channel text NOT NULL,
    campaign_budget numeric(18,2) NOT NULL,
    allocated numeric(18,2) NOT NULL,
    attributed_orders integer NOT NULL,
    attributed_gross_value numeric(18,2) NOT NULL,
    provenance text NOT NULL,
    _refreshed_at timestamptz NOT NULL,
    _run_id text NOT NULL,
    _source_version jsonb NOT NULL,
    PRIMARY KEY (campaign_id, date)
);

-- depends: 000_create_schemas
CREATE TABLE mart_finance.contribution (
    campaign_id text NOT NULL,
    campaign_name text NOT NULL,
    attributed_gross_value numeric(18,2) NOT NULL,
    reference_cogs numeric(18,2) NOT NULL,
    campaign_cost numeric(18,2) NOT NULL,
    estimated_contribution numeric(18,2) NOT NULL,
    skus_without_cost integer NOT NULL,
    provenance text NOT NULL,
    _refreshed_at timestamptz NOT NULL,
    _run_id text NOT NULL,
    _source_version jsonb NOT NULL,
    PRIMARY KEY (campaign_id)
);

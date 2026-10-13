-- depends: 000_create_schemas
CREATE TABLE mart_finance.contribution_sku (
    campaign_id text NOT NULL,
    product_sku text NOT NULL,
    product_description text NOT NULL,
    quantity bigint NOT NULL,
    attributed_gross_value numeric(18,2) NOT NULL,
    estimated_unit_cost numeric(18,2),
    reference_cogs numeric(18,2),
    cost_available boolean NOT NULL,
    provenance text NOT NULL,
    _refreshed_at timestamptz NOT NULL,
    _run_id text NOT NULL,
    _source_version jsonb NOT NULL,
    PRIMARY KEY (campaign_id, product_sku)
);

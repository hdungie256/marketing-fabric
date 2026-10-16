-- depends: 000_create_schemas
CREATE TABLE mart_campaign.product_sales (
    month date NOT NULL,
    campaign_id text NOT NULL,
    campaign_name text NOT NULL,
    product_sku text NOT NULL,
    product_description text NOT NULL,
    canonical_category text NOT NULL,
    quantity integer NOT NULL,
    gross_value numeric(18,2) NOT NULL,
    provenance text NOT NULL,
    _refreshed_at timestamptz NOT NULL,
    _run_id text NOT NULL,
    _source_version jsonb NOT NULL,
    PRIMARY KEY (month, campaign_id, product_sku)
);

COMMENT ON TABLE mart_campaign.product_sales IS
    'Sparse: only months and SKUs with sales. The ALL rows include sales not attributed to any campaign.';

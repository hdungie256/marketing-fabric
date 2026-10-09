-- depends: 000_create_schemas
CREATE TABLE mart_shared.campaign_attributed_daily (
    campaign_id text NOT NULL,
    date date NOT NULL,
    attributed_orders integer NOT NULL,
    attributed_gross_value numeric(18,2) NOT NULL,
    buyers integer NOT NULL,
    first_observed_buyers integer NOT NULL,
    provenance text NOT NULL,
    _refreshed_at timestamptz NOT NULL,
    _run_id text NOT NULL,
    _source_version jsonb NOT NULL,
    PRIMARY KEY (campaign_id, date)
);

COMMENT ON COLUMN mart_shared.campaign_attributed_daily.buyers IS
    'Distinct customers within the day. Not additive across days; use campaign_attributed_orders for a period.';

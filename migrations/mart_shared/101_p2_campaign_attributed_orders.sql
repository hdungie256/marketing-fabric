-- depends: 000_create_schemas
CREATE TABLE mart_shared.campaign_attributed_orders (
    order_key text NOT NULL,
    campaign_id text NOT NULL,
    date date NOT NULL,
    customer_id bigint NOT NULL,
    gross_value numeric(18,2) NOT NULL,
    is_first_observed boolean NOT NULL,
    provenance text NOT NULL,
    _refreshed_at timestamptz NOT NULL,
    _run_id text NOT NULL,
    _source_version jsonb NOT NULL,
    PRIMARY KEY (order_key)
);

CREATE INDEX campaign_attributed_orders_campaign_date_idx
    ON mart_shared.campaign_attributed_orders (campaign_id, date);

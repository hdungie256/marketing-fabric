-- depends: 000_create_schemas
CREATE TABLE mart_customer.rfm (
    customer_id bigint NOT NULL,
    recency_days integer NOT NULL,
    recency_score smallint NOT NULL,
    frequency_orders integer NOT NULL,
    frequency_score smallint NOT NULL,
    monetary_value numeric(18,2) NOT NULL,
    monetary_score smallint NOT NULL,
    segment text NOT NULL,
    categories text NOT NULL,
    gender text,
    location text,
    tenure_months integer,
    provenance text NOT NULL,
    _refreshed_at timestamptz NOT NULL,
    _run_id text NOT NULL,
    _source_version jsonb NOT NULL,
    PRIMARY KEY (customer_id)
);

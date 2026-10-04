CREATE SCHEMA IF NOT EXISTS meta;

CREATE TABLE IF NOT EXISTS meta.source_versions (
    source text PRIMARY KEY,
    version bigint NOT NULL
);

CREATE SCHEMA IF NOT EXISTS sales;

CREATE SCHEMA IF NOT EXISTS crm;

CREATE SCHEMA IF NOT EXISTS erp;

CREATE SCHEMA IF NOT EXISTS campaign;

CREATE SCHEMA IF NOT EXISTS promotion;

CREATE SCHEMA IF NOT EXISTS spend;

CREATE TABLE IF NOT EXISTS sales.sales_lines (
    sales_line_id text NOT NULL,
    canonical_order_id text NOT NULL,
    transaction_date_iso date NOT NULL,
    customer_id bigint NOT NULL,
    transaction_id bigint NOT NULL,
    transaction_date text NOT NULL,
    product_sku text NOT NULL,
    product_description text NOT NULL,
    product_category text NOT NULL,
    quantity integer NOT NULL,
    avg_price numeric(18,2) NOT NULL,
    delivery_charges numeric(18,2) NOT NULL,
    coupon_status text NOT NULL,
    provenance text NOT NULL,
    PRIMARY KEY (sales_line_id)
);

CREATE TABLE IF NOT EXISTS crm.customers (
    customer_id bigint NOT NULL,
    gender text NOT NULL,
    location text NOT NULL,
    tenure_months integer NOT NULL,
    provenance text NOT NULL,
    PRIMARY KEY (customer_id)
);

CREATE TABLE IF NOT EXISTS erp.product_costs (
    product_sku text NOT NULL,
    product_category text NOT NULL,
    observed_avg_price numeric(18,4) NOT NULL,
    estimated_unit_cost numeric(18,2) NOT NULL,
    valid_from date NOT NULL,
    valid_through date NOT NULL,
    provenance text NOT NULL,
    provenance_note text NOT NULL,
    PRIMARY KEY (product_sku)
);

CREATE TABLE IF NOT EXISTS campaign.campaigns (
    campaign_id text NOT NULL,
    campaign_name text NOT NULL,
    channel text NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    target_category text NOT NULL,
    objective text NOT NULL,
    budget numeric(18,2) NOT NULL,
    provenance text NOT NULL,
    provenance_note text NOT NULL,
    PRIMARY KEY (campaign_id)
);

CREATE TABLE IF NOT EXISTS campaign.targets (
    campaign_id text NOT NULL,
    target_metric text NOT NULL,
    target_value numeric(18,2) NOT NULL,
    evaluation_from date NOT NULL,
    evaluation_through date NOT NULL,
    target_note text NOT NULL,
    provenance text NOT NULL,
    provenance_note text NOT NULL,
    PRIMARY KEY (campaign_id)
);

CREATE TABLE IF NOT EXISTS campaign.attribution (
    canonical_order_id text NOT NULL,
    customer_id bigint NOT NULL,
    transaction_id bigint NOT NULL,
    transaction_date_iso date NOT NULL,
    campaign_id text NOT NULL,
    matched_category text NOT NULL,
    attribution_rule text NOT NULL,
    provenance text NOT NULL,
    provenance_note text NOT NULL,
    PRIMARY KEY (canonical_order_id)
);

CREATE TABLE IF NOT EXISTS promotion.coupon_plan (
    month text NOT NULL,
    product_category text NOT NULL,
    coupon_code text NOT NULL,
    discount_pct integer NOT NULL,
    provenance text NOT NULL,
    PRIMARY KEY (month, product_category)
);

CREATE TABLE IF NOT EXISTS spend.campaign_spend (
    date_iso date NOT NULL,
    campaign_id text NOT NULL,
    allocated_online_spend numeric(18,2) NOT NULL,
    basis text NOT NULL,
    provenance text NOT NULL,
    provenance_note text NOT NULL,
    PRIMARY KEY (date_iso, campaign_id)
);

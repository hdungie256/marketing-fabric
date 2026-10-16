-- depends: 000_create_schemas
CREATE TABLE mart_campaign.new_returning (
    period_id text NOT NULL,
    period_label text NOT NULL,
    period_start date NOT NULL,
    period_end date NOT NULL,
    campaign_id text NOT NULL,
    campaign_name text NOT NULL,
    attributed_buyers integer NOT NULL,
    first_observed_buyers integer NOT NULL,
    returning_buyers integer NOT NULL,
    provenance text NOT NULL,
    _refreshed_at timestamptz NOT NULL,
    _run_id text NOT NULL,
    _source_version jsonb NOT NULL,
    PRIMARY KEY (period_id, campaign_id)
);

COMMENT ON COLUMN mart_campaign.new_returning.attributed_buyers IS
    'Distinct customers in the period; the ALL row is distinct across campaigns, not a sum.';

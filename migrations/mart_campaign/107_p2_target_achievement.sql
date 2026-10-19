-- depends: 000_create_schemas
CREATE TABLE mart_campaign.target_achievement (
    campaign_id text NOT NULL,
    campaign_name text NOT NULL,
    target_metric text NOT NULL,
    target_value numeric(18,2) NOT NULL,
    evaluation_from date NOT NULL,
    evaluation_through date NOT NULL,
    actual numeric(18,2) NOT NULL,
    achievement numeric(9,6) NOT NULL,
    allocated_spend numeric(18,2) NOT NULL,
    recommendation text NOT NULL,
    provenance text NOT NULL,
    _refreshed_at timestamptz NOT NULL,
    _run_id text NOT NULL,
    _source_version jsonb NOT NULL,
    PRIMARY KEY (campaign_id)
);

COMMENT ON COLUMN mart_campaign.target_achievement.achievement IS
    'actual / target_value over the target evaluation window; thresholds applied to the unrounded ratio.';

"""New vs Returning (BR06): read the mart view and reshape for the chart; no metric math here (AD-11)."""

import pandas as pd

from app.shell import DataSource

DATASET = "mart_campaign.new_returning"
BUYER_TYPES = {"first_observed_buyers": "First observed", "returning_buyers": "Returning"}


def load(source: DataSource) -> pd.DataFrame:
    return source.read(DATASET)


def stack(rows: pd.DataFrame) -> pd.DataFrame:
    long = rows.melt(id_vars="campaign_id", value_vars=list(BUYER_TYPES), var_name="buyer_type", value_name="buyers")
    return long.assign(buyer_type=long["buyer_type"].map(BUYER_TYPES))

"""New vs Returning (BR06): read the mart view and reshape for the chart; no metric math here (AD-11).

Period and campaign pickers read this mart's own rows, not the Overview mart, so the two pages cannot
drift apart when their marts refresh at different times.
"""

import pandas as pd

from app.shell import DataSource

DATASET = "mart_campaign.new_returning"
ALL = "ALL"
BUYER_TYPES = {"first_observed_buyers": "First observed", "returning_buyers": "Returning"}


def load(source: DataSource) -> pd.DataFrame:
    return source.read(DATASET)


def periods(df: pd.DataFrame) -> list[tuple[str, str]]:
    p = df.drop_duplicates("period_id").sort_values(["period_start", "period_end"], ascending=[True, False])
    return list(zip(p["period_id"], p["period_label"], strict=True))


def campaigns(df: pd.DataFrame) -> list[tuple[str, str]]:
    names = df.drop_duplicates("campaign_id").set_index("campaign_id")["campaign_name"]
    return [(ALL, names[ALL]), *((c, names[c]) for c in sorted(names.index) if c != ALL)]


def select(df: pd.DataFrame, period_id: str, campaign_id: str) -> tuple[pd.Series, pd.DataFrame]:
    rows = df[df["period_id"] == period_id]
    kpi = rows[rows["campaign_id"] == campaign_id]
    if len(kpi) != 1:
        raise KeyError(f"{DATASET}: no row for ({period_id}, {campaign_id})")
    table = rows[rows["campaign_id"] != ALL] if campaign_id == ALL else kpi
    return kpi.iloc[0], table.sort_values("campaign_id")


def first_observed_share(rows: pd.DataFrame) -> pd.Series:
    """First observed buyers as a share of attributed buyers (presentation ratio; blank when no buyers)."""
    buyers = rows["attributed_buyers"].where(rows["attributed_buyers"] > 0)
    return rows["first_observed_buyers"] / buyers


def stack(rows: pd.DataFrame) -> pd.DataFrame:
    long = rows.melt(id_vars="campaign_id", value_vars=list(BUYER_TYPES), var_name="buyer_type", value_name="buyers")
    return long.assign(buyer_type=long["buyer_type"].map(BUYER_TYPES))

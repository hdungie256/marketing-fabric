"""Campaign Overview (BR01): read the overview view and pick rows; no metric math here (AD-11)."""

import pandas as pd

from app.shell import DataSource

DATASET = "mart_campaign.campaign_overview"
ALL = "ALL"
MONEY = ("attributed_gross_value", "average_order_value")


def load(source: DataSource) -> pd.DataFrame:
    return source.read(DATASET).astype({c: "float64" for c in MONEY})


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

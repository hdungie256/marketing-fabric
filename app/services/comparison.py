"""Campaign Comparison (BR02): read the comparison view and pick rows; no metric math here (AD-11)."""

import pandas as pd

from app.services.campaign_overview import periods
from app.shell import DataSource

__all__ = ["DATASET", "METRICS", "load", "periods", "select"]

DATASET = "mart_campaign.comparison"
METRICS = ["attributed_gross_value", "attributed_orders", "attributed_buyers", "average_order_value"]
MONEY = ("attributed_gross_value", "average_order_value")


def load(source: DataSource) -> pd.DataFrame:
    return source.read(DATASET).astype({c: "float64" for c in MONEY})


def select(df: pd.DataFrame, period_id: str, compare_by: str) -> pd.DataFrame:
    rows = df[(df["period_id"] == period_id) & (df["compare_by"] == compare_by)]
    return rows.sort_values("group_id")

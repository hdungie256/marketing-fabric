"""Products & Categories (BR03): filter and additive sums only; the mart owns the metric logic (AD-11)."""

import pandas as pd

from app.shell import DataSource
from pipelines.jobs.marts.campaign.campaign_overview.transforms import periods

DATASET = "mart_campaign.product_sales"
SKU = ["product_sku", "product_description", "canonical_category"]


def load(source: DataSource) -> pd.DataFrame:
    return source.read(DATASET).astype({"gross_value": "float64"})


def _periods(df: pd.DataFrame):
    return periods({m.year for m in df["month"]})


def period_options(df: pd.DataFrame) -> list[tuple[str, str]]:
    return [(pid, label) for pid, label, _, _ in _periods(df)]


def select(df: pd.DataFrame, period_id: str, campaign_id: str) -> pd.DataFrame:
    start, end = next((s, e) for pid, _, s, e in _periods(df) if pid == period_id)
    months = df["month"].map(lambda m: start <= m <= end)
    return df[months & (df["campaign_id"] == campaign_id)]


def top_skus(rows: pd.DataFrame, by: str, n: int = 10) -> pd.DataFrame:
    sums = rows.groupby(SKU, as_index=False)[["quantity", "gross_value"]].sum()
    return sums.sort_values(by, ascending=False).head(n).reset_index(drop=True)


def top_categories(rows: pd.DataFrame, by: str) -> pd.DataFrame:
    sums = rows.groupby("canonical_category", as_index=False)[["quantity", "gross_value"]].sum()
    return sums.sort_values(by, ascending=False).reset_index(drop=True)


def trend(rows: pd.DataFrame, n: int = 4) -> pd.DataFrame:
    top = top_categories(rows, "gross_value")["canonical_category"].head(n)
    kept = rows[rows["canonical_category"].isin(top)]
    out = kept.groupby(["month", "canonical_category"], as_index=False)[["gross_value", "quantity"]].sum()
    return out.assign(month=pd.to_datetime(out["month"]))

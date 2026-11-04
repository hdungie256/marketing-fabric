"""Products & Categories (BR03): filter and additive sums only; the mart owns the metric logic (AD-11)."""

import pandas as pd

from app.shell import DataSource
from pipelines.jobs.marts.campaign.campaign_overview.transforms import periods

DATASET = "mart_campaign.product_sales"
ALL = "ALL"
TOP_SKUS = [5, 10, 20]
TREND_CATEGORIES = [3, 4, 6]


def load(source: DataSource) -> pd.DataFrame:
    return source.read(DATASET).astype({"gross_value": "float64"})


def campaigns(df: pd.DataFrame) -> list[tuple[str, str]]:
    """Campaign picker from this mart's own rows (not the Overview mart's)."""
    names = df.drop_duplicates("campaign_id").set_index("campaign_id")["campaign_name"]
    return [(ALL, names[ALL]), *((c, names[c]) for c in sorted(names.index) if c != ALL)]


def _periods(df: pd.DataFrame):
    return periods({m.year for m in df["month"]})


def period_options(df: pd.DataFrame) -> list[tuple[str, str]]:
    return [(pid, label) for pid, label, _, _ in _periods(df)]


def select(df: pd.DataFrame, period_id: str, campaign_id: str) -> pd.DataFrame:
    start, end = next((s, e) for pid, _, s, e in _periods(df) if pid == period_id)
    months = df["month"].map(lambda m: start <= m <= end)
    return df[months & (df["campaign_id"] == campaign_id)]


def top_skus(rows: pd.DataFrame, by: str, n: int = 10) -> pd.DataFrame:
    sums = rows.groupby("product_sku", as_index=False).agg(
        product_description=("product_description", "min"),
        canonical_category=("canonical_category", "min"),
        quantity=("quantity", "sum"),
        gross_value=("gross_value", "sum"),
    )
    return sums.sort_values(by, ascending=False).head(n).reset_index(drop=True)


def top_categories(rows: pd.DataFrame, by: str) -> pd.DataFrame:
    sums = rows.groupby("canonical_category", as_index=False)[["quantity", "gross_value"]].sum()
    return sums.sort_values(by, ascending=False).reset_index(drop=True)


def share(sums: pd.DataFrame, by: str) -> pd.Series:
    """Each row's share of the column total (presentation ratio over additive sums)."""
    total = sums[by].sum()
    if not total:
        return pd.Series(float("nan"), index=sums.index)
    return sums[by] / total


def trend(rows: pd.DataFrame, n: int = 4, by: str = "gross_value") -> pd.DataFrame:
    top = top_categories(rows, by)["canonical_category"].head(n)
    kept = rows[rows["canonical_category"].isin(top)]
    out = kept.groupby(["month", "canonical_category"], as_index=False)[["gross_value", "quantity"]].sum()
    return out.assign(month=pd.to_datetime(out["month"]))

"""Customers (BR05/BR08/BR09): read the RFM view and filter in pandas; the mart owns the math (AD-11)."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pandas as pd

from app.shell import DataSource

DATASET = "mart_customer.rfm"
SEGMENTS_TABLE = "app.segments"
ALL = "All"

SEGMENT_ORDER = [
    "Champions",
    "Can't Lose",
    "At Risk",
    "Loyal",
    "Potential Loyalist",
    "Recent First Buyers",
    "Needs Attention",
    "Hibernating",
    "Lost",
]

MONEY = ("monetary_value",)


def load(source: DataSource) -> pd.DataFrame:
    df = source.read(DATASET)
    money = [c for c in MONEY if c in df.columns]
    return df.astype({c: "float64" for c in money})


def buyer_count(df: pd.DataFrame) -> int:
    return int(df["customer_id"].nunique())


def category_options(df: pd.DataFrame) -> list[str]:
    cats: set[str] = set()
    for raw in df["categories"].fillna(""):
        cats.update(c for c in str(raw).split(",") if c)
    return sorted(cats)


def has_category(categories: str, category: str) -> bool:
    return category in str(categories).split(",") if category != ALL else True


def segment_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-segment buyer counts and shares in canonical segment order."""
    counts = df.groupby("segment", observed=True).size().reset_index(name="customers")
    counts["share"] = counts["customers"] / counts["customers"].sum()
    counts["segment"] = pd.Categorical(counts["segment"], categories=SEGMENT_ORDER, ordered=True)
    return counts.sort_values("segment").reset_index(drop=True)[["segment", "customers", "share"]]


def match(df: pd.DataFrame, segment: str = ALL, category: str = ALL, min_orders: int = 0) -> pd.DataFrame:
    """Audience criteria: segment × purchased category × purchase history (min technical orders)."""
    out = df
    if segment != ALL:
        out = out[out["segment"] == segment]
    if category != ALL:
        out = out[out["categories"].map(lambda raw: has_category(raw, category))]
    if min_orders > 0:
        out = out[out["frequency_orders"] >= min_orders]
    return out.sort_values("customer_id").reset_index(drop=True)


def win_back(df: pd.DataFrame, category: str = ALL) -> pd.DataFrame:
    """Lapsed high-value buyers: (F = 5 or M = 5) and R = 1 (FR-33a)."""
    out = df[((df["frequency_score"] == 5) | (df["monetary_score"] == 5)) & (df["recency_score"] == 1)]
    if category != ALL:
        out = out[out["categories"].map(lambda raw: has_category(raw, category))]
    return out.sort_values("customer_id").reset_index(drop=True)


def criteria(segment: str = ALL, category: str = ALL, min_orders: int = 0) -> dict[str, Any]:
    return {"segment": segment, "category": category, "min_orders": min_orders}


def new_audience_id() -> str:
    return uuid.uuid4().hex


def save_audience(conn: Any, name: str, crit: dict[str, Any], count: int, by: str) -> str:
    """Insert one saved audience via app_writer. Returns the audience id."""
    audience_id = new_audience_id()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO app.segments (audience_id, name, criteria, customer_count, created_by)"
            " VALUES (%s, %s, %s, %s, %s)",
            (audience_id, name, json.dumps(crit, sort_keys=True), count, by),
        )
    return audience_id


def read_audiences(conn: Any) -> pd.DataFrame:
    cursor = conn.execute(
        "SELECT audience_id, name, criteria, customer_count, created_by, created_at"
        " FROM app_v.segments ORDER BY created_at DESC"
    )
    return pd.DataFrame(cursor.fetchall(), columns=[d.name for d in cursor.description])

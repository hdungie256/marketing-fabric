"""Targets (BR12): read the mart view, sort and word it; no metric math here (AD-11)."""

import pandas as pd

import fabric_control
from app.shell import DataSource, fmt_count, fmt_money

DATASET = "mart_campaign.target_achievement"
RULER_MAX = 1.3


def load(source: DataSource) -> pd.DataFrame:
    return source.read(DATASET)


def goal_text(metric: str, target: float) -> str:
    if metric == "attributed_gross_value":
        return f"Goal: {float(target) / 1000:.1f}k in sales"
    unit = "new buyers" if metric == "first_observed_buyers" else "orders"
    return f"Goal: {fmt_count(target)} {unit}"


def detail_text(metric: str, actual: float, target: float, spend: float) -> str:
    name = fabric_control.term(metric)["display_name"]
    return f"{fmt_count(actual)} of {fmt_count(target)} {name}. Spent {fmt_money(spend)}"


def rows(df: pd.DataFrame) -> pd.DataFrame:
    out = df.assign(achievement=df["achievement"].astype(float)).sort_values(["achievement", "campaign_id"])
    return out.assign(
        goal=[goal_text(m, t) for m, t in zip(out["target_metric"], out["target_value"], strict=True)],
        detail=[
            detail_text(m, a, t, s)
            for m, a, t, s in zip(
                out["target_metric"], out["actual"], out["target_value"], out["allocated_spend"], strict=True
            )
        ],
    ).reset_index(drop=True)

from decimal import Decimal

import altair as alt
import pandas as pd
import streamlit as st

from app.shell import SERIES_NEUTRAL, Filter, current_source, empty_state, filter_bar, metric, table

BUDGET = "mart_finance.budget_daily"
RECON = "mart_shared.spend_reconciliation"
ALL = "All campaigns"
ACCENT = "#2F5BEA"  # DESIGN.md colors.accent
SURFACE = "#FFFFFF"  # DESIGN.md colors.surface: the 2px gap between segments
SEGMENTS = {"allocated": "Allocated", "unallocated": "Unallocated"}
LABELLED_DAYS = 31


def ratio(numerator, denominator):
    return None if not denominator else Decimal(str(numerator)) / Decimal(str(denominator))


def summarize(days: pd.DataFrame, recon: pd.DataFrame) -> dict:
    """Ratios of sums over the selection; the budget is counted once per campaign, never summed into cost (R8)."""
    allocated = days["allocated"].sum()
    return {
        "campaign_budget": days.groupby("campaign_id")["campaign_budget"].max().sum(),
        "allocated_spend": allocated,
        "unallocated_spend": recon["unallocated"].sum(),
        "attributed_value_per_spend_ratio": ratio(days["attributed_gross_value"].sum(), allocated),
        "cost_per_attributed_order": ratio(allocated, days["attributed_orders"].sum()),
    }


def by_campaign(days: pd.DataFrame) -> pd.DataFrame:
    grouped = days.groupby(["campaign_id", "campaign_name"], as_index=False).agg(
        campaign_budget=("campaign_budget", "max"),
        allocated=("allocated", "sum"),
        attributed_orders=("attributed_orders", "sum"),
        attributed_gross_value=("attributed_gross_value", "sum"),
    )
    grouped["value_per_spend"] = [
        ratio(v, a) for v, a in zip(grouped["attributed_gross_value"], grouped["allocated"], strict=True)
    ]
    grouped["cost_per_order"] = [
        ratio(a, o) for a, o in zip(grouped["allocated"], grouped["attributed_orders"], strict=True)
    ]
    return grouped


def stack(recon: pd.DataFrame) -> pd.DataFrame:
    long = recon.melt(id_vars="date", value_vars=list(SEGMENTS), var_name="segment", value_name="spend")
    return long.assign(segment=long["segment"].map(SEGMENTS), spend=long["spend"].astype(float))


def spend_stack_bar(recon: pd.DataFrame) -> None:
    st.markdown("**Daily online spend: allocated vs unallocated**")
    if st.toggle("Table view", key="budget_spend_table_view"):
        table(recon[["date", "online_spend", "allocated", "unallocated"]], dataset_id=RECON)
        return
    data = stack(recon)
    color = alt.Color(
        "segment:N",
        scale=alt.Scale(domain=list(SEGMENTS.values()), range=[ACCENT, SERIES_NEUTRAL]),
        legend=alt.Legend(title=None, orient="top"),
    )
    base = alt.Chart(data).encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y("spend:Q", title="Online spend", stack="zero"),
        order=alt.Order("segment:N"),
    )
    bars = base.mark_bar(stroke=SURFACE, strokeWidth=2).encode(
        color=color, tooltip=["date:T", "segment:N", alt.Tooltip("spend:Q", format=",.2f")]
    )
    chart = bars
    if recon["date"].nunique() <= LABELLED_DAYS:
        labels = base.mark_text(dy=10, color=SURFACE, fontSize=10).encode(text=alt.Text("spend:Q", format=",.0f"))
        chart = bars + labels
    st.altair_chart(chart, use_container_width=True)


def render() -> None:
    source = current_source()
    days, recon = source.read(BUDGET), source.read(RECON)
    if days.empty:
        empty_state("No campaign spend yet.", "Budget & Spend fills after the finance marts refresh.")
        return
    names = dict(zip(days["campaign_id"], days["campaign_name"], strict=False))
    options = [ALL, *sorted(names)]
    chosen = filter_bar(
        "budget_spend",
        [Filter("campaign", "Campaign", options, ALL, lambda c: c if c == ALL else f"{names[c]} · {c}")],
    )["campaign"]
    if chosen != ALL:
        days = days[days["campaign_id"] == chosen]
        recon = recon[recon["date"].isin(days["date"])]
    fresh = max(days["_refreshed_at"].max(), recon["_refreshed_at"].max())
    values = summarize(days, recon)
    kinds = ["money", "money", "money", "ratio", "money"]
    for column, (term_id, value), kind in zip(st.columns(len(values)), values.items(), kinds, strict=True):
        with column:
            metric(term_id, value, fresh, kind=kind)
    spend_stack_bar(recon)
    st.markdown("**By campaign**")
    table(
        by_campaign(days),
        dataset_id=BUDGET,
        formats={"value_per_spend": "ratio", "cost_per_order": "money", "attributed_orders": "count"},
    )

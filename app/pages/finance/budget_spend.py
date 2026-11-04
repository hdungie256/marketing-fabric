from datetime import date
from decimal import Decimal

import altair as alt
import pandas as pd
import streamlit as st

from app.services.spend_edit import EVENT_KEY
from app.shell import (
    SERIES_NEUTRAL,
    Filter,
    current_in_flight,
    current_source,
    empty_state,
    filter_bar,
    fmt_date,
    fmt_money,
    fmt_time,
    metric,
    session,
    table,
    watch,
)
from app.shell.components.spend_edit import progress_strip, spend_edit_form
from pipelines.jobs.marts.campaign.campaign_overview.transforms import periods

BUDGET = "mart_finance.budget_daily"
RECON = "mart_shared.spend_reconciliation"
ALL = "All campaigns"
ACCENT = "#2F5BEA"  # DESIGN.md colors.accent
SURFACE = "#FFFFFF"  # DESIGN.md colors.surface: the 2px gap between segments
SEGMENTS = {"allocated": "Allocated", "unallocated": "Unallocated"}
LABELLED_DAYS = 31
CARDS = [  # DESIGN.md caps a KPI row at 4 cards: spend first, then efficiency
    [("campaign_budget", "money"), ("allocated_spend", "money"), ("unallocated_spend", "money")],
    [("attributed_value_per_spend_ratio", "ratio"), ("cost_per_attributed_order", "money")],
]


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
    few = recon["date"].nunique() <= LABELLED_DAYS  # the 2px segment gap and the labels would hide narrow bars
    bars = base.mark_bar(stroke=SURFACE, strokeWidth=2 if few else 0).encode(
        color=color, tooltip=["date:T", "segment:N", alt.Tooltip("spend:Q", format=",.2f")]
    )
    chart = bars
    if few:
        labels = base.mark_text(dy=10, color=SURFACE, fontSize=10).encode(text=alt.Text("spend:Q", format=",.0f"))
        chart = bars + labels
    st.altair_chart(chart, use_container_width=True)


def edited_window(recon: pd.DataFrame, day: date, days: int = 7) -> pd.DataFrame:
    """The `days` rows around `day`, shifted inward at the edges of the data so the window stays full."""
    recon = recon.sort_values("date").reset_index(drop=True)
    hits = recon.index[recon["date"].map(fmt_date) == fmt_date(day)]
    at = hits[0] if len(hits) else 0
    start = max(0, min(at - days // 2, len(recon) - days))
    return recon.iloc[start : start + days]


def reconciliation(recon: pd.DataFrame, state: dict, busy: bool) -> None:
    """The edited day and its neighbours: old values until the refresh lands, then old → new.

    st.dataframe cannot strike text through, so "old → new" stands in for the spec's struck-through old value.
    """
    day = date.fromisoformat(state["event"]["keys"]["date"])
    window = edited_window(recon, day)
    edited = window["date"].map(fmt_date) == fmt_date(day)
    out = window.assign(
        **{c: window[c].map(lambda v: fmt_money(v, places=2)) for c in ("online_spend", *SEGMENTS)}, note=""
    )
    refreshed = pd.Timestamp(window.loc[edited, "_refreshed_at"].max())
    emitted = state["event"].get("emitted_at")
    landed = emitted is not None and not pd.isna(refreshed) and refreshed >= pd.Timestamp(emitted)
    if busy:
        out.loc[edited, "note"] = f"↻ Saved {fmt_money(state['new'], places=2)}, updating"
    elif not landed:  # failed, gated or timed out: the row still holds the old values
        out.loc[edited, "note"] = "Refresh stopped · see Pipeline Status"
    else:
        out.loc[edited, "note"] = f"Refreshed {fmt_time(refreshed)} · difference 0 · see Change History"
        for column in SEGMENTS:
            if column in state["old"]:
                out.loc[edited, column] = f"{fmt_money(state['old'][column], places=2)} → " + out.loc[edited, column]
    st.markdown("**Daily reconciliation**")
    table(
        out[["date", "online_spend", *SEGMENTS, "note"]],
        dataset_id=RECON,
        highlight=lambda row: fmt_date(row["date"]) == fmt_date(day),
    )


def render() -> None:
    source = current_source()
    days, recon = source.read(BUDGET), source.read(RECON)
    all_recon = recon
    if days.empty:
        empty_state("No campaign spend yet.", "Budget & Spend fills after the finance marts refresh.")
        return
    spans = {pid: (label, start, end) for pid, label, start, end in periods({d.year for d in days["date"]})}
    names = dict(zip(days["campaign_id"], days["campaign_name"], strict=False))
    options = [ALL, *sorted(names)]
    chosen = filter_bar(
        "budget_spend",
        [
            Filter("period", "Period", list(spans), format_func=lambda p: spans[p][0]),
            Filter("campaign", "Campaign", options, ALL, lambda c: c if c == ALL else f"{names[c]} · {c}"),
        ],
    )
    _, start, end = spans[chosen["period"]]
    days, recon = days[days["date"].between(start, end)], recon[recon["date"].between(start, end)]
    campaign = chosen["campaign"]
    if campaign != ALL:
        days = days[days["campaign_id"] == campaign]
        recon = recon[recon["date"].isin(days["date"])]
    if days.empty:
        if campaign == ALL:
            empty_state("No campaign spend in this period.")
        else:
            empty_state(f"No campaign spend for {campaign} in this period.", "Clear the Campaign filter to see all.")
        return
    campaigns = None if campaign == ALL else {campaign}
    shown = current_in_flight(campaigns)
    fresh = max(days["_refreshed_at"].max(), recon["_refreshed_at"].max())
    values = summarize(days, recon)
    for row in CARDS:
        for column, (term_id, kind) in zip(st.columns(3), row, strict=False):
            with column:
                metric(term_id, values[term_id], fresh, kind=kind, in_flight=shown)
    if campaigns:
        st.caption(
            f"Allocated Spend covers {names[campaign]} only. Unallocated Spend and the daily chart cover all campaigns"
            " on the same days: online spend is reconciled per day, not per campaign."
        )
    if shown:
        watch(campaigns, shown)
    if EVENT_KEY in st.session_state:
        # date-grain: busy for any campaign selection, so ask without the campaign filter
        busy = RECON in (shown if campaigns is None else current_in_flight(None))
        reconciliation(all_recon, st.session_state[EVENT_KEY], busy)
    spend_stack_bar(recon)
    st.markdown("**By campaign**")
    table(
        by_campaign(days),
        dataset_id=BUDGET,
        formats={"value_per_spend": "ratio", "cost_per_order": "money", "attributed_orders": "count"},
    )
    if session.role() == "UG04":
        spend_edit_form(days, recon)
        progress_strip()

import streamlit as st

import fabric_control
from app.services import campaign_overview as svc
from app.shell import Filter, current_source, empty_state, filter_bar, metric, table

KEY = "campaign_overview"
CARDS = [
    ("attributed_orders", "count"),
    ("attributed_buyers", "count"),
    ("attributed_gross_value", "money"),
    ("average_order_value", "money"),
]


def render() -> None:
    df = svc.load(current_source())
    periods = dict(svc.periods(df))
    names = dict(svc.campaigns(df))
    chosen = filter_bar(
        KEY,
        [
            Filter("period", "Period", list(periods), format_func=periods.get),
            Filter(
                "campaign",
                "Campaign",
                list(names),
                format_func=lambda c: names[c] if c == svc.ALL else f"{names[c]} · {c}",
            ),
        ],
    )
    kpi, rows = svc.select(df, chosen["period"], chosen["campaign"])
    if kpi["attributed_orders"] == 0:
        if chosen["campaign"] == svc.ALL:
            empty_state("No attributed orders in this period.")
        else:
            empty_state(
                f"No attributed orders for {chosen['campaign']} in this period.",
                "Clear the Campaign filter to see all.",
            )
        return
    for column, (term_id, kind) in zip(st.columns(4), CARDS, strict=True):
        with column:
            metric(term_id, kpi[term_id], kpi["_refreshed_at"], kind=kind)
    st.subheader("By Campaign")
    headers = {term_id: fabric_control.term(term_id)["display_name"] for term_id, _ in CARDS}
    table(
        rows[["campaign_id", "campaign_name", *headers]].rename(columns=headers),
        dataset_id=svc.DATASET,
        campaign_col="campaign_id",
    )

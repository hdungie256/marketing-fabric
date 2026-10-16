import streamlit as st

import fabric_control
from app.services import campaign_overview as overview
from app.services import new_returning as svc
from app.shell import Filter, chart, current_source, empty_state, filter_bar, metric, table

KEY = "new_vs_returning"
CARDS = ["first_observed_buyers", "returning_buyers", "attributed_buyers"]


def render() -> None:
    df = svc.load(current_source())
    periods = dict(overview.periods(df))
    names = dict(overview.campaigns(df))
    chosen = filter_bar(
        KEY,
        [
            Filter("period", "Period", list(periods), format_func=periods.get),
            Filter(
                "campaign",
                "Campaign",
                list(names),
                format_func=lambda c: names[c] if c == overview.ALL else f"{names[c]} · {c}",
            ),
        ],
    )
    kpi, rows = overview.select(df, chosen["period"], chosen["campaign"])
    if kpi["attributed_buyers"] == 0:
        if chosen["campaign"] == overview.ALL:
            empty_state("No attributed buyers in this period.")
        else:
            empty_state(
                f"No attributed buyers for {chosen['campaign']} in this period.",
                "Clear the Campaign filter to see all.",
            )
        return
    for column, term_id in zip(st.columns(3), CARDS, strict=True):
        with column:
            metric(term_id, kpi[term_id], kpi["_refreshed_at"])
    chart(
        svc.stack(rows),
        key="new_returning_chart",
        title="First observed vs returning buyers by campaign",
        x="campaign_id",
        y="buyers",
        x_title="Campaign",
        y_title="Buyers",
        series="buyer_type",
        horizontal=True,
        table_dataset_id=svc.DATASET,
    )
    headers = {term_id: fabric_control.term(term_id)["display_name"] for term_id in CARDS}
    table(
        rows[["campaign_id", "campaign_name", *headers]].rename(columns={"campaign_id": "Campaign", **headers}),
        dataset_id=svc.DATASET,
        campaign_col="Campaign",
        info_terms={
            "First Observed Buyers": "first_observed_buyers",
            "Returning Buyers": "returning_buyers",
            "Attributed Buyers": "attributed_buyers",
        },
    )

"""RFM Segments (Story 5.1, BR05). Home page of UG02."""

import streamlit as st

from app.services import customers as svc
from app.shell import Filter, chart, current_source, empty_state, filter_bar, table
from app.shell.data_source import data_mode

KEY = "rfm_segments"
FIXTURE_NOTE = "Sample data (fixture mode): a small synthetic customer set, not the 2019 customer base."


def render() -> None:
    df = svc.load(current_source())
    if df.empty:
        empty_state("No buying customers in this data.")
        return
    summary = svc.segment_summary(df)
    values = filter_bar(KEY, [Filter("segment", "Segment", list(summary["segment"]))])
    if data_mode() == "fixture":
        st.caption(FIXTURE_NOTE)
    chart(
        summary,
        key="rfm_distribution",
        title="Buyers by RFM segment",
        x="segment",
        y="customers",
        x_title="Segment",
        y_title="Buyers",
        table_dataset_id=svc.DATASET,
    )
    table(
        summary,
        dataset_id=svc.DATASET,
        formats={"customers": "count", "share": "pct"},
        highlight=lambda row: row["segment"] == values["segment"],
    )
    rows = svc.match(df, segment=values["segment"])
    st.markdown(f"**{values['segment']} · {len(rows)} buyers**")
    table(
        svc.detail(rows),
        dataset_id=svc.DATASET,
        formats={"monetary_value": "money"},
        info_terms={"segment": "rfm_segment"},
    )

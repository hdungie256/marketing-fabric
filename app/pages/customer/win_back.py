"""Win-back (Story 5.2, BR09, FR-33a, UX-DR29)."""

import streamlit as st

from app.services import customers as svc
from app.shell import Filter, current_source, empty_state, filter_bar, table

KEY = "win_back"
PREFILL_KEY = "audience_prefill"


def render() -> None:
    df = svc.load(current_source())
    cats = svc.category_options(df)
    values = filter_bar(KEY, [Filter("category", "Purchased category", [svc.ALL, *cats])])
    rows = svc.win_back(df, category=values["category"])
    if rows.empty:
        empty_state("No lapsed high-value customers for this filter.", "Widen the category filter.")
        return
    table(
        svc.detail(rows),
        dataset_id=svc.DATASET,
        formats={"monetary_value": "money"},
        info_terms={"segment": "rfm_segment"},
    )
    if st.button("Build audience from this list", key=f"{KEY}-to-builder"):
        st.session_state[PREFILL_KEY] = svc.criteria(category=values["category"], min_orders=1)
        st.toast("Audience Builder prefilled with the Win-back criteria")

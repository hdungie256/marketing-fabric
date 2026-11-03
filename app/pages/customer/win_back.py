"""Win-back (Story 5.2, BR09, FR-33a, UX-DR29)."""

import streamlit as st

from app.services import customers as svc
from app.shell import Filter, current_source, empty_state, filter_bar, fmt_count, fmt_date, session, table

KEY = "win_back"
PREFILL_KEY = "audience_prefill"


def render() -> None:
    df = svc.load(current_source())
    cats = svc.category_options(df)
    values = filter_bar(KEY, [Filter("category", "Purchased category", [svc.ALL, *cats])])
    rows = svc.win_back(df, category=values["category"])
    st.markdown(
        f"**{fmt_count(len(rows))} of {fmt_count(svc.buyer_count(df))} buyers** · {svc.WIN_BACK_RULE} (R18)"
        f" · as of {fmt_date(svc.as_of_date())}"
    )
    if rows.empty:
        empty_state("No lapsed high-value customers for this filter.", "Widen the category filter.")
        return
    table(
        rows,
        dataset_id=svc.DATASET,
        formats={"monetary_value": "money"},
        info_terms={"segment": "rfm_segment"},
    )
    if st.button("Build audience from this list", key=f"{KEY}-to-builder"):
        st.session_state[PREFILL_KEY] = svc.criteria(category=values["category"], win_back=True)
        session.request_toast("Audience Builder prefilled with the Win-back criteria")
        session.request_redirect("audience_builder")
        st.rerun()

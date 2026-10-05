from datetime import datetime

import streamlit as st

import fabric_control
from app.shell.badges import badge_fresh, badge_synthetic
from app.shell.errors import UnknownTermError
from app.shell.format import FORMATTERS
from app.shell.page import add_footnote

NOTE_TEXT: dict[str, str] = {
    "currency_unverified": "Currency of monetary values is not stated in the source (R10).",
    "retrospective_target": "Retrospective synthetic target (R14).",
    "estimate_not_profit": "Estimate, not accounting profit.",
    "attributed_not_incremental": "Attributed, not incremental.",
    "first_in_observed_history": "First within observed history.",
}
FOOTNOTE_NOTES = {"currency_unverified"}


def metric(term_id: str, value: float | int | None, freshness: datetime, *, kind: str = "count") -> None:
    if kind not in FORMATTERS:
        raise ValueError(f"kind must be one of {sorted(FORMATTERS)}, got {kind!r}")
    if freshness is None:
        raise ValueError(f"{term_id}: freshness is required (max(_refreshed_at) of the rows behind the value)")
    term = fabric_control.term(term_id)
    if term is None:
        raise UnknownTermError(term_id)
    notes = list(term.get("notes") or [])
    unknown = [note for note in notes if note not in NOTE_TEXT]
    if unknown:
        raise ValueError(f"{term_id}: unknown notes {unknown}")

    with st.container(key=f"metric-{term_id}"):
        with st.container(key=f"kpi-label-{term_id}"):
            st.markdown(term["display_name"])
        with st.container(key=f"kpi-value-{term_id}"):
            st.markdown(FORMATTERS[kind](value))
        with st.container(key=f"kpi-badges-{term_id}", horizontal=True):
            badge_fresh(freshness)
            if term.get("synthetic"):
                badge_synthetic()
        inline = [NOTE_TEXT[note] for note in notes if note not in FOOTNOTE_NOTES]
        if inline:
            st.caption(" · ".join(inline))
    for note in notes:
        if note in FOOTNOTE_NOTES:
            add_footnote(NOTE_TEXT[note])

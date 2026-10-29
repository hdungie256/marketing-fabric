from datetime import datetime

import streamlit as st

import fabric_control
from app.shell.badges import badge_fresh, badge_refreshing, badge_stale, badge_synthetic
from app.shell.components.definition_dialog import definition_dialog
from app.shell.errors import UnknownTermError
from app.shell.format import FORMATTERS
from app.shell.notes import FOOTNOTE_NOTES, NOTE_TEXT
from app.shell.page import add_footnote, add_stale


def metric(
    term_id: str,
    value: float | int | None,
    freshness: datetime,
    *,
    kind: str = "count",
    in_flight: frozenset[str] = frozenset(),
) -> None:
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

    state = fabric_control.status(term["dataset_id"]) if term.get("dataset_id") else {"stale": False}
    if state["stale"]:
        add_stale(state["datasets"])

    with st.container(key=f"metric-{'stale-' if state['stale'] else ''}{term_id}"):
        label, info = st.columns([6, 1])
        with label:
            st.markdown(term["display_name"])
        with info:
            if st.button(
                f"Definition of {term['display_name']}",  # the accessible name; components.css shows only the icon
                key=f"kpi-info-{term_id}",  # not metric-*: components.css styles every st-key-metric-* as a card
                help=f"About {term['display_name']}",
                icon=":material/info:",
            ):
                definition_dialog(term_id)
        with st.container(key=f"kpi-value-{term_id}"):
            st.markdown(FORMATTERS[kind](value))
        with st.container(key=f"kpi-badges-{term_id}", horizontal=True):
            if state["stale"]:
                badge_stale()
            elif term.get("dataset_id") in in_flight:
                badge_refreshing()
            else:
                badge_fresh(freshness)
            if term.get("synthetic"):
                badge_synthetic()
        inline = [NOTE_TEXT[note] for note in notes if note not in FOOTNOTE_NOTES]
        if inline:
            st.caption(" · ".join(inline))
    for note in notes:
        if note in FOOTNOTE_NOTES:
            add_footnote(NOTE_TEXT[note])

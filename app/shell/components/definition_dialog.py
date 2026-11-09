"""Metric definition dialog (Story 2.4, FR-12, UX-DR14).

One modal level by construction: this module exposes a single @st.dialog
function; callers invoke it from a button and it never opens another dialog.
"""

from __future__ import annotations

import streamlit as st

import fabric_control
from app.shell.badges import badge_synthetic
from app.shell.components.lineage_graph import SOURCE_DEPTH, lineage_graph
from app.shell.components.status_chip import status_chip
from app.shell.format import fmt_time
from app.shell.notes import NOTE_TEXT


def is_roas_caution(term: dict) -> bool:
    return any("roas" in str(item).lower() for item in term.get("limitations") or [])


def render_definition(term: dict) -> None:
    st.markdown(f":blue[{term['display_name']}]")
    st.write(term["definition"])
    st.markdown(f"**Formula:** {term['formula']}")
    sources = ", ".join(f"`{term['dataset_id']}.{c}`" for c in term.get("source_columns") or [term["column"]])
    st.markdown(f"**Source columns:** {sources}")
    st.markdown(f"**Rules:** {', '.join(term.get('rules') or [])}")
    st.markdown("**Limitations:**")
    for item in term.get("limitations") or []:
        st.markdown(f"- {item}")
    st.markdown(f"**Owner slice:** {term.get('owner_slice') or '—'}")
    if term.get("synthetic"):
        badge_synthetic()
    if is_roas_caution(term):
        status_chip("danger", "Not ROAS — see limitations")
    for note in term.get("notes") or []:
        if note in NOTE_TEXT:
            st.caption(NOTE_TEXT[note])


def render_quality(term: dict) -> None:
    score, status = term.get("score"), term.get("status")
    if status == "not yet measured" or status is None:
        status_chip("neutral", "Quality not yet measured")
    else:
        variant = "success" if status == "Green" else "warning" if status == "Amber" else "danger"
        status_chip(variant, f"{status}" + (f" {score:.0f}%" if score is not None else ""))
    refreshed = term.get("refreshed_at")
    st.write(f"Last refresh: {fmt_time(refreshed) if refreshed else '—'}")


@st.dialog("Metric definition", width="large")
def definition_dialog(term_id: str) -> None:
    term = fabric_control.term(term_id)
    if term is None:
        st.error(f"Unknown metric {term_id}: not in the glossary.")
        return
    st.markdown(f"## :blue[{term['display_name']}]")
    definition, lineage, quality = st.tabs(["Definition", "Lineage", "Quality"])
    with definition:
        render_definition(term)
    with lineage:
        lineage_graph(term["dataset_id"], depth=SOURCE_DEPTH, key=f"dlg-{term_id}")
    with quality:
        render_quality(term)

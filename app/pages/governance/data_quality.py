"""Data Quality & Exceptions page (Story 3.4, FR-7, FR-9). Home page of UG05."""

from __future__ import annotations

import streamlit as st

from app.services import exception_triage as triage
from app.shell import Filter, empty_state, filter_bar, table
from app.shell.components.status_chip import status_chip
from app.shell.roles import ROLES

KEY = "data_quality"
CLASSES = ["shared_transaction_id", "coupon_plan_mismatch", "coupon_plan_duplicate"]
STATUS_CHIP = {"new": "info", "seen": "warning", "accepted": "success", triage.RESOLVED: "neutral"}


def render_scoreboard() -> None:
    with triage.connect_reader() as conn:
        dq = triage.read_view(conn, "ops_v.dq_results")
    board = triage.scoreboard(dq)
    if board.empty:
        empty_state("No quality results yet.", "Scores appear after jobs run with DQ rules.")
        return
    for row in board.itertuples():
        left, right = st.columns([3, 1])
        with left:
            st.markdown(f"**{row.dataset_id}**")
            if row.failing:
                st.caption(f"Failing: {row.failing}")
        with right:
            variant = "success" if row.status == "Green" else "warning" if row.status == "Amber" else "danger"
            status_chip(variant, f"{row.status} {row.score_pct:.0f}%")


def render_exceptions() -> None:
    with triage.connect_reader() as conn:
        exceptions = triage.read_view(conn, "mart_shared_v.exceptions")
        statuses = triage.read_view(conn, "app_v.exception_status")
    if exceptions.empty:
        empty_state("No exceptions detected.")
        return
    values = filter_bar(KEY, [Filter("class", "Class", sorted(exceptions["class"].unique()))])
    framed = triage.with_status(exceptions[exceptions["class"] == values["class"]], statuses)
    counts = framed["status"].value_counts()
    chips = st.columns(len(counts))
    for column, (status, count) in zip(chips, counts.items(), strict=True):
        with column:
            status_chip(STATUS_CHIP.get(status, "neutral"), f"{status}: {count}")
    table(framed, dataset_id="mart_shared.exceptions")
    markable = framed.loc[framed["status"] != triage.RESOLVED, "exception_id"].tolist()
    chosen = st.multiselect("Exceptions", markable, key=f"{KEY}-triage")
    left, right = st.columns(2)
    with left:
        if st.button("Mark seen", key=f"{KEY}-seen") and chosen:
            _mark(chosen, "seen", set(framed["exception_id"]))
    with right:
        if st.button("Mark accepted", key=f"{KEY}-accepted") and chosen:
            _mark(chosen, "accepted", set(framed["exception_id"]))
    st.caption("Coupon status per line and repeated shipping are storage conventions (R17), never exceptions.")


def _mark(exception_ids: list[str], status: str, known_ids: set[str]) -> None:
    try:
        with triage.connect_writer() as conn:
            count = triage.mark_status(conn, exception_ids, status, ROLES["UG05"].code, known_ids)
    except ValueError as e:
        st.error(str(e))
        return
    st.toast(f"Marked {count} as {status}")


def render() -> None:
    st.subheader("Quality scoreboard")
    render_scoreboard()
    st.subheader("Exceptions")
    render_exceptions()

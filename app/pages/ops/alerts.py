"""Sidebar alert indicator (Story 7.2, UX-DR9): open pipeline failures for UG06, quality failures for UG05."""

from __future__ import annotations

import logging

import streamlit as st

from app.services import pipeline_status as ps
from app.services.exception_triage import read_view
from app.shell.roles import ROLES

log = logging.getLogger("app.ops")
TARGETS = {"UG06": "pipeline_status", "UG05": "data_quality"}


@st.cache_data(ttl=10, show_spinner=False)
def count(role: str) -> int:
    with ps.connect(ROLES[role]) as conn:
        return ps.alert_count(read_view(conn, "ops_v.runs"), role)


def alert_indicator(role: str, st_pages: dict) -> None:
    if role not in TARGETS or TARGETS[role] not in st_pages:
        return
    try:
        n = count(role)
    except Exception as e:  # the indicator must never break navigation
        log.warning("alert count unavailable for %s: %s", role, e)
        return
    if n:
        label = f"{n} open {'pipeline' if role == 'UG06' else 'quality'} alert{'s' if n > 1 else ''}"
        st.page_link(st_pages[TARGETS[role]], label=label, icon="🔔", query_params={"status": "failed"})

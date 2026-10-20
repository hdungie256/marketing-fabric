import logging
from datetime import UTC, datetime

import psycopg
import streamlit as st

from app.services import pipeline_status
from app.services.exception_triage import read_view
from app.services.refresh_progress import in_flight
from app.shell import session
from app.shell.data_source import data_mode
from app.shell.roles import ROLES

log = logging.getLogger(__name__)


def current_in_flight(campaign_ids: set[str] | None) -> frozenset[str]:
    if data_mode() == "fixture":
        return frozenset()
    try:
        with pipeline_status.connect(ROLES[session.role()]) as conn:
            events = read_view(conn, "ops_v.source_events")
            runs = read_view(conn, "ops_v.runs")
    except psycopg.Error:
        log.warning("refresh watcher: could not read ops views", exc_info=True)
        return frozenset()
    return in_flight(events, runs, campaign_ids, datetime.now(UTC))


@st.fragment(run_every=2)
def watch(campaign_ids: set[str] | None, shown: frozenset[str]) -> None:
    if current_in_flight(campaign_ids) != shown:
        st.rerun()

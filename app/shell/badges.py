from datetime import datetime

import streamlit as st

from app.shell.format import fmt_time


def badge_fresh(dt: datetime) -> None:
    st.badge(f"Refreshed {fmt_time(dt)}", icon=":material/check_circle:", color="green")


def badge_stale() -> None:
    st.badge("Using previous version", icon=":material/warning:", color="orange")


def badge_synthetic() -> None:
    st.badge("Synthetic", icon=":material/science:", color="gray")


def badge_refreshing() -> None:
    st.badge("Refreshing…", icon=":material/sync:", color="blue")


def freshness_badge(freshness: datetime, dataset_id: str, in_flight: frozenset[str]) -> None:
    badge_refreshing() if dataset_id in in_flight else badge_fresh(freshness)

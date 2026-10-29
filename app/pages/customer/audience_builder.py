"""Audience Builder (Story 5.3, BR08, FR-33, UX-DR28) with locked export (Story 5.4, FR-21)."""

from __future__ import annotations

import os

import psycopg
import streamlit as st

import fabric_control
from app.pages.customer.win_back import PREFILL_KEY
from app.services import customers as svc
from app.shell import Filter, current_source, empty_state, filter_bar, table
from app.shell import session as session_
from app.shell.roles import ROLES

KEY = "audience_builder"


def connect_reader() -> psycopg.Connection:
    role = ROLES[session_.role()]
    return psycopg.connect(
        host=os.environ.get("DB_HOST", "postgresql"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname="serving",
        user=role.db_user,
        password=os.environ[role.password_env],
        autocommit=True,
        options="-c default_transaction_read_only=on",
    )


def connect_writer() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ.get("DB_HOST", "postgresql"),
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname="serving",
        user="app_writer",
        password=os.environ["APP_WRITER_DB_PASSWORD"],
        autocommit=True,
    )


def render() -> None:
    df = svc.load(current_source())
    prefill = st.session_state.pop(PREFILL_KEY, None) or {}
    if prefill:
        session_.filters(KEY).clear()  # a Win-back prefill wins over the filters kept from an earlier visit
    cats = svc.category_options(df)
    values = filter_bar(
        KEY,
        [
            Filter("segment", "Segment", [svc.ALL, *svc.SEGMENT_ORDER], prefill.get("segment", svc.ALL)),
            Filter("category", "Purchased category", [svc.ALL, *cats], prefill.get("category", svc.ALL)),
        ],
    )
    min_orders = st.number_input(
        "Minimum past orders", min_value=0, value=prefill.get("min_orders", 0), key=f"{KEY}-min"
    )
    win_back = st.checkbox(
        f"Lapsed high-value only: {svc.WIN_BACK_RULE}", value=prefill.get("win_back", False), key=f"{KEY}-win-back"
    )
    crit = svc.criteria(
        segment=values["segment"], category=values["category"], min_orders=int(min_orders), win_back=win_back
    )
    rows = svc.match(df, **crit)
    st.markdown(f"**{len(rows)} customers match**")
    if rows.empty:
        empty_state("No customers match these criteria.", "Widen the segment or category filter.")
    else:
        table(rows, dataset_id=svc.DATASET, formats={"monetary_value": "money"})
    with st.form(key=f"{KEY}-save"):
        name = st.text_input("Audience name", key=f"{KEY}-name")
        save = st.form_submit_button("Save audience")
    if save:
        if not (name or "").strip():
            st.error("Give the audience a name before saving.")
        else:
            with connect_writer() as conn:
                audience_id = svc.save_audience(conn, name.strip(), crit, len(rows), session_.role())
            st.toast(f"Audience saved · {audience_id}")
    allowed, reason = fabric_control.can_export(svc.DATASET, session_.role())
    st.button("🔒 Export contacts", disabled=True, key=f"{KEY}-export")
    if not allowed:
        st.caption(reason)
    try:
        with connect_reader() as conn:
            saved = svc.read_audiences(conn)
    except Exception:
        saved = None
    if saved is not None and not saved.empty:
        st.subheader("Saved audiences")
        table(saved)

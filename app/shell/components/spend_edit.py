"""Spend edit form and partial refresh progress strip (Story 8.5). The API judges the value; the form shows it."""

from datetime import UTC, datetime
from decimal import Decimal

import pandas as pd
import psycopg
import streamlit as st

from app.services import pipeline_status
from app.services import spend_edit as service
from app.services.change_history import PAGE_OF, changed_values
from app.services.exception_triage import read_view
from app.services.refresh_progress import finished, statuses, steps
from app.services.spend_edit import EVENT_KEY, SpendServiceUnavailable, field_errors
from app.shell import session
from app.shell.components.feedback import banner_error, toast
from app.shell.data_source import data_mode
from app.shell.format import DASH, fmt_date
from app.shell.roles import ROLES
from fabric_control.glossary import load_terms

PAGE_TITLE = {"budget_spend": "Budget & Spend", "contribution": "Contribution", "targets": "Targets"}
_VALUE_GEN = "_spend_edit_value_gen"  # bumped after a save so the value field comes back empty


def spend_edit_form(days: pd.DataFrame, recon: pd.DataFrame) -> None:
    """Caller contract: `recon` must cover every date in `days` (the hint and the saved old values read from it)."""
    st.markdown("**Edit daily spend**")
    st.caption("Correct one day's allocated spend for a campaign.")
    banner = st.empty()
    names = dict(zip(days["campaign_id"], days["campaign_name"], strict=False))
    campaign = st.selectbox(
        "Campaign", sorted(names), format_func=lambda c: f"{names[c]} · {c}", key="spend_edit_campaign"
    )
    slots = {"campaign_id": st.empty()}
    dates = sorted(days.loc[days["campaign_id"] == campaign, "date"].unique())
    day = st.selectbox("Date", dates, format_func=fmt_date, key=f"spend_edit_date_{campaign}")
    slots["date"] = st.empty()
    gen = st.session_state.setdefault(_VALUE_GEN, 0)
    value = st.number_input("Allocated spend", value=None, step=0.01, format="%.2f", key=f"spend_edit_value_{gen}")
    row = recon[recon["date"].map(fmt_date) == fmt_date(day)]
    online = f"{Decimal(str(row['online_spend'].iloc[0])):,.2f}" if not row.empty else DASH  # cents: the API's bound
    st.caption(f"Online spend that day is {online}. Allocated must be between 0 and that amount.")
    slots["allocated_online_spend"] = st.empty()
    live = data_mode() == "pg"
    clicked = st.button("Save change", type="primary", disabled=not live)
    if not live:
        st.caption("Saving needs the live stack (APP_DATA_MODE=pg).")
    if not clicked:
        return
    if value is None:
        slots["allocated_online_spend"].error("Enter a value")
        return
    new = Decimal(f"{value:.2f}")
    try:
        with st.spinner("Saving…"):
            status, body = service.put_spend(campaign, pd.Timestamp(day).date(), new, session.role())
    except SpendServiceUnavailable as e:
        with banner.container():
            banner_error("The spend service did not answer", str(e))
        return
    errors = field_errors(status, body)
    for field, reason in errors.items():
        slots.get(field, banner).error(reason)
    if errors:
        return
    detail = body.get("detail")
    reason = detail.get("reason") if isinstance(detail, dict) else None
    if status == 200:
        toast("Change saved · partial refresh started", "success")
        st.session_state[EVENT_KEY] = {
            "event": body["event"],
            "dag_run_id": body["dag_run_id"],
            "campaign_name": names[campaign],
            "old": {k: row[k].iloc[0] for k in ("allocated", "unallocated")} if not row.empty else {},
            "new": new,
        }
        st.session_state[_VALUE_GEN] = gen + 1
        return
    with banner.container():
        if status == 502:
            banner_error(f"Change saved, but the refresh did not start: {reason}")
        else:
            banner_error(reason or f"The spend service answered {status}")


def _read(role: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    with pipeline_status.connect(ROLES[role]) as conn:
        return read_view(conn, "ops_v.runs"), read_view(conn, "ops_v.metric_change_log")


def _pages(event_steps: list[dict]) -> str:
    keys = {PAGE_OF.get(s["dataset_id"].rsplit(".", 1)[-1]) for s in event_steps}
    titles = [t for k, t in PAGE_TITLE.items() if k in keys]
    return " and ".join([", ".join(titles[:-1]), titles[-1]]) if len(titles) > 1 else "".join(titles)


def _render(state: dict) -> bool:
    """Draw the strip once; True when the event is finished."""
    event = state["event"]
    try:
        runs, log = _read(session.role())
    except psycopg.Error as e:
        banner_error("Could not read the refresh progress", str(e))
        return False
    now = datetime.now(UTC)
    emitted = datetime.fromisoformat(event["emitted_at"])
    event_steps = steps(event)
    states = statuses(event_steps, runs, event["event_id"], emitted, now)
    done = finished(states)
    mine = runs[runs["event_id"] == event["event_id"]]
    end = mine["ended_at"].max() if done and "ended_at" in mine and not mine.empty else None
    with st.container(border=True):
        head, timer = st.columns([5, 1])
        head.markdown(
            f"**Refreshing {len(event_steps)} datasets for {state['campaign_name']}, {event['keys']['date']}**"
        )
        timer.markdown(pipeline_status.fmt_duration(pipeline_status.seconds(emitted, end, now)))
        st.caption(f"Affects {_pages(event_steps)}")
        for step, step_state in zip(event_steps, states, strict=True):
            left, right = st.columns([5, 1])
            left.markdown(f"{step['label']}  \n`{step['dataset_id']}`")
            right.markdown(step_state)
        if done and all(s == "done" for s in states):
            count = len(changed_values(log, event, load_terms()))
            st.markdown(f"{count} metrics changed — see Change History")
            if st.button("See Change History"):
                st.query_params["event_id"] = event["event_id"]
                session.request_redirect("change_history")
                st.rerun()
        elif done:
            bad = mine[mine["status"].isin(["failed", "gated"])]
            causes = bad.get("failing_step", pd.Series(dtype=object)).dropna()
            stopped = causes.iloc[0] if not causes.empty else "a step did not finish"
            st.markdown(f"Refresh stopped: {stopped}. See Pipeline Status.")
        st.caption("Full run detail is on Pipeline Status (Data Ops role).")
    return done


@st.fragment(run_every=2)
def _live() -> None:
    state = st.session_state[EVENT_KEY]
    if _render(state):
        state["finished"] = True
        st.rerun()  # whole app: the finished strip is drawn outside the fragment, so polling stops


def progress_strip() -> None:
    state = st.session_state.get(EVENT_KEY)
    if state is None:
        return
    if state.get("finished"):
        _render(state)
    else:
        _live()

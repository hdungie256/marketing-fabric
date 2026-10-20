"""Refresh progress for spend change events (Stories 8.5-8.6). Pure pandas over ops_v runs and events."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd

import fabric_control

TIMEOUT_SECONDS = 600
LABELS = {
    "unified/campaign_spend": "Spend source data",
    "unified/daily_spend": "Daily online spend",
    "mart_shared.campaign_spend_allocated": "Spend allocation by campaign",
    "mart_shared.spend_reconciliation": "Daily spend reconciliation",
    "mart_finance.budget_daily": "Budget & Spend",
    "mart_finance.contribution": "Contribution",
    "mart_finance.contribution_sku": "Contribution by SKU",
    "mart_campaign.target_achievement": "Targets",
}
_RUN_STATE = {"success": "done", "running": "running", "failed": "failed", "gated": "failed"}
_BAD = {"failed", "skipped", "timed out"}


def label(dataset_id: str) -> str:
    return LABELS.get(dataset_id, dataset_id)


def steps(event: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"dataset_id": a["dataset_id"], "job_id": a["job_id"], "label": label(a["dataset_id"])}
        for a in fabric_control.affected_by(event)[1:]
    ]


def statuses(steps: list[dict], runs: pd.DataFrame, event_id: str, emitted_at: datetime, now: datetime) -> list[str]:
    rows = runs[runs["event_id"] == event_id]
    by_job = dict(zip(rows["job_id"], rows["status"], strict=False))  # ponytail: last row per job wins
    timed_out = (now - emitted_at).total_seconds() > TIMEOUT_SECONDS
    out: list[str] = []
    for step in steps:
        status = by_job.get(step["job_id"])
        if status is not None:
            out.append(_RUN_STATE[status])
        elif "failed" in out:
            out.append("skipped")
        else:
            out.append("timed out" if timed_out else "queued")
    return out


def finished(states: list[str]) -> bool:
    return all(s == "done" for s in states) or any(s in _BAD for s in states)


def in_flight(
    events: pd.DataFrame, runs: pd.DataFrame, campaign_ids: set[str] | None, now: datetime
) -> frozenset[str]:
    live = events[events["dag_run_id"].notna()]
    if live.empty:
        return frozenset()
    ev = live.sort_values("emitted_at").iloc[-1]
    keys = ev["keys"]
    keys = json.loads(keys) if isinstance(keys, str) else keys
    campaigns = keys.get("campaign_id", [])
    campaigns = campaigns if isinstance(campaigns, list) else [campaigns]
    if campaign_ids is not None and not campaign_ids.intersection(campaigns):
        return frozenset()
    event_steps = steps({"source": ev["source"], "keys": keys})
    states = statuses(event_steps, runs, ev["event_id"], ev["emitted_at"], now)
    if finished(states):
        return frozenset()
    return frozenset(s["dataset_id"] for s, st in zip(event_steps, states, strict=True) if st in ("queued", "running"))

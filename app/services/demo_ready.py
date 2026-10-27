"""Pre-demo readiness check and NFR-4 report (Story 9.4, UX-DR42). `make demo-ready` runs it in the streamlit container.

Checks the pre-demo state from the EXPERIENCE demo script: full refresh done, no stale dataset, alert count 0, fault
toggles off. Then prints end-to-end refresh, partial refresh and page response times against the NFR-4 targets.
"""

from __future__ import annotations

import sys
from datetime import datetime

import pandas as pd

from app.services import pipeline_status as ps
from app.shell.roles import ROLES

Check = tuple[str, bool, str]


def full_refresh_check(runs: pd.DataFrame) -> Check:
    latest = ps.last_full_refresh(runs)
    if latest.empty:
        return "full refresh done", False, "no full refresh recorded; run `make bootstrap`"
    bad = latest[latest["status"] != "success"]
    detail = ", ".join(f"{j} {s}" for j, s in zip(bad["job_id"], bad["status"], strict=True))
    return "full refresh done", bad.empty, detail or latest["dag_run"].iloc[0]


def state_checks(runs: pd.DataFrame, stale: list[str], faults: list[str], dq_breaks: list[str]) -> list[Check]:
    alerts = {role: ps.alert_count(runs, role) for role in ps.ALERT_STATUS}
    return [
        full_refresh_check(runs),
        ("all badges fresh", not stale, ", ".join(stale) or "no stale dataset"),
        ("alert count 0", not any(alerts.values()), ", ".join(f"{r}={n}" for r, n in alerts.items())),
        ("fault toggles off", not faults and not dq_breaks, ", ".join(faults + dq_breaks) or "none set"),
    ]


def timing_checks(runs: pd.DataFrame, timings: pd.DataFrame, now: datetime | None = None) -> list[Check]:
    """NFR-4: measure and report. A timing never measured fails and says what to run to measure it."""
    full = ps.last_full_refresh_seconds(runs, now)
    rows = [
        (
            "full refresh < 10 min",
            full is not None and full < ps.FULL_REFRESH_TARGET_SECONDS,
            ps.fmt_duration(full) if full is not None else "not measured; run `make bootstrap`",
        )
    ]
    # A source change has an emitted_at; runs tagged with a test's fixed event_id have none and are not a refresh.
    changes = runs[runs["emitted_at"].notna()] if "emitted_at" in runs else runs.iloc[:0]
    partial = ps.event_latencies(changes, now)["seconds"].dropna()
    rows.append(
        (
            "partial refresh < 2 min",
            not partial.empty and partial.max() < ps.TARGET_SECONDS,
            f"max {ps.fmt_duration(partial.max())} over {len(partial)} change events"
            if not partial.empty
            else "not measured; edit one day's spend on Budget & Spend",
        )
    )
    pages = ps.page_percentiles(timings)
    if pages.empty:
        return rows + [("page response < 3 s", False, "not measured; open each page once")]
    slow = pages[pages["p95_ms"] >= ps.PAGE_TARGET_MS]
    return rows + [
        (f"page {p} < 3 s", p not in set(slow["page"]), f"p95 {p95:.0f} ms, {n} samples")
        for p, p95, n in zip(pages["page"], pages["p95_ms"], pages["samples"], strict=True)
    ]


def render(title: str, checks: list[Check]) -> str:
    lines = [title] + [f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}" for name, ok, detail in checks]
    return "\n".join(lines)


def main() -> int:
    import fabric_control
    from fabric_control.clients import postgres
    from fabric_control.refresh import gated_datasets
    from sources.faults import SOURCES, active_fault

    with ps.connect(ROLES["UG06"]) as conn:
        runs, _, _, timings = ps.read(conn)
    stale = sorted(gated_datasets(fabric_control.load_registry()))
    faults = [f"source {s}" for s in SOURCES if active_fault(s)]
    dq = [f"dq {d}" for d in sorted(postgres.dq_breaks())]
    state, timing = state_checks(runs, stale, faults, dq), timing_checks(runs, timings)
    print(render("Pre-demo state (UX-DR42)", state))
    print(render("NFR-4 performance", timing))
    return 0 if all(ok for _, ok, _ in state + timing) else 1


if __name__ == "__main__":
    sys.exit(main())

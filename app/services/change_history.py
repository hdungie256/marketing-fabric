"""Change History reads (Story 8.6, BR16). Pure pandas over ops_v source events, runs and the metric change log."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd

import fabric_control
from app.services.pipeline_status import event_runs, with_emitted_at
from app.services.refresh_progress import label
from fabric_control.glossary import load_terms

# (dataset short name, column) -> meaning; rows of one meaning, campaign and date are one changed value.
MEANING = {
    ("campaign_spend_allocated", "allocated"): "allocated",
    ("budget_daily", "allocated"): "allocated",
    ("spend_reconciliation", "allocated"): "allocated",
    ("target_achievement", "allocated_spend"): "allocated",
    ("spend_reconciliation", "unallocated"): "unallocated",
    ("contribution", "campaign_cost"): "campaign_cost",
}
METRIC_LABEL = {"allocated": "Allocated spend", "unallocated": "Unallocated spend", "campaign_cost": "Campaign cost"}
INFO_TERM = {"allocated": "allocated_spend", "unallocated": "unallocated_spend"}
PAGE_OF = {
    "campaign_spend_allocated": "budget_spend",
    "spend_reconciliation": "budget_spend",
    "budget_daily": "budget_spend",
    "contribution": "contribution",
    "contribution_sku": "contribution",
    "target_achievement": "targets",
}
COLUMNS = ("Source", "Unified", "Shared marts", "Page marts")
RECOMPUTED = ("neutral", "Recomputed, no tracked change")
CHANGE_DATASET = "mart_shared.campaign_spend_allocated"


def _short(dataset_id: str) -> str:
    return dataset_id.rsplit(".", 1)[-1]


def _json(value: Any) -> dict:
    return json.loads(value) if isinstance(value, str) else dict(value)


def _event(row: Any) -> dict[str, Any]:
    event = dict(row)
    event["keys"] = _json(event["keys"])
    return event


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) else value


def _for_event(log: pd.DataFrame, event: dict) -> pd.DataFrame:
    if "event_id" in event and "event_id" in log:
        return log[log["event_id"] == event["event_id"]]
    return log


def column_of(dataset_id: str, term_id: str, terms: dict) -> str:
    term = terms.get(term_id)
    return term["column"] if term and term["dataset_id"] == dataset_id else term_id


def metric_label(meaning: str) -> str:
    return METRIC_LABEL.get(meaning) or meaning.replace("_", " ").capitalize()


def _same(a: tuple, b: tuple) -> bool:
    """Equal key, or a date-only row and a campaign × date row of the same meaning and date (one campaign per day)."""
    if a == b:
        return True
    return a[0] == b[0] and a[2] is not None and a[2] == b[2] and (a[1] is None) != (b[1] is None)


def changed_values(log: pd.DataFrame, event: dict, terms: dict) -> pd.DataFrame:
    order = {a["dataset_id"]: i for i, a in enumerate(fabric_control.affected_by(event))}
    groups: list[dict[str, Any]] = []
    for row in _for_event(log, event).to_dict("records"):
        column = column_of(row["dataset_id"], row["term_id"], terms)
        grain = _json(row["grain_key"])
        meaning = MEANING.get((_short(row["dataset_id"]), column), column)
        key = (meaning, grain.get("campaign_id"), grain.get("date"))
        values = (row["old_value"], row["new_value"])
        match = next((g for g in groups if g["values"] == values and _same(g["key"], key)), None)
        pos = order.get(row["dataset_id"], len(order))
        if match is None:
            match = {"key": key, "values": values, "pos": pos, "rows": []}
            groups.append(match)
        elif match["key"][1] is None:  # a date-only row came first: keep the campaign × date level
            match["key"] = key
        match["pos"] = min(match["pos"], pos)
        match["rows"].append((row["dataset_id"], column))
    groups.sort(key=lambda g: (g["pos"], g["key"][0]))
    out = []
    for g in groups:
        meaning, campaign, date = g["key"]
        info = INFO_TERM.get(meaning)
        defined = info in terms and (terms[info]["dataset_id"], terms[info]["column"]) in g["rows"]
        old, new = g["values"]
        out.append(
            {
                "metric": metric_label(meaning),
                "info_term": info if defined else None,
                "level": f"{campaign} · {date}" if campaign and date else date or "Campaign total",
                "page": PAGE_OF.get(_short(min(g["rows"], key=lambda r: order.get(r[0], len(order)))[0])),
                "old": old,
                "new": new,
                "change": None if pd.isna(old) or pd.isna(new) else round(float(new) - float(old), 2),
            }
        )
    columns = ["metric", "info_term", "level", "page", "old", "new", "change"]
    return pd.DataFrame(out, columns=columns, dtype=object)  # object keeps None (no ⓘ) as None, not NaN


def kept(
    frames: dict[str, pd.DataFrame | None], metrics: dict[str, list[str]], emitted_at: datetime
) -> tuple[int, datetime | None]:
    count, latest = 0, None
    for dataset_id, frame in frames.items():
        if frame is None or "_refreshed_at" not in frame:
            continue
        rows = frame[frame["_refreshed_at"] < emitted_at]
        if rows.empty:
            continue
        count += len(rows) * sum(c in frame for c in metrics.get(dataset_id, []))
        top = rows["_refreshed_at"].max()
        latest = top if latest is None else max(latest, top)
    return count, latest


def event_table(events: pd.DataFrame, runs: pd.DataFrame, log: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    terms = load_terms()
    runs = with_emitted_at(runs, events)
    out = []
    for row in events.sort_values("emitted_at", ascending=False).head(limit).to_dict("records"):
        event = _event(row)
        rows = _for_event(log, event)
        date = _first(event["keys"].get("date"))
        new = next(
            (
                r["new_value"]
                for r in rows.to_dict("records")
                if r["dataset_id"] == CHANGE_DATASET and column_of(CHANGE_DATASET, r["term_id"], terms) == "allocated"
            ),
            None,
        )
        out.append(
            {
                "event_id": event["event_id"],
                "saved_at": event["emitted_at"],
                "change": f"Allocated spend for {date} " + ("changed" if new is None else f"set to {float(new):,.2f}"),
                "campaign_id": _first(event["keys"].get("campaign_id")),
                "datasets": len(fabric_control.affected_by(event)) - 1,
                "values_changed": len(changed_values(rows, event, terms)),
                "refresh_seconds": event_runs(runs, event["event_id"])[1],
            }
        )
    return pd.DataFrame(
        out, columns=["event_id", "saved_at", "change", "campaign_id", "datasets", "values_changed", "refresh_seconds"]
    )


def _column(dataset_id: str) -> str:
    if dataset_id.startswith("raw/"):
        return "Source"
    if dataset_id.startswith("unified/"):
        return "Unified"
    return "Shared marts" if dataset_id.startswith("mart_shared.") else "Page marts"


def _refreshed(run: dict | None) -> str:
    ended = run and run.get("ended_at")
    return "Not refreshed yet" if ended is None or pd.isna(ended) else f"Refreshed {ended:%H:%M}"


def flow(event: dict, runs: pd.DataFrame, log: pd.DataFrame) -> list[tuple[str, list[dict]]]:
    chosen, _ = event_runs(runs, event["event_id"])
    by_job = {r["job_id"]: r for r in chosen.to_dict("records")}  # start order: latest run per job wins
    counts = _for_event(log, event)["dataset_id"].value_counts().to_dict()
    columns: dict[str, list[dict]] = {c: [] for c in COLUMNS}
    first_output: set[str] = set()
    for item in fabric_control.affected_by(event):
        dataset_id, job_id = item["dataset_id"], item["job_id"]
        column, run = _column(dataset_id), by_job.get(job_id)
        first = job_id not in first_output
        first_output.add(job_id)
        k = counts.get(dataset_id, 0)
        chip = ("info", f"{k} changed") if k else RECOMPUTED
        meta = _refreshed(run)
        if column == "Source":
            version = int(event["source_version"])
            meta, chip = f"Source version {version - 1} → {version}", ("info", "Edited")
        elif column == "Unified" and first and run and pd.notna(run.get("delta_version")):
            meta = f"Delta version {int(run['delta_version_before'])} → {int(run['delta_version'])}"
        page = PAGE_OF.get(_short(dataset_id)) if column == "Page marts" else None
        columns[column].append(
            {"dataset_id": dataset_id, "label": label(dataset_id), "meta": meta, "chip": chip, "page": page}
        )
    return list(columns.items())


def not_downstream(event: dict) -> list[str]:
    affected = {a["dataset_id"] for a in fabric_control.affected_by(event)}
    return sorted(label(d) for d in fabric_control.load_registry() if d.startswith("mart_") and d not in affected)

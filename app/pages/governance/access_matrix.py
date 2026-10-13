import pandas as pd
import streamlit as st

import fabric_control
from app.shell import STATUS_COLORS, Filter, empty_state, filter_bar
from app.shell.roles import ROLES

ALL = "All datasets"
# DESIGN.md access matrix: allow = success, mask = warning, deny = neutral; icon + word, never color alone.
CELLS = {"allow": ("✓ allow", STATUS_COLORS["success"]), "deny": ("⊘ deny", STATUS_COLORS["muted"])}
MASK = ("◐ mask", STATUS_COLORS["warning"])


def cell(action: str) -> str:
    return (MASK if action.startswith("mask") else CELLS[action])[0]


def matrix(rows: list[dict], dataset_id: str = ALL) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["role", "dataset_id", "column", "action"])
    if dataset_id != ALL:
        df = df[df["dataset_id"] == dataset_id]
    df = df.assign(action=df["action"].map(cell))
    grid = df.pivot(index=["dataset_id", "column"], columns="role", values="action")
    grid = grid.reindex(columns=[code for code in ROLES if code in grid.columns])
    grid.columns = [ROLES[code].label for code in grid.columns]
    return grid.reset_index().rename(columns={"dataset_id": "Dataset", "column": "Column"})


def color(text: str) -> str:
    for label, value in [*CELLS.values(), MASK]:
        if text == label:
            return f"color: {value}; font-weight: 600"
    return ""


def render() -> None:
    rows = fabric_control.effective_matrix()
    if not rows:
        empty_state("No access policy in effect yet.", "Policies appear after migrations and sync_policies() run.")
        return
    datasets = sorted({r["dataset_id"] for r in rows})
    chosen = filter_bar("access_matrix", [Filter("dataset", "Dataset", [ALL, *datasets], ALL)])["dataset"]
    grid = matrix(rows, chosen)
    roles = [c for c in grid.columns if c not in ("Dataset", "Column")]
    st.dataframe(grid.style.map(color, subset=roles), hide_index=True, width="stretch")
    st.caption("Read from ops.policy_effective: what Postgres enforces, cross-checked by verify_policies(). Read-only.")

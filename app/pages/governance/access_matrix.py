import pandas as pd
import streamlit as st

import fabric_control
from app.shell import STATUS_COLORS, Filter, empty_state, filter_bar
from app.shell.roles import ROLES
from fabric_control.policy import load_policy

ALL = "All datasets"
# DESIGN.md access matrix: allow = success, mask = warning, deny = neutral; icon + word, never color alone.
CELLS = {"allow": ("✓ allow", STATUS_COLORS["success"]), "deny": ("⊘ deny", STATUS_COLORS["muted"])}
MASK = ("◐ mask", STATUS_COLORS["warning"])


def cell(action: str) -> str:
    return (MASK if action.startswith("mask") else CELLS[action])[0]


def policy_columns() -> set[tuple[str, str]]:
    """(dataset, column) whose tag masks or denies some role (FR-20); other columns follow the dataset's readers."""
    policy = load_policy()
    return {
        (dataset_id, column)
        for dataset_id, columns in policy.column_tags.items()
        for column in columns
        if any(policy.tag_action(role, dataset_id, column) != "allow" for role in policy.roles)
    }


def matrix(rows: list[dict], dataset_id: str = ALL) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["role", "dataset_id", "column", "action"])
    if dataset_id != ALL:
        df = df[df["dataset_id"] == dataset_id]
    df = df.assign(action=df["action"].map(cell))
    grid = df.pivot(index=["dataset_id", "column"], columns="role", values="action")
    grid = grid.reindex(columns=[code for code in ROLES if code in grid.columns]).rename_axis(columns=None)
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
    if not st.toggle(
        "Show all columns",
        key="access_matrix_all_columns",
        help="Off: only columns whose tag masks or denies a role. The others follow who can read the dataset.",
    ):
        tagged = policy_columns()
        rows = [r for r in rows if (r["dataset_id"], r["column"]) in tagged]
    grid = matrix(rows, chosen)
    if grid.empty:
        empty_state(f"No column in {chosen} has a mask or deny tag.", "Turn on Show all columns to see every column.")
        return
    roles = [c for c in grid.columns if c not in ("Dataset", "Column")]
    st.caption(" · ".join(f"{code} {ROLES[code].name}" for code in roles))
    st.dataframe(
        grid.style.map(color, subset=roles),
        hide_index=True,
        width="stretch",
        column_config={code: st.column_config.TextColumn(help=ROLES[code].label) for code in roles},
    )
    st.caption("Read from ops.policy_effective: what Postgres enforces, cross-checked by verify_policies(). Read-only.")

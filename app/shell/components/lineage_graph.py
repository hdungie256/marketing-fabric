"""Left-to-right lineage DAG (Story 2.3, FR-15, UX-DR15).

Pure-Streamlit columns-per-layer rendering: no extra dependencies, works in
AppTest, keyboard-operable through the node selectbox. Node detail appears
below the graph; stale nodes carry the warning treatment.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

import fabric_control
from app.shell import session
from app.shell.components.status_chip import status_chip
from app.shell.format import fmt_time
from app.shell.navigation import can_open

LAYER_ORDER = ["raw", "unified", "mart", "serving"]


def layer_of(node: dict[str, Any]) -> str:
    layer = node.get("layer") or "serving"
    return layer if layer in LAYER_ORDER else "serving"


def columns_of(graph: dict[str, list]) -> list[list[dict[str, Any]]]:
    """Group nodes into left-to-right layer columns, sorted for determinism."""
    buckets: dict[str, list[dict[str, Any]]] = {layer: [] for layer in LAYER_ORDER}
    for node in graph["nodes"]:
        buckets[layer_of(node)].append(node)
    return [[n for n in sorted(bucket, key=lambda n: n["dataset_id"])] for bucket in buckets.values() if bucket]


def node_label(node: dict[str, Any]) -> str:
    return node["dataset_id"]


def render_node(node: dict[str, Any], selected: bool) -> None:
    with st.container(border=True, key=f"lineage-node-{node['dataset_id']}"):
        st.markdown(f"**{node['dataset_id']}**")
        refreshed = node.get("refreshed_at")
        st.caption(f"Refreshed {fmt_time(refreshed)}" if refreshed else "Not refreshed yet")
        version = node.get("version")
        if version is not None:
            st.caption(f"Version {version}")
        score, status = node.get("score"), node.get("status")
        if status == "not yet measured":
            status_chip("neutral", "Quality not yet measured")
        elif score is not None:
            variant = "success" if status == "Green" else "warning" if status == "Amber" else "danger"
            status_chip(variant, f"{status} {score:.0f}%")
        if selected:
            status_chip("info", "Selected")


def render_detail(node: dict[str, Any]) -> None:
    st.subheader(node["dataset_id"])
    st.write(f"Owner: {node.get('owner') or '—'}")
    st.write(f"Sources: {', '.join(node.get('sources') or []) or '—'}")
    st.write(f"Provenance: {node.get('provenance') or '—'}")
    refreshed = node.get("refreshed_at")
    st.write(f"Last refresh: {fmt_time(refreshed) if refreshed else '—'}")
    version = node.get("version")
    st.write(f"Version: {version if version is not None else '—'}")
    score, status = node.get("score"), node.get("status")
    st.write(f"Quality: {status if status else '—'}" + (f" ({score:.0f}%)" if score is not None else ""))


def lineage_graph(dataset_id: str, depth: int = 1, key: str = "lineage") -> None:
    """Draw the source → metric DAG around `dataset_id` with node detail."""
    graph = fabric_control.lineage(dataset_id, depth)
    if not graph["nodes"]:
        st.caption("No lineage recorded for this dataset yet.")
        return
    columns = columns_of(graph)
    marked = st.session_state.get(f"{key}-node", dataset_id)
    row = st.columns(len(columns))
    for column, bucket in zip(row, columns, strict=True):
        with column:
            for node in bucket:
                render_node(node, selected=(node["dataset_id"] == marked))
            if len(columns) > 1:
                st.caption("→")
    ids = sorted(node["dataset_id"] for node in graph["nodes"])
    default = dataset_id if dataset_id in ids else ids[0]
    chosen = st.selectbox("Dataset", ids, index=ids.index(default), key=f"{key}-node")
    render_detail(next(n for n in graph["nodes"] if n["dataset_id"] == chosen))


def lineage_flow(columns: list[tuple[str, list[dict[str, Any]]]], key: str = "flow") -> None:
    """Draw a change event's flow: one column per layer, nodes carry a chip and optional page link."""
    row = st.columns(len(columns))
    for index, (column, (title, nodes)) in enumerate(zip(row, columns, strict=True)):
        with column:
            st.caption(title)
            for node in nodes:
                with st.container(border=True, key=f"{key}-node-{node['dataset_id']}"):
                    st.markdown(f"**{node['label']}**")
                    st.markdown(f"`{node['dataset_id']}`")
                    st.caption(node["meta"])
                    status_chip(*node["chip"])
                    page = node.get("page")
                    if page and not can_open(session.role(), page):
                        st.caption(f"{node['label']} page")  # the role cannot open it: text, not a dead button
                    elif page and st.button(f"Open {node['label']} page", key=f"{key}-open-{node['dataset_id']}"):
                        session.request_redirect(node["page"])
                        st.rerun()
            if index < len(columns) - 1:
                st.caption("→")

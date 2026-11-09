"""Left-to-right lineage DAG (Story 2.3, FR-15, UX-DR15).

Graphviz rendering through st.graphviz_chart (built into Streamlit): one rank
per layer, edges from the lineage graph, nodes tinted by quality status, the
selected node outlined. Keyboard-operable through the node selectbox; node
detail appears below the graph.
"""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

import fabric_control
from app.shell import session
from app.shell.components.status_chip import status_chip
from app.shell.format import fmt_time
from app.shell.navigation import can_open

LAYER_ORDER = ["raw", "unified", "mart", "serving"]
STATUS_FILL = {"Green": "#E7F4EA", "Amber": "#FDF0E1", "Red": "#FBE9E7"}
# Reaches the raw sources of every glossary dataset (test_lineage_page guards it). It is also
# OpenMetadata's lineage depth cap: a deeper request fails and falls back to job declarations.
SOURCE_DEPTH = 3


def layer_of(node: dict[str, Any]) -> str:
    layer = node.get("layer") or "serving"
    return layer if layer in LAYER_ORDER else "serving"


def columns_of(graph: dict[str, list]) -> list[list[dict[str, Any]]]:
    """Group nodes into left-to-right layer columns, sorted for determinism."""
    buckets: dict[str, list[dict[str, Any]]] = {layer: [] for layer in LAYER_ORDER}
    for node in graph["nodes"]:
        buckets[layer_of(node)].append(node)
    return [[n for n in sorted(bucket, key=lambda n: n["dataset_id"])] for bucket in buckets.values() if bucket]


def quality_text(node: dict[str, Any]) -> str:
    score, status = node.get("score"), node.get("status")
    if status == "not yet measured":
        return "Quality not yet measured"
    return f"{status} {score:.0f}%" if score is not None else ""


def lineage_dot(graph: dict[str, list], selected: str) -> str:
    """Graphviz DOT for a lineage graph: left to right, one rank per layer, `selected` outlined.

    Node ids are positional (n0, n1, ...) and labels are HTML-escaped, so no dataset id reaches DOT syntax.
    """
    columns = columns_of(graph)
    ids = {node["dataset_id"]: f"n{i}" for i, node in enumerate(n for bucket in columns for n in bucket)}
    lines = [
        "digraph lineage {",
        '  graph [rankdir=LR, bgcolor="transparent"];',
        '  node [shape=box, style="rounded,filled", fontname="sans-serif", fontsize=11, color="#5B6472"];',
    ]
    for bucket in columns:
        lines.append("  { rank=same;")
        for node in bucket:
            label = html.escape(node["dataset_id"])
            if quality := quality_text(node):
                label += f'<br/><font point-size="9">{html.escape(quality)}</font>'
            attrs = f'label=<{label}>, fillcolor="{STATUS_FILL.get(node.get("status"), "white")}"'
            if node["dataset_id"] == selected:
                attrs += ', color="#2F5BEA", penwidth=3'
            lines.append(f"    {ids[node['dataset_id']]} [{attrs}];")
        lines.append("  }")
    lines += [f"  {ids[edge['from']]} -> {ids[edge['to']]};" for edge in graph["edges"]]
    return "\n".join([*lines, "}"])


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
    marked = st.session_state.get(f"{key}-node", dataset_id)
    st.graphviz_chart(lineage_dot(graph, marked), width="stretch")
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

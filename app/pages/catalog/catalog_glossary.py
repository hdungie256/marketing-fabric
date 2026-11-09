"""Catalog & Glossary page with keyword search (Story 2.5, BR13, FR-10, FR-13)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import fabric_control
from app.shell import empty_state, table
from app.shell.components.definition_dialog import definition_dialog
from app.shell.components.lineage_graph import SOURCE_DEPTH, lineage_graph, render_detail

KEY = "catalog_glossary"
BROWSE_COLUMNS = ["dataset_id", "layer", "description", "owner", "sources", "provenance", "score", "status"]


def browse_frame(items: list[dict]) -> pd.DataFrame:
    rows = [
        {
            "dataset_id": item["dataset_id"],
            "layer": item["layer"],
            "description": item.get("description") or "",
            "owner": item.get("owner") or "",
            "sources": ", ".join(item.get("sources") or []),
            "provenance": item.get("provenance") or "",
            "score": item.get("score"),
            "status": item.get("status") or "",
        }
        for item in items
    ]
    return pd.DataFrame(rows, columns=BROWSE_COLUMNS)


def render_search(q: str) -> None:
    hits = fabric_control.search(q)
    if not hits:
        st.markdown(f"No datasets or terms match '{q}'.")
        return
    for hit in hits:
        label = f"{'ⓘ' if hit['kind'] == 'term' else '▦'} {hit['name']}"
        if st.button(label, key=f"catalog-hit-{hit['kind']}-{hit['id']}"):
            st.session_state["catalog_selected"] = hit
    selected = st.session_state.get("catalog_selected")
    if selected is None:
        return
    if selected["kind"] == "term":
        definition_dialog(selected["id"])
    else:
        item = next(i for i in fabric_control.catalog() if i["dataset_id"] == selected["id"])
        render_detail(item)
        lineage_graph(selected["id"], depth=SOURCE_DEPTH, key=f"{KEY}-selected")


def render() -> None:
    q = st.text_input("Search datasets and terms", key=f"{KEY}-q")
    if q:
        render_search(q)
        return
    st.session_state.pop("catalog_selected", None)
    items = fabric_control.catalog()
    if not items:
        empty_state("No datasets registered yet.")
        return
    table(browse_frame(items))

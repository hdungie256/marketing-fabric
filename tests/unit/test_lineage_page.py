"""Story 2.3 tests: layer columns, graph rendering, Lineage page."""

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from app.shell.components import lineage_graph as graph  # noqa: E402

NODES = [
    {
        "dataset_id": "raw/sales/lines",
        "layer": "raw",
        "owner": "platform",
        "sources": ["sales"],
        "provenance": "original",
        "refreshed_at": None,
        "version": 3,
        "score": 100.0,
        "status": "Green",
    },
    {
        "dataset_id": "unified/orders",
        "layer": "unified",
        "owner": "p3",
        "sources": ["sales"],
        "provenance": "original",
        "refreshed_at": None,
        "version": 7,
        "score": 92.0,
        "status": "Amber",
    },
    {
        "dataset_id": "mart_campaign.overview",
        "layer": "mart",
        "owner": "p2",
        "sources": ["sales"],
        "provenance": "original",
        "refreshed_at": None,
        "version": None,
        "score": None,
        "status": "not yet measured",
    },
]
GRAPH = {
    "nodes": NODES,
    "edges": [
        {"from": "raw/sales/lines", "to": "unified/orders", "job_id": "unified/orders"},
        {"from": "unified/orders", "to": "mart_campaign.overview", "job_id": "marts/campaign/overview"},
    ],
}


def test_columns_group_layers_left_to_right_sorted():
    columns = graph.columns_of(GRAPH)
    assert [[n["dataset_id"] for n in bucket] for bucket in columns] == [
        ["raw/sales/lines"],
        ["unified/orders"],
        ["mart_campaign.overview"],
    ]


def test_unknown_layer_falls_back_to_serving():
    assert graph.layer_of({"layer": "weird"}) == "serving"


def _graph_script():
    from app.shell.components import lineage_graph as graph

    graph.lineage_graph("unified/orders", 1)


def _empty_script():
    from app.shell.components import lineage_graph as graph

    graph.lineage_graph("unified/orders", 1)


def _page_script():
    from app.pages.catalog import lineage as lineage_page

    lineage_page.render()


def test_graph_renders_nodes_and_detail(monkeypatch):
    monkeypatch.setattr("fabric_control.lineage", lambda dataset_id, depth=1: GRAPH)
    at = AppTest.from_function(_graph_script).run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "raw/sales/lines" in text
    assert "unified/orders" in text
    assert "Amber 92%" in text
    assert "Quality not yet measured" in text
    assert at.subheader[0].value == "unified/orders"
    at.selectbox(key="lineage-node").set_value("raw/sales/lines").run()
    assert at.subheader[0].value == "raw/sales/lines"


def test_empty_graph_shows_caption(monkeypatch):
    monkeypatch.setattr("fabric_control.lineage", lambda dataset_id, depth=1: {"nodes": [], "edges": []})
    at = AppTest.from_function(_empty_script).run()
    assert not at.exception
    assert "No lineage recorded for this dataset yet." in [c.value for c in at.caption]


def test_lineage_page_lists_catalog_datasets(monkeypatch):
    monkeypatch.setattr(
        "fabric_control.catalog",
        lambda filter=None: [{"dataset_id": "unified/orders"}, {"dataset_id": "unified/customers"}],
    )
    monkeypatch.setattr("fabric_control.lineage", lambda dataset_id, depth=1: {"nodes": [], "edges": []})
    at = AppTest.from_function(_page_script).run()
    assert not at.exception
    assert set(at.selectbox(key="_filter_lineage_dataset").options) == {"unified/orders", "unified/customers"}

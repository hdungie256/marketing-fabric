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


def test_dot_draws_edges_one_rank_per_layer_and_outlines_selected():
    dot = graph.lineage_dot(GRAPH, "unified/orders")
    assert dot.startswith("digraph lineage {") and "rankdir=LR" in dot
    ranks = dot.split("{ rank=same;")[1:]
    assert [("raw/sales/lines" in r, "unified/orders" in r, "mart_campaign.overview" in r) for r in ranks] == [
        (True, False, False),
        (False, True, False),
        (False, False, True),
    ]
    assert "n0 -> n1;" in dot and "n1 -> n2;" in dot
    assert "n1 [label=<unified/orders<br/>" in dot and "Amber 92%" in dot and "Quality not yet measured" in dot
    assert [line for line in dot.splitlines() if "penwidth" in line] == [
        '    n1 [label=<unified/orders<br/><font point-size="9">Amber 92%</font>>, fillcolor="#FDF0E1",'
        ' color="#2F5BEA", penwidth=3];'
    ]


def test_dot_escapes_labels_and_keeps_ids_out_of_dot_syntax():
    tricky = 'raw/x"]; evil -> "<b>&\\'
    dot = graph.lineage_dot({"nodes": [{"dataset_id": tricky, "layer": "raw"}], "edges": []}, tricky)
    assert "label=<raw/x&quot;]; evil -&gt; &quot;&lt;b&gt;&amp;\\>" in dot
    assert tricky not in dot and "->" not in dot.replace("-&gt;", "")


def test_source_depth_reaches_every_raw_source_of_glossary_datasets(monkeypatch):
    import fabric_control
    from fabric_control.catalog import ancestors, layer, snapshot
    from fabric_control.glossary import load_terms

    monkeypatch.setenv("FABRIC_CONTROL_MODE", "offline")
    upstream = snapshot().graph
    datasets = {entry["dataset_id"] for entry in load_terms().values()}
    assert "mart_finance.budget_daily" in datasets  # the 2026-10-29 review case: depth 2 missed raw/spend, raw/sales
    for dataset_id in datasets:
        raw = {d for d in ancestors(upstream, dataset_id) if layer(d) == "raw"}
        nodes = {n["dataset_id"] for n in fabric_control.lineage(dataset_id, graph.SOURCE_DEPTH)["nodes"]}
        assert raw <= nodes, dataset_id


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
    assert at.get("graphviz_chart")[0].proto.spec == graph.lineage_dot(GRAPH, "unified/orders")
    assert at.subheader[0].value == "unified/orders"
    at.selectbox(key="lineage-node").set_value("raw/sales/lines").run()
    assert at.subheader[0].value == "raw/sales/lines"
    assert at.get("graphviz_chart")[0].proto.spec == graph.lineage_dot(GRAPH, "raw/sales/lines")


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


def _flow_script(role):
    from app.shell import session
    from app.shell.components.lineage_graph import lineage_flow

    session.set_role(role)

    def node(i, page):
        return {
            "dataset_id": f"ds/{i}",
            "label": f"Label {i}",
            "meta": f"meta {i}",
            "chip": ("info", f"chip {i}"),
            "page": page,
        }

    lineage_flow(
        [
            ("Source", [node(1, None)]),
            ("Unified", [node(2, None)]),
            ("Shared marts", [node(3, None), node(4, "targets")]),
            ("Page marts", [node(5, "targets"), node(6, "budget_spend"), node(7, None), node(8, None)]),
        ]
    )


def test_lineage_flow_renders_all_nodes_and_page_buttons():
    at = AppTest.from_function(_flow_script, kwargs={"role": "UG03"}).run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert all(f"Label {i}" in text and f"ds/{i}" in text for i in range(1, 9))
    assert [b.label for b in at.button] == ["Open Label 4 page", "Open Label 5 page", "Open Label 6 page"]


def test_lineage_flow_shows_text_for_pages_the_role_cannot_open():
    at = AppTest.from_function(_flow_script, kwargs={"role": "UG04"}).run()
    assert not at.exception
    assert [b.label for b in at.button] == ["Open Label 6 page"]
    assert "Label 4 page" in [c.value for c in at.caption]

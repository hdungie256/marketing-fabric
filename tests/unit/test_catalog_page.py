"""Story 2.5 tests: browse, search, BR13 scenario, term usage guard."""

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import fabric_control  # noqa: E402

ITEMS = [
    {
        "dataset_id": "unified/orders",
        "layer": "unified",
        "description": "orders",
        "owner": "p3",
        "sources": ["sales"],
        "provenance": "original",
        "refreshed_at": None,
        "version": 1,
        "score": 100.0,
        "status": "Green",
    },
]
TERM = {
    "term_id": "attributed_value_per_spend_ratio",
    "display_name": "Attributed Value / Spend Ratio",
    "definition": "d",
    "formula": "f",
    "dataset_id": "mart_finance.budget_daily",
    "column": "attributed_gross_value",
    "rules": ["R7"],
    "limitations": ["Not ROAS."],
    "owner_slice": "finance",
    "notes": [],
    "provenance": "synthetic",
    "synthetic": True,
    "refreshed_at": None,
    "score": None,
    "status": "not yet measured",
}


def _page_script():
    from app.pages.catalog import catalog_glossary

    catalog_glossary.render()


def test_browse_lists_every_dataset(monkeypatch):
    monkeypatch.setattr("fabric_control.catalog", lambda filter=None: ITEMS)
    at = AppTest.from_function(_page_script).run()
    assert not at.exception
    assert at.dataframe[0].value["dataset_id"].tolist() == ["unified/orders"]


def test_search_without_match_shows_exact_message(monkeypatch):
    monkeypatch.setattr("fabric_control.catalog", lambda filter=None: ITEMS)
    monkeypatch.setattr("fabric_control.search", lambda q: [])
    at = AppTest.from_function(_page_script).run()
    at.text_input(key="catalog_glossary-q").input("zzz-no-such-thing").run()
    assert not at.exception
    assert "No datasets or terms match 'zzz-no-such-thing'." in [m.value for m in at.markdown]


def test_search_term_hit_opens_definition_dialog(monkeypatch):
    hit = {"kind": "term", "id": TERM["term_id"], "name": TERM["display_name"], "description": "d"}
    monkeypatch.setattr("fabric_control.catalog", lambda filter=None: ITEMS)
    monkeypatch.setattr("fabric_control.search", lambda q: [hit])
    monkeypatch.setattr("fabric_control.term", lambda term_id: TERM)
    monkeypatch.setattr("fabric_control.status", lambda dataset_id: {"stale": False})
    monkeypatch.setattr("fabric_control.lineage", lambda dataset_id, depth=1: {"nodes": [], "edges": []})
    at = AppTest.from_function(_page_script).run()
    at.text_input(key="catalog_glossary-q").input("spend ratio").run()
    at.button(key=f"catalog-hit-term-{TERM['term_id']}").click().run()
    assert not at.exception
    assert sorted(t.label for t in at.tabs) == ["Definition", "Lineage", "Quality"]


def test_search_dataset_hit_shows_detail_and_graph(monkeypatch):
    hit = {"kind": "dataset", "id": "unified/orders", "name": "unified/orders", "description": "orders"}
    monkeypatch.setattr("fabric_control.catalog", lambda filter=None: ITEMS)
    monkeypatch.setattr("fabric_control.search", lambda q: [hit])
    monkeypatch.setattr("fabric_control.lineage", lambda dataset_id, depth=1: {"nodes": ITEMS, "edges": []})
    at = AppTest.from_function(_page_script).run()
    at.text_input(key="catalog_glossary-q").input("orders").run()
    at.button(key="catalog-hit-dataset-unified/orders").click().run()
    assert not at.exception
    assert at.subheader[0].value == "unified/orders"


def test_br13_ratio_term_is_searchable_with_not_roas_and_synthetic():
    hits = fabric_control.search("Attributed Value / Spend Ratio")
    term_hits = [h for h in hits if h["kind"] == "term"]
    assert [h["id"] for h in term_hits] == ["attributed_value_per_spend_ratio"]
    term = fabric_control.term("attributed_value_per_spend_ratio")
    assert term["display_name"] == "Attributed Value / Spend Ratio"
    assert term["formula"] and term["dataset_id"] and term["column"] and term["owner_slice"]
    assert term["source_columns"] == ["attributed_gross_value", "allocated"]
    assert any("roas" in item.lower() for item in term["limitations"])
    assert term["synthetic"] is True
    assert [h["id"] for h in fabric_control.search("ROAS") if h["kind"] == "term"] == [term["term_id"]]


def test_roas_search_opens_ratio_term_with_not_roas_caution(monkeypatch):
    monkeypatch.setattr("fabric_control.status", lambda dataset_id: {"stale": False})
    monkeypatch.setattr("fabric_control.lineage", lambda dataset_id, depth=1: {"nodes": [], "edges": []})
    at = AppTest.from_function(_page_script).run()
    at.text_input(key="catalog_glossary-q").input("ROAS").run()
    at.button(key="catalog-hit-term-attributed_value_per_spend_ratio").click().run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Not ROAS" in text
    assert "`mart_finance.budget_daily.attributed_gross_value`, `mart_finance.budget_daily.allocated`" in text

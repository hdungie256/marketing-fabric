"""Story 2.4 tests: definition dialog content and the metric/table info buttons."""

from datetime import UTC, datetime

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

RATIO_TERM = {
    "term_id": "attributed_value_per_spend_ratio",
    "display_name": "Attributed Value / Spend Ratio",
    "definition": "Attributed gross value per unit of allocated spend.",
    "formula": "SUM(attributed_gross_value) / SUM(allocated)",
    "dataset_id": "mart_finance.budget_daily",
    "column": "attributed_gross_value",
    "rules": ["R6", "R7", "R8"],
    "limitations": ["Not ROAS (R7): attribution is a sample rule."],
    "owner_slice": "finance",
    "notes": ["attributed_not_incremental"],
    "provenance": "synthetic",
    "synthetic": True,
    "refreshed_at": datetime(2026, 10, 5, 7, 5, tzinfo=UTC),
    "score": 100.0,
    "status": "Green",
}
GRAPH = {
    "nodes": [
        {
            "dataset_id": "mart_finance.budget_daily",
            "layer": "mart",
            "owner": "p4",
            "sources": ["spend"],
            "provenance": "original",
            "refreshed_at": None,
            "version": 2,
            "score": 100.0,
            "status": "Green",
        },
    ],
    "edges": [],
}


@pytest.fixture
def stubs(monkeypatch):
    monkeypatch.setattr("fabric_control.term", lambda term_id: RATIO_TERM if term_id == RATIO_TERM["term_id"] else None)
    monkeypatch.setattr("fabric_control.status", lambda dataset_id: {"stale": False})
    monkeypatch.setattr("fabric_control.lineage", lambda dataset_id, depth=1: GRAPH)


def _metric_script():
    from datetime import UTC, datetime

    from app.shell.metric import metric

    metric("attributed_value_per_spend_ratio", 3.21, datetime(2026, 10, 5, 7, 5, tzinfo=UTC), kind="money")


def _table_script():
    import pandas as pd

    from app.shell.table import table

    table(
        pd.DataFrame({"ratio": [3.21]}),
        info_terms={"ratio": "attributed_value_per_spend_ratio"},
    )


def test_metric_info_button_opens_definition_dialog(stubs):
    at = AppTest.from_function(_metric_script).run()
    assert not at.exception
    at.button(key="metric-info-attributed_value_per_spend_ratio").click().run()
    assert not at.exception
    assert sorted(t.label for t in at.tabs) == ["Definition", "Lineage", "Quality"]
    text = " ".join(m.value for m in at.markdown)
    assert "Attributed Value / Spend Ratio" in text
    assert "SUM(attributed_gross_value) / SUM(allocated)" in text
    assert "mart_finance.budget_daily.attributed_gross_value" in text
    assert "Not ROAS" in text


def test_table_info_button_opens_definition_dialog(stubs):
    at = AppTest.from_function(_table_script).run()
    assert not at.exception
    at.button(key="table-info-ratio").click().run()
    assert not at.exception
    assert sorted(t.label for t in at.tabs) == ["Definition", "Lineage", "Quality"]


def test_unknown_term_dialog_shows_error(stubs):
    def _unknown_script():
        from app.shell.components.definition_dialog import definition_dialog

        definition_dialog("nope")

    at = AppTest.from_function(_unknown_script).run()
    assert not at.exception
    assert "Unknown metric nope" in " ".join(e.value for e in at.error)


def _overview_script():
    from app.pages.campaign import overview

    overview.render()


def test_overview_cards_each_open_the_dialog(monkeypatch):
    terms = {
        term_id: {
            "display_name": term_id,
            "notes": [],
            "dataset_id": "mart_campaign.campaign_overview",
            "definition": "d",
            "formula": "f",
            "column": "c",
            "rules": [],
            "limitations": [],
            "owner_slice": "campaign",
            "synthetic": False,
            "score": 100.0,
            "status": "Green",
            "refreshed_at": None,
        }
        for term_id in (
            "attributed_orders",
            "attributed_buyers",
            "attributed_gross_value",
            "average_order_value",
        )
    }
    monkeypatch.setattr("fabric_control.term", terms.get)
    monkeypatch.setattr("fabric_control.status", lambda dataset_id: {"stale": False})
    monkeypatch.setattr("fabric_control.lineage", lambda dataset_id, depth=1: {"nodes": [], "edges": []})
    monkeypatch.setenv("APP_DATA_MODE", "fixture")
    at = AppTest.from_function(_overview_script).run()
    assert not at.exception
    for term_id in terms:
        at.button(key=f"metric-info-{term_id}").click().run()
        assert not at.exception
        assert sorted(t.label for t in at.tabs) == ["Definition", "Lineage", "Quality"]

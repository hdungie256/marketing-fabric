"""Stories 5.3/5.4 AppTest: live count, save form, locked export, prefill, zero-match."""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app.pages.customer import audience_builder
from app.services import customers as svc


def frame():
    return pd.DataFrame(
        [
            (1, 5, 5, 6, 5, 600.0, 5, "Champions", "Apparel"),
            (3, 300, 1, 1, 1, 10.0, 1, "Lost", "Nest"),
        ],
        columns=[
            "customer_id",
            "recency_days",
            "recency_score",
            "frequency_orders",
            "frequency_score",
            "monetary_value",
            "monetary_score",
            "segment",
            "categories",
        ],
    )


class Source:
    def read(self, dataset_id):
        return frame()


class FakeConn:
    def __init__(self):
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        parent = self

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, sql, params=None):
                parent.rows.append(params)

        return Cursor()

    def execute(self, sql):
        class Cursor:
            description = []

            def fetchall(self):
                return []

        return Cursor()


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.setattr(audience_builder, "current_source", lambda: Source())
    monkeypatch.setattr(audience_builder, "connect_writer", lambda: FakeConn())
    monkeypatch.setattr(audience_builder, "connect_reader", lambda: FakeConn())
    monkeypatch.setenv("APP_DATA_MODE", "fixture")


def _script():
    from app.pages.customer import audience_builder

    audience_builder.render()


def test_live_count_updates_and_zero_match_shows_hint():
    at = AppTest.from_function(_script).run()
    assert not at.exception
    assert "**2 customers match**" in [m.value for m in at.markdown]
    at.selectbox(key="_filter_audience_builder_segment").set_value("Lost").run()
    at.selectbox(key="_filter_audience_builder_category").set_value("Apparel").run()
    assert not at.exception
    assert "**0 customers match**" in [m.value for m in at.markdown]
    assert "No customers match these criteria." in " ".join(m.value for m in at.markdown)


def test_save_audience_requires_name_then_toasts(monkeypatch):
    import app.pages.customer.audience_builder as page

    saved = {}
    monkeypatch.setattr(
        svc, "save_audience", lambda conn, name, crit, count, by: saved.setdefault("id", "abc") or "abc"
    )
    monkeypatch.setattr(page, "connect_writer", lambda: FakeConn())
    at = AppTest.from_function(_script).run()
    at.button(key="FormSubmitter:audience_builder-save-Save audience").click().run()
    assert not at.exception
    assert "Give the audience a name before saving." in [e.value for e in at.error]
    at.text_input(key="audience_builder-name").input("Win-back Fun").run()
    at.button(key="FormSubmitter:audience_builder-save-Save audience").click().run()
    assert not at.exception
    assert any("Audience saved" in t.value for t in at.toast)


def test_export_stays_locked_with_reason():
    at = AppTest.from_function(_script).run()
    assert not at.exception
    export = at.button(key="audience_builder-export")
    assert export.disabled
    assert "Contact export disabled — no marketing consent data (R12)" in [c.value for c in at.caption]


def test_win_back_prefill_arrives_in_builder(monkeypatch):
    def _prefilled():
        import streamlit as st

        st.session_state["audience_prefill"] = {"segment": "All", "category": "Nest", "min_orders": 1}
        from app.pages.customer import audience_builder

        audience_builder.render()

    at = AppTest.from_function(_prefilled).run()
    assert not at.exception
    assert "**1 customers match**" in [m.value for m in at.markdown]

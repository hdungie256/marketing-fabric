import json
from datetime import UTC, datetime

import pandas as pd
import pyarrow as pa
import pytest
from streamlit.testing.v1 import AppTest

import fabric_control
from app.pages.campaign import targets
from app.shell import STATUS_COLORS

AT = datetime(2026, 10, 19, 7, 5, tzinfo=UTC)
NAMES = {
    "first_observed_buyers": "First Observed Buyers",
    "attributed_orders": "Attributed Orders",
    "attributed_gross_value": "Attributed Gross Value",
    "target_achievement": "Target Achievement",
    "allocated_spend": "Allocated Spend",
}
STALE_DATASET = "mart_shared.campaign_spend_allocated"
SUBTITLE = "How far each campaign got toward its own goal."
FOOTNOTE = "Stop below 70%, Continue from 100%. Goals were set after the fact for this demo."
VERDICTS = {
    "Summer Drinkware": "Adjust",
    "Back-to-work Office": "Adjust",
    "Spring Nest": "Adjust",
    "Holiday Nest": "Continue",
    "New-year Apparel": "Continue",
}


def frame():
    data = [
        ("CMP19_01", "New-year Apparel", "attributed_gross_value", 25923.17, 28177.36, 1.086962, "continue"),
        ("CMP19_02", "Spring Nest", "attributed_orders", 495, 442, 0.892929, "adjust"),
        ("CMP19_03", "Summer Drinkware", "first_observed_buyers", 40, 28, 0.7, "adjust"),
        ("CMP19_04", "Back-to-work Office", "attributed_gross_value", 32428.42, 28953.95, 0.892853, "adjust"),
        ("CMP19_05", "Holiday Nest", "attributed_orders", 267, 290, 1.086142, "continue"),
    ]
    return pd.DataFrame(
        [
            {
                "campaign_id": c,
                "campaign_name": n,
                "target_metric": m,
                "target_value": t,
                "evaluation_from": "2019-01-01",
                "evaluation_through": "2019-12-31",
                "actual": a,
                "achievement": r,
                "allocated_spend": 18897.68,
                "recommendation": rec,
                "provenance": "synthetic",
                "_refreshed_at": AT,
                "_run_id": "r",
                "_source_version": "{}",
            }
            for c, n, m, t, a, r, rec in data
        ]
    )


class Source:
    def read(self, dataset_id):
        return frame()


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.setattr(
        fabric_control,
        "term",
        lambda t: {"display_name": NAMES[t], "notes": [], "synthetic": True} if t in NAMES else None,
    )
    monkeypatch.setattr(fabric_control, "record_timing", lambda page, ms: None)
    monkeypatch.setattr(fabric_control, "status", lambda d: {"stale": False, "datasets": []})
    monkeypatch.setattr(targets, "current_source", lambda: Source())


def _script():
    from app.pages.campaign import targets
    from app.shell import PageSpec, session
    from app.shell.page import wrap

    session.set_role("UG03")
    wrap(PageSpec("targets", "Targets", "Campaigns", targets.render, frozenset({"UG03"})))()


def text(at):
    return [*(m.value for m in at.markdown), *(c.value for c in at.caption), *(t.value for t in at.title)]


def dots_and_verdicts(at):
    """(layer spec, rows) of the ruler's dot layer and of its verdict text layer, as the page sent them."""
    chart = at.get("vega_lite_chart")[0].proto
    data = {d.name: pa.ipc.open_stream(d.data.data).read_pandas() for d in chart.datasets}
    layers = json.loads(chart.spec)["layer"]
    dots = next(layer for layer in layers if layer["mark"]["type"] == "circle")
    verdicts = next(layer for layer in layers if layer["encoding"].get("text", {}).get("field") == "verdict")
    return (dots, data[dots["data"]["name"]]), (verdicts, data[verdicts["data"]["name"]])


def test_ruler_rows_and_verdicts():
    at = AppTest.from_function(_script).run()
    assert not at.exception
    assert not at.error
    shown = text(at)
    assert "Targets" in shown and SUBTITLE in shown and FOOTNOTE in shown
    (dots, _), (verdicts, rows) = dots_and_verdicts(at)
    # same rows and same y as the dots, so each verdict is drawn on its own campaign's row
    assert verdicts["data"] == dots["data"] and verdicts["encoding"]["y"] == dots["encoding"]["y"]
    assert dict(zip(rows["campaign_name"], rows["verdict"], strict=True)) == VERDICTS
    # literal status colors: a color scale would be shared with the other layers and pick up their hues
    assert verdicts["encoding"]["color"]["scale"] is None
    assert dict(zip(rows["verdict"], rows["verdict_color"], strict=True)) == {
        "Adjust": STATUS_COLORS["warning"],
        "Continue": STATUS_COLORS["success"],
    }
    assert any("Synthetic" in t for t in shown)


def test_table_view_has_cost_and_canonical_names():
    at = AppTest.from_function(_script).run()
    at.toggle(key="targets_table_view").set_value(True).run()
    assert not at.exception
    columns = list(at.dataframe[0].value.columns)
    assert "Allocated Spend" in columns and "Target Achievement" in columns


def test_stale_keeps_recommendation(monkeypatch):
    monkeypatch.setattr(fabric_control, "status", lambda d: {"stale": True, "datasets": [STALE_DATASET]})
    at = AppTest.from_function(_script).run()
    assert not at.exception
    assert any(STALE_DATASET in w.value for w in at.warning)
    _, (_, rows) = dots_and_verdicts(at)
    stale = {name: f"{verdict} · stale" for name, verdict in VERDICTS.items()}
    assert dict(zip(rows["campaign_name"], rows["verdict"], strict=True)) == stale
    # only the page badge; each row says "stale" inside the chart instead
    assert sum("Using previous version" in m.value for m in at.markdown) == 1
    assert not any("Refreshed" in m.value for m in at.markdown)


def test_targets_badge_shows_refreshing(monkeypatch):
    monkeypatch.setattr(targets, "current_in_flight", lambda campaigns: frozenset({"mart_campaign.target_achievement"}))
    monkeypatch.setattr(targets, "watch", lambda campaigns, shown: None)
    at = AppTest.from_function(_script).run()
    assert not at.exception, at.exception
    shown = " ".join(m.value for m in at.markdown)
    assert "Refreshing…" in shown and "Refreshed" not in shown

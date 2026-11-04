import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import fabric_control
from app.pages.finance import budget_spend
from app.pages.finance.budget_spend import by_campaign, edited_window, stack, summarize
from app.services.spend_edit import EVENT_KEY
from app.shell import fmt_money
from fabric_control.glossary import load_terms

FRESH = datetime(2026, 10, 13, 7, 0, tzinfo=UTC)
D1, D2, D3 = date(2019, 1, 15), date(2019, 1, 16), date(2019, 1, 17)


def budget_rows():
    rows = [
        ("CMP19_01", D1, "Spring", Decimal("1000"), Decimal("10.00"), 2, Decimal("40.00")),
        ("CMP19_01", D2, "Spring", Decimal("1000"), Decimal("30.00"), 2, Decimal("100.00")),
        ("CMP19_02", D3, "Summer", Decimal("500"), Decimal("0.00"), 0, Decimal("0.00")),
    ]
    cols = ["campaign_id", "date", "campaign_name", "campaign_budget", "allocated", "attributed_orders"]
    df = pd.DataFrame(rows, columns=[*cols, "attributed_gross_value"])
    return df.assign(channel="Paid Search", provenance="synthetic", _refreshed_at=FRESH)


def recon_rows():
    rows = [
        (D1, Decimal("100.00"), Decimal("10.00"), Decimal("90.00")),
        (D2, Decimal("30.00"), Decimal("30.00"), Decimal("0.00")),
    ]
    df = pd.DataFrame(rows, columns=["date", "online_spend", "allocated", "unallocated"])
    return df.assign(offline_spend=Decimal("4500"), provenance="synthetic", _refreshed_at=FRESH)


def test_summary_counts_budget_once_per_campaign_and_uses_ratio_of_sums():
    values = summarize(budget_rows(), recon_rows())
    assert values["campaign_budget"] == Decimal("1500")
    assert values["allocated_spend"] == Decimal("40.00")
    assert values["unallocated_spend"] == Decimal("90.00")
    assert values["attributed_value_per_spend_ratio"] == Decimal("3.5")
    assert values["cost_per_attributed_order"] == Decimal("10")


def test_campaign_without_spend_or_orders_has_no_ratio():
    summer = by_campaign(budget_rows()).set_index("campaign_id").loc["CMP19_02"]
    assert summer["value_per_spend"] is None and summer["cost_per_order"] is None


def test_stack_has_one_bar_segment_per_day_and_kind():
    data = stack(recon_rows())
    assert sorted(data["segment"].unique()) == ["Allocated", "Unallocated"] and len(data) == 4


def test_page_terms_exist_in_glossary():
    assert set(summarize(budget_rows(), recon_rows())) <= set(load_terms())


class Source:
    def read(self, dataset_id):
        return {"mart_finance.budget_daily": budget_rows(), "mart_shared.spend_reconciliation": recon_rows()}[
            dataset_id
        ]


def _script():
    from app.pages.finance.budget_spend import render
    from app.shell import session

    session.set_role("UG04")
    render()


@pytest.mark.parametrize("table_view", [False, True])
def test_page_renders_metrics_chart_and_table(monkeypatch, table_view):
    terms = load_terms()
    monkeypatch.setattr(fabric_control, "term", lambda term_id: terms.get(term_id))
    monkeypatch.setattr(fabric_control, "effective_matrix", lambda: [])
    monkeypatch.setattr(budget_spend, "current_source", lambda: Source())
    at = AppTest.from_function(_script).run()
    if table_view:
        at.toggle(key="budget_spend_table_view").set_value(True).run()
    assert not at.exception, at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Attributed Value / Spend Ratio" in text and "3.50×" in text
    assert len(at.dataframe) == (2 if table_view else 1)


def _role_script(role):
    from app.pages.finance.budget_spend import render
    from app.shell import session

    session.set_role(role)
    render()


def _page(monkeypatch, role="UG04", in_flight=frozenset(), event=None, chosen=None, source=Source):
    monkeypatch.setenv("APP_TZ", "UTC")
    terms = load_terms()
    monkeypatch.setattr(fabric_control, "term", lambda term_id: terms.get(term_id))
    monkeypatch.setattr(fabric_control, "effective_matrix", lambda: [])
    monkeypatch.setattr(budget_spend, "current_source", lambda: source())
    flight = in_flight if callable(in_flight) else lambda campaigns: frozenset(in_flight)
    monkeypatch.setattr(budget_spend, "current_in_flight", flight)
    monkeypatch.setattr(budget_spend, "watch", lambda campaigns, shown: None)
    monkeypatch.setattr(budget_spend, "progress_strip", lambda: None)
    at = AppTest.from_function(_role_script, kwargs={"role": role})
    if event:
        at.session_state[EVENT_KEY] = event
    at.run()
    if chosen:
        at.selectbox(key="_filter_budget_spend_campaign").set_value(chosen).run()
    assert not at.exception, at.exception
    return at


def test_ug04_sees_spend_form_ug03_does_not(monkeypatch):
    assert "**Edit daily spend**" in [m.value for m in _page(monkeypatch, "UG04").markdown]
    at = _page(monkeypatch, "UG03")
    assert "**Edit daily spend**" not in [m.value for m in at.markdown]
    assert "Save change" not in [b.label for b in at.button]


def test_spend_form_sits_below_the_analysis(monkeypatch):  # mockups/key-budget-spend.html Section 1
    values = [m.value for m in _page(monkeypatch).markdown]
    assert values.index("**By campaign**") < values.index("**Edit daily spend**")


def _card(at, label):
    values = [m.value for m in at.markdown]
    return values[values.index(label) + 1]  # metric() writes the label, then the value


def _kpi_rows(at):
    """(columns in the row, term ids of its cards) for each st.columns row holding metric cards."""
    rows = []
    for block in at.main.children.values():
        columns = [c for c in getattr(block, "children", {}).values() if c.type == "column"]
        keys = [str(c.children[0].key) for c in columns if c.children]
        cards = [k.removeprefix("metric-") for k in keys if k.startswith("metric-")]
        if cards:
            rows.append((len(columns), cards))
    return rows


def test_kpi_cards_wrap_to_a_spend_row_and_an_efficiency_row(monkeypatch):
    assert _kpi_rows(_page(monkeypatch)) == [
        (3, ["campaign_budget", "allocated_spend", "unallocated_spend"]),
        (3, ["attributed_value_per_spend_ratio", "cost_per_attributed_order"]),
    ]


D4 = date(2019, 4, 10)


class TwoQuarters(Source):
    """Adds a Q2 day for Summer; every other row is in Q1."""

    def read(self, dataset_id):
        df = super().read(dataset_id)
        april = df.iloc[[-1]].assign(date=D4, allocated=Decimal("5.00"))
        if dataset_id == budget_spend.RECON:
            april = april.assign(online_spend=Decimal("50.00"), unallocated=Decimal("45.00"))
        return pd.concat([df, april], ignore_index=True)


def test_period_filter_applies_to_cards_chart_and_table(monkeypatch):
    at = _page(monkeypatch, source=TwoQuarters)
    period = at.selectbox(key="_filter_budget_spend_period")
    assert period.value == "FY2019" and (_card(at, "Allocated Spend"), _card(at, "Unallocated Spend")) == ("45", "135")
    period.set_value("2019-Q2").run()
    assert [_card(at, t) for t in ("Campaign Budget", "Allocated Spend", "Unallocated Spend")] == ["500", "5", "45"]
    at.toggle(key="budget_spend_table_view").set_value(True).run()
    chart_rows, campaign_rows = (d.value for d in at.dataframe)
    assert list(chart_rows["date"]) == [D4] and list(campaign_rows["campaign_id"]) == ["CMP19_02"]
    at.selectbox(key="_filter_budget_spend_campaign").set_value("CMP19_01").run()
    assert ":material/info: No campaign spend for CMP19_01 in this period." in [m.value for m in at.markdown]


def test_one_campaign_says_unallocated_and_chart_are_all_campaigns(monkeypatch):
    note = "Unallocated Spend and the daily chart cover all campaigns"
    assert not any(note in c.value for c in _page(monkeypatch).caption)
    at = _page(monkeypatch, chosen="CMP19_01")
    assert any(note in c.value and "Allocated Spend covers Spring only." in c.value for c in at.caption)
    assert (_card(at, "Allocated Spend"), _card(at, "Unallocated Spend")) == ("40", "90")


class ManyDays(Source):
    def read(self, dataset_id):
        df = super().read(dataset_id)
        if dataset_id == budget_spend.RECON:
            march = [date(2019, 3, 1) + timedelta(days=i) for i in range(budget_spend.LABELLED_DAYS)]
            df = pd.concat([df, *(df.iloc[[0]].assign(date=d) for d in march)], ignore_index=True)
        return df


@pytest.mark.parametrize("source,width", [(Source, 2), (ManyDays, 0)])
def test_segment_gap_only_on_wide_bars(monkeypatch, source, width):
    spec = json.loads(_page(monkeypatch, source=source).get("vega_lite_chart")[0].proto.spec)
    assert (spec["layer"][0] if "layer" in spec else spec)["mark"]["strokeWidth"] == width


def test_in_flight_cards_show_refreshing_and_keep_value(monkeypatch):
    at = _page(monkeypatch, in_flight={"mart_finance.budget_daily", "mart_shared.campaign_spend_allocated"})
    values = [m.value for m in at.markdown]
    assert "40" in values  # Allocated Spend keeps its previous value
    assert " ".join(values).count("Refreshing…") == 4  # every card but Unallocated (spend_reconciliation)


def test_edited_window_is_seven_days_centred():
    recon = pd.DataFrame({"date": [date(2019, 11, d) for d in range(1, 21)]})
    assert [d.day for d in edited_window(recon, date(2019, 11, 12))["date"]] == list(range(9, 16))
    assert [d.day for d in edited_window(recon, date(2019, 11, 2))["date"]] == list(range(1, 8))
    assert [d.day for d in edited_window(recon, date(2019, 11, 20))["date"]] == list(range(14, 21))
    assert len(edited_window(recon.head(3), date(2019, 11, 2))) == 3


EVENT = {
    "event": {
        "event_id": "e1",
        "emitted_at": "2026-10-13T06:59:00+00:00",  # just before FRESH: the recon row is newer, so it landed
        "keys": {"campaign_id": "CMP19_01", "date": "2019-01-16"},
    },
    "dag_run_id": "r1",
    "campaign_name": "Spring",
    "old": {"allocated": Decimal("10.00"), "unallocated": Decimal("20.00")},
    "new": Decimal("30.00"),
}


def _recon_table(at):
    return next(d.value for d in at.dataframe if "note" in d.value.columns)


def test_reconciliation_note_while_updating(monkeypatch):
    at = _page(monkeypatch, in_flight={"mart_shared.spend_reconciliation"}, event=EVENT)
    assert "**Daily reconciliation**" in [m.value for m in at.markdown]
    row = _recon_table(at).set_index("date").loc[D2]
    assert row["note"] == "↻ Saved 30.00, updating" and row["allocated"] == "30.00"


def test_reconciliation_note_after_refresh_shows_old_and_new(monkeypatch):
    at = _page(monkeypatch, event=EVENT)
    df = _recon_table(at).set_index("date")
    row = df.loc[D2]
    assert row["note"] == "Refreshed 07:00 · difference 0 · see Change History"
    assert row["allocated"] == "10.00 → 30.00" and row["unallocated"] == "20.00 → 0.00"
    assert df.loc[D1, "note"] == "" and df.loc[D1, "allocated"] == "10.00"


def test_reconciliation_busy_ignores_campaign_filter(monkeypatch):
    def flight(campaigns):
        return frozenset({budget_spend.RECON}) if campaigns is None else frozenset()

    at = _page(monkeypatch, in_flight=flight, event=EVENT, chosen="CMP19_02")
    assert _recon_table(at).set_index("date").loc[D2, "note"] == "↻ Saved 30.00, updating"


def test_reconciliation_says_stopped_when_row_not_refreshed_after_event(monkeypatch):
    late = {**EVENT, "event": {**EVENT["event"], "emitted_at": "2026-10-13T08:00:00+00:00"}}
    row = _recon_table(_page(monkeypatch, event=late)).set_index("date").loc[D2]
    assert row["note"] == "Refresh stopped · see Pipeline Status" and row["allocated"] == "30.00"


def test_cents_shows_dash_for_missing():  # the reconciliation table formats with fmt_money(places=2)
    assert [fmt_money(v, places=2) for v in (None, pd.NA, float("nan"), Decimal("1234.5"))] == [
        "—",
        "—",
        "—",
        "1,234.50",
    ]

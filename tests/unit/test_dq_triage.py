"""Story 3.4 tests: scoreboard, status join, triage writes, DQ page."""

import pandas as pd
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from app.services import exception_triage as triage  # noqa: E402


def dq_frame():
    return pd.DataFrame(
        [
            ("unified/orders", "order_key_unique", "critical", True, 100.0, "Green", "2026-10-08 10:00"),
            ("unified/orders", "late_rule", "warning", False, 80.0, "Amber", "2026-10-08 10:00"),
            ("unified/orders", "late_rule", "warning", True, 100.0, "Green", "2026-10-08 09:00"),
        ],
        columns=["dataset_id", "rule_id", "severity", "passed", "score_pct", "status", "checked_at"],
    )


def test_scoreboard_takes_latest_run_and_failing_rules():
    board = triage.scoreboard(dq_frame())
    assert board[["dataset_id", "score_pct", "status"]].values.tolist() == [["unified/orders", 80.0, "Amber"]]
    assert board["failing"].tolist() == ["late_rule (warning)"]


def test_scoreboard_empty_without_results():
    assert triage.scoreboard(pd.DataFrame(columns=["dataset_id"])).empty


def exc_frame():
    return pd.DataFrame(
        [("e1", "shared_transaction_id"), ("e2", "coupon_plan_mismatch")],
        columns=["exception_id", "class"],
    )


def test_scoreboard_with_results_but_no_failing_rule():
    dq = dq_frame()
    dq["passed"] = True
    board = triage.scoreboard(dq)
    assert set(board["failing"]) == {""}
    assert len(board) == dq["dataset_id"].nunique()


def test_with_status_defaults_new_and_keeps_resolved():
    statuses = pd.DataFrame([("e1", "seen"), ("gone", "accepted")], columns=["exception_id", "status"])
    out = triage.with_status(exc_frame(), statuses)
    assert dict(zip(out["exception_id"], out["status"], strict=True)) == {
        "e1": "seen",
        "e2": "new",
        "gone": triage.RESOLVED,
    }


class FakeCursor:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def executemany(self, sql, rows):
        self.statements.append((sql, list(rows)))


class FakeConn:
    def __init__(self):
        self.cursor_obj = FakeCursor()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_obj


def test_mark_status_upserts_and_refuses_resolved():
    conn = FakeConn()
    assert triage.mark_status(conn, ["e1", "e2"], "seen", "UG05", {"e1", "e2"}) == 2
    sql, rows = conn.cursor_obj.statements[0]
    assert "ON CONFLICT (exception_id) DO UPDATE" in sql
    assert rows == [("e1", "seen", "UG05"), ("e2", "seen", "UG05")]
    with pytest.raises(ValueError, match="resolved at source"):
        triage.mark_status(conn, ["gone"], "seen", "UG05", {"e1"})
    with pytest.raises(ValueError, match="seen or accepted"):
        triage.mark_status(conn, ["e1"], "new", "UG05", {"e1"})


def test_read_view_rejects_non_view_tables():
    with pytest.raises(ValueError, match="only generated"):
        triage.read_view(None, "mart_shared.exceptions")


def _page_script():
    from app.pages.governance import data_quality

    data_quality.render()


def _frames(*args):
    return {
        "ops_v.dq_results": dq_frame(),
        "mart_shared_v.exceptions": exc_frame(),
        "app_v.exception_status": pd.DataFrame(columns=["exception_id", "status"]),
    }[args[1]]


def test_dq_page_renders_scoreboard_and_triage(monkeypatch):
    monkeypatch.setattr(triage, "connect_reader", lambda: FakeConn())
    monkeypatch.setattr(triage, "connect_writer", lambda: FakeConn())
    monkeypatch.setattr(triage, "read_view", lambda conn, view: _frames(conn, view))
    at = AppTest.from_function(_page_script).run()
    assert not at.exception
    assert "unified/orders" in " ".join(m.value for m in at.markdown)
    assert "Amber 80%" in " ".join(m.value for m in at.markdown)
    assert set(at.selectbox(key="_filter_data_quality_class").options) == {
        "shared_transaction_id",
        "coupon_plan_mismatch",
    }
    at.selectbox(key="_filter_data_quality_class").set_value("shared_transaction_id").run()
    at.multiselect(key="data_quality-triage").set_value(["e1"]).run()
    at.button(key="data_quality-seen").click().run()
    assert not at.exception
    assert any("Marked 1 as seen" in t.value for t in at.toast)


def test_triage_respects_class_filter(monkeypatch):
    monkeypatch.setattr(triage, "connect_reader", lambda: FakeConn())
    monkeypatch.setattr(triage, "connect_writer", lambda: FakeConn())
    monkeypatch.setattr(triage, "read_view", lambda conn, view: _frames(conn, view))
    at = AppTest.from_function(_page_script).run()
    at.selectbox(key="_filter_data_quality_class").set_value("shared_transaction_id").run()
    assert not at.exception
    assert at.multiselect(key="data_quality-triage").options == ["e1"]
    at.multiselect(key="data_quality-triage").set_value(["e1"]).run()
    at.button(key="data_quality-seen").click().run()
    assert not at.exception
    assert any("Marked 1 as seen" in t.value for t in at.toast)


def test_class_filter_shows_no_statuses_of_other_classes(monkeypatch):
    statuses = pd.DataFrame(
        [("e1", "seen"), ("e2", "accepted"), ("gone", "accepted")], columns=["exception_id", "status"]
    )
    views = {
        "ops_v.dq_results": dq_frame(),
        "mart_shared_v.exceptions": exc_frame(),
        "app_v.exception_status": statuses,
    }
    monkeypatch.setattr(triage, "connect_reader", lambda: FakeConn())
    monkeypatch.setattr(triage, "read_view", lambda conn, view: views[view])
    at = AppTest.from_function(_page_script).run()
    shown = at.dataframe[0].value
    assert dict(zip(shown["exception_id"], shown["status"], strict=True)) == {"e2": "accepted", "gone": triage.RESOLVED}
    at.selectbox(key="_filter_data_quality_class").set_value("shared_transaction_id").run()
    assert not at.exception
    shown = at.dataframe[0].value
    assert dict(zip(shown["exception_id"], shown["status"], strict=True)) == {"e1": "seen", "gone": triage.RESOLVED}


def test_coupon_status_counts_reads_mismatch_detail_only():
    frame = pd.DataFrame(
        [
            ("e1", "shared_transaction_id", "customers=2"),
            ("e2", "coupon_plan_mismatch", "month=1; category=Fun; coupon_status=Used"),
            ("e3", "coupon_plan_mismatch", "month=2; category=Fun; coupon_status=Not Used"),
            ("e4", "coupon_plan_mismatch", "month=3; category=Fun"),
        ],
        columns=["exception_id", "class", "detail"],
    )
    assert triage.coupon_status_counts(frame) == {"Used": 1, "Not Used": 1}
    assert triage.coupon_status_counts(exc_frame()) == {}


def test_dq_page_counts_used_mismatch_lines(monkeypatch):
    exceptions = pd.DataFrame(
        [
            ("e2", "coupon_plan_mismatch", "month=1; category=Fun; coupon_status=Used"),
            ("e3", "coupon_plan_mismatch", "month=2; category=Fun; coupon_status=Not Used"),
        ],
        columns=["exception_id", "class", "detail"],
    )
    views = {
        "ops_v.dq_results": dq_frame(),
        "mart_shared_v.exceptions": exceptions,
        "app_v.exception_status": pd.DataFrame(columns=["exception_id", "status"]),
    }
    monkeypatch.setattr(triage, "connect_reader", lambda: FakeConn())
    monkeypatch.setattr(triage, "read_view", lambda conn, view: views[view])
    at = AppTest.from_function(_page_script).run()
    assert not at.exception
    assert any("1 of 2 lines are Used" in c.value for c in at.caption)

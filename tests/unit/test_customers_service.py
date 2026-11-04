"""Stories 5.1-5.3 service tests: summary, match, win-back, save/read audiences."""

import pandas as pd

from app.services import customers as svc


def frame():
    return pd.DataFrame(
        [
            {
                "customer_id": 1,
                "recency_days": 5,
                "recency_score": 5,
                "frequency_orders": 6,
                "frequency_score": 5,
                "monetary_value": 600.0,
                "monetary_score": 5,
                "segment": "Champions",
                "categories": "Apparel",
            },
            {
                "customer_id": 2,
                "recency_days": 40,
                "recency_score": 3,
                "frequency_orders": 2,
                "frequency_score": 2,
                "monetary_value": 100.0,
                "monetary_score": 2,
                "segment": "Needs Attention",
                "categories": "Apparel,Nest",
            },
            {
                "customer_id": 3,
                "recency_days": 300,
                "recency_score": 1,
                "frequency_orders": 1,
                "frequency_score": 1,
                "monetary_value": 10.0,
                "monetary_score": 1,
                "segment": "Lost",
                "categories": "Nest",
            },
            {
                "customer_id": 4,
                "recency_days": 200,
                "recency_score": 1,
                "frequency_orders": 4,
                "frequency_score": 5,
                "monetary_value": 500.0,
                "monetary_score": 5,
                "segment": "Can't Lose",
                "categories": "Fun",
            },
            {
                "customer_id": 5,
                "recency_days": 10,
                "recency_score": 4,
                "frequency_orders": 1,
                "frequency_score": 1,
                "monetary_value": 20.0,
                "monetary_score": 1,
                "segment": "Recent First Buyers",
                "categories": "",
            },
        ]
    )


def test_segment_summary_orders_and_shares():
    summary = svc.segment_summary(frame())
    assert list(summary["segment"]) == ["Champions", "Can't Lose", "Recent First Buyers", "Needs Attention", "Lost"]
    assert list(summary["customers"]) == [1, 1, 1, 1, 1]
    assert abs(summary["share"].sum() - 1.0) < 1e-9


def test_buyer_count_counts_distinct_customers():
    assert svc.buyer_count(frame()) == 5


def test_category_options_sorted_unique():
    assert svc.category_options(frame()) == ["Apparel", "Fun", "Nest"]


def test_match_filters_segment_category_history():
    df = frame()
    assert len(svc.match(df)) == 5
    assert svc.match(df, segment="Lost")["customer_id"].tolist() == [3]
    assert svc.match(df, category="Nest")["customer_id"].tolist() == [2, 3]
    assert svc.match(df, min_orders=2)["customer_id"].tolist() == [1, 2, 4]
    assert svc.match(df, segment="Champions", category="Apparel", min_orders=6)["customer_id"].tolist() == [1]
    assert svc.match(df, segment="Lost", category="Apparel").empty


def test_win_back_selects_high_value_lapsed_only():
    df = frame()
    assert svc.win_back(df)["customer_id"].tolist() == [4]
    assert svc.win_back(df, category="Fun")["customer_id"].tolist() == [4]
    assert svc.win_back(df, category="Apparel").empty


def test_criteria_and_audience_id_shape():
    assert svc.criteria(segment="Lost", category="Nest", min_orders=1) == {
        "segment": "Lost",
        "category": "Nest",
        "min_orders": 1,
    }
    assert len(svc.new_audience_id()) == 32


class FakeCursor:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.statements.append((sql, params))


class FakeConn:
    def __init__(self, rows=None, columns=None):
        self.cursor_obj = FakeCursor()
        self._rows = rows or []
        self._columns = columns or []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cursor_obj

    def execute(self, sql):
        columns = self._columns

        class Cursor:
            description = [type("C", (), {"name": c}) for c in columns]

            def fetchall(inner):
                return self._rows

        return Cursor()


def test_save_audience_inserts_with_json_criteria():
    conn = FakeConn()
    audience_id = svc.save_audience(conn, "Win-back Fun", {"segment": "All"}, 4, "UG02")
    assert len(audience_id) == 32
    sql, params = conn.cursor_obj.statements[0]
    assert "INSERT INTO app.segments" in sql
    assert params[1] == "Win-back Fun" and params[3] == 4 and params[4] == "UG02"


def test_read_audiences_returns_frame():
    conn = FakeConn(
        rows=[("a1", "Win-back", "{}", 4, "UG02", "2026-10-16")],
        columns=["audience_id", "name", "criteria", "customer_count", "created_by", "created_at"],
    )
    assert svc.read_audiences(conn)["name"].tolist() == ["Win-back"]


def test_detail_drops_profile_columns_but_keeps_denied_flags():
    df = frame().assign(gender="F", location="Hanoi", tenure_months=3, provenance="original", customer_id__denied=False)
    shown = svc.detail(df)
    assert not set(svc.DETAIL_HIDDEN) & set(shown.columns)
    assert {"customer_id", "segment", "customer_id__denied"} <= set(shown.columns)


def test_name_taken_queries_case_insensitively():
    seen = {}

    class Conn:
        def execute(self, sql, params):
            seen["sql"], seen["params"] = sql, params

            class Cursor:
                def fetchone(self):
                    return (1,)

            return Cursor()

    assert svc.name_taken(Conn(), "Win-back Fun")
    assert "lower(btrim(name))" in seen["sql"] and seen["params"] == ("Win-back Fun",)

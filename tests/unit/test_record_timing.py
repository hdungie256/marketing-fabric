import psycopg

import fabric_control


class FakeConn:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))


def test_record_timing_online_inserts_as_ops_writer(monkeypatch):
    calls, kwargs = [], {}
    monkeypatch.setenv("FABRIC_CONTROL_MODE", "online")
    monkeypatch.setenv("OPS_WRITER_DB_PASSWORD", "pw")

    def connect(**kw):
        kwargs.update(kw)
        return FakeConn(calls)

    monkeypatch.setattr(psycopg, "connect", connect)
    fabric_control.record_timing("campaign_overview", 812.345)
    assert kwargs["user"] == "ops_writer" and kwargs["password"] == "pw" and kwargs["dbname"] == "serving"
    assert calls == [("INSERT INTO ops.page_timings (page, ms) VALUES (%s, %s)", ("campaign_overview", 812.3))]


def test_record_timing_offline_does_not_connect(monkeypatch):
    monkeypatch.setattr(psycopg, "connect", lambda **kw: (_ for _ in ()).throw(AssertionError("connected")))
    fabric_control.record_timing("campaign_overview", 1.0)

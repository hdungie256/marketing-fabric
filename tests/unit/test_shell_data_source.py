from types import SimpleNamespace

import pandas as pd
import psycopg
import pytest

from app.shell import data_source
from app.shell.data_source import FixtureSource, PgSource, current_source, data_mode, view_for
from app.shell.errors import NotPermittedError
from app.shell.roles import ROLES

REGISTRY = {
    "mart_campaign/overview": {"om_fqn": "serving.serving.mart_campaign.overview"},
    "raw/sales/sales_lines": {"om_fqn": "lake_raw.default.lake.sales_lines"},
}


def test_view_for_maps_serving_table_to_policy_view():
    assert view_for("mart_campaign/overview", REGISTRY) == "mart_campaign_v.overview"


def test_view_for_rejects_lake_dataset():
    with pytest.raises(ValueError, match="not a Postgres serving dataset"):
        view_for("raw/sales/sales_lines", REGISTRY)


def test_view_for_rejects_unknown_dataset():
    with pytest.raises(ValueError, match="not in contracts registry"):
        view_for("mart_campaign/nope", REGISTRY)


def test_fixture_source_reads_parquet_by_dataset_id(tmp_path):
    (tmp_path / "mart_campaign").mkdir()
    pd.DataFrame({"a": [1]}).to_parquet(tmp_path / "mart_campaign" / "overview.parquet")
    assert FixtureSource(tmp_path).read("mart_campaign/overview").to_dict("list") == {"a": [1]}


def test_fixture_source_names_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="mart_campaign/overview"):
        FixtureSource(tmp_path).read("mart_campaign/overview")


class FakeConnection:
    def __init__(self, error=None):
        self.error = error
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query):
        self.queries.append(query)
        if self.error:
            raise self.error
        return SimpleNamespace(description=[SimpleNamespace(name="a")], fetchall=lambda: [(1,), (2,)])


def test_pg_source_selects_from_view_with_role_login(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(PgSource, "_connect", lambda self: conn)
    df = PgSource(ROLES["UG01"], REGISTRY).read("mart_campaign/overview")
    assert df.to_dict("list") == {"a": [1, 2]}
    assert "mart_campaign_v" in conn.queries[0].as_string(None)


def test_pg_source_turns_permission_error_into_not_permitted(monkeypatch):
    conn = FakeConnection(psycopg.errors.InsufficientPrivilege("permission denied for view overview"))
    monkeypatch.setattr(PgSource, "_connect", lambda self: conn)
    with pytest.raises(NotPermittedError):
        PgSource(ROLES["UG01"], REGISTRY).read("mart_campaign/overview")


def test_data_mode_defaults_to_fixture(monkeypatch):
    monkeypatch.delenv("APP_DATA_MODE", raising=False)
    assert data_mode() == "fixture"


def test_data_mode_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("APP_DATA_MODE", "duckdb")
    with pytest.raises(ValueError, match="'fixture' or 'pg'"):
        data_mode()


def test_current_source_follows_mode_and_role(monkeypatch):
    monkeypatch.setattr(data_source.session, "role", lambda: "UG04")
    monkeypatch.setenv("APP_DATA_MODE", "fixture")
    assert isinstance(current_source(), FixtureSource)
    monkeypatch.setenv("APP_DATA_MODE", "pg")
    source = current_source()
    assert isinstance(source, PgSource) and source.role.code == "UG04"

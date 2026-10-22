import pytest

from pipelines.io.scope import scope_predicate
from pipelines.io.storage import table_path


def test_table_path(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "lake")
    assert table_path("raw/crm/orders") == "s3a://lake/raw/crm/orders"
    assert table_path("unified/orders") == "s3a://lake/unified/orders"


@pytest.mark.parametrize("scope", [None, {}, {"mode": "full"}])
def test_full_scope_has_no_predicate(scope):
    assert scope_predicate(scope) is None


def test_scope_predicate():
    scope = {"mode": "scope", "keys": {"channel": ["web", "o'neil"], "period_month": [202609]}}
    assert scope_predicate(scope) == "`channel` IN ('web', 'o''neil') AND `period_month` IN (202609)"


@pytest.mark.parametrize("scope", [{"mode": "scope"}, {"mode": "scope", "keys": {"a": []}}, {"mode": "x"}])
def test_invalid_scope(scope):
    with pytest.raises(ValueError):
        scope_predicate(scope)


def test_append_raw_rejects_non_raw_dataset():
    from pipelines import io

    with pytest.raises(ValueError, match="not a raw dataset"):
        io.append_raw("unified/orders", None, "r", "src", "snapshot", 1, "1.0.0")


def test_restrict_keeps_grain_keys_only():
    from pipelines.io.scope import restrict

    scope = {"mode": "scope", "keys": {"campaign_id": ["C1"], "date": ["2019-01-15"]}}
    assert restrict(scope, ["date"]) == {"mode": "scope", "keys": {"date": ["2019-01-15"]}}
    assert restrict(scope, ["channel"]) == {"mode": "full"}
    assert restrict({"mode": "full"}, ["date"]) == {"mode": "full"}


def test_upsert_rejects_rows_outside_scope():
    from pipelines.io.pg import outside

    rows = [("C1", "2019-01-15", 1), ("C2", "2019-01-15", 2)]
    assert outside(rows, ["campaign_id", "date", "v"], {"campaign_id": ["C1"]}) == [rows[1]]


def test_delta_version_is_none_before_first_write(monkeypatch):
    pytest.importorskip("delta")
    from delta.tables import DeltaTable

    import pipelines.io as io_module

    monkeypatch.setattr(io_module, "get_spark", lambda: object())
    monkeypatch.setattr(DeltaTable, "isDeltaTable", staticmethod(lambda spark, path: False))
    assert io_module.delta_version("unified/campaign_spend") is None

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

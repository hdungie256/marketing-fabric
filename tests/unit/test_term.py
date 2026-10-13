import pytest

import fabric_control
from fabric_control import metadata


@pytest.fixture(autouse=True)
def fresh_cache():
    metadata._local_terms.cache_clear()
    yield
    metadata._local_terms.cache_clear()


@pytest.mark.parametrize("mode", ["offline", "online"])
def test_term_reads_repo_glossary_in_both_modes(monkeypatch, mode):
    monkeypatch.setenv("FABRIC_CONTROL_MODE", mode)
    t = fabric_control.term("gross_value")
    assert t["display_name"] == "Gross Value"
    assert t["term_id"] == "gross_value"
    assert t["synthetic"] is (t["provenance"] == "synthetic")


def test_unknown_term_is_none():
    assert fabric_control.term("nope") is None

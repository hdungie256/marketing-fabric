import glob

import pytest
import yaml

from benchmark.quality.sodacl import check, checks_yaml


@pytest.mark.parametrize(
    "rule,expected",
    [
        ({"expectation": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "a"}}, {"missing_count(a) = 0": {}}),
        ({"expectation": "ExpectColumnValuesToBeUnique", "kwargs": {"column": "a"}}, {"duplicate_count(a) = 0": {}}),
        (
            {"expectation": "ExpectCompoundColumnsToBeUnique", "kwargs": {"column_list": ["a", "b"]}},
            {"duplicate_count(a, b) = 0": {}},
        ),
        (
            {
                "expectation": "ExpectColumnValuesToBeBetween",
                "kwargs": {"column": "m", "min_value": 1, "max_value": 12},
            },
            {"invalid_count(m) = 0": {"valid min": 1, "valid max": 12}},
        ),
        (
            {
                "expectation": "ExpectColumnPairValuesAToBeGreaterThanB",
                "kwargs": {"column_A": "e", "column_B": "s", "or_equal": True},
            },
            {"failed rows": {"fail condition": "e < s"}},
        ),
    ],
)
def test_each_expectation_has_a_named_sodacl_twin(rule, expected):
    [(key, config)] = expected.items()
    assert check({**rule, "rule_id": "r1"}) == {key: {"name": "r1", **config}}


def test_strict_pair_rule_fails_on_equal_values():
    rule = {
        "rule_id": "r",
        "expectation": "ExpectColumnPairValuesAToBeGreaterThanB",
        "kwargs": {"column_A": "a", "column_B": "b"},
    }
    assert check(rule) == {"failed rows": {"name": "r", "fail condition": "a <= b"}}


def test_unknown_expectation_is_rejected():
    with pytest.raises(ValueError, match="no SodaCL translation"):
        check({"rule_id": "r", "expectation": "ExpectSomethingElse"})


def test_every_repository_rule_translates():
    files = [f for f in glob.glob("pipelines/jobs/**/data_quality/*.yml", recursive=True) if "_templates" not in f]
    rules = [r for f in files for r in (yaml.safe_load(open(f)) or {}).get("rules") or []]
    assert rules
    parsed = yaml.safe_load(checks_yaml("t", rules))
    assert len(parsed["checks for t"]) == len(rules)

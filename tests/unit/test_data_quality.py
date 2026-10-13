import pytest
import yaml

import fabric_control as fc
from fabric_control import data_quality
from fabric_control.contracts import ContractError, columns, load_schema
from fabric_control.data_quality import RuleFileError, load_rules, rules_path

CHECKED = ("unified/", "mart_")
COLUMN_KWARGS = ("column", "column_A", "column_B")


def checked_datasets() -> list[str]:
    return [d for d in fc.load_registry() if d.startswith(CHECKED)]


def rule_columns(rule: dict) -> set[str]:
    kwargs = rule.get("kwargs") or {}
    return {kwargs[k] for k in COLUMN_KWARGS if k in kwargs} | set(kwargs.get("column_list") or [])


@pytest.mark.parametrize("dataset_id", checked_datasets())
def test_every_checked_dataset_has_valid_rules(dataset_id):
    rules = load_rules(rules_path(dataset_id))
    assert rules, f"{dataset_id} has no quality rules"
    try:
        contract = {name for name, _ in columns(load_schema(dataset_id))}
    except ContractError:
        return
    unknown = set().union(*(rule_columns(r) for r in rules)) - contract
    assert not unknown, f"{dataset_id} rules reference columns outside the contract: {sorted(unknown)}"


def test_unified_orders_has_critical_order_key_uniqueness():
    rules = load_rules(rules_path("unified/orders"))
    assert any(
        r["expectation"] == "ExpectColumnValuesToBeUnique"
        and r["kwargs"] == {"column": "order_key"}
        and r["severity"] == "critical"
        for r in rules
    )


@pytest.mark.parametrize(
    "rules,message",
    [
        ([{"rule_id": "a", "expectation": "ExpectX", "severity": "critical"}] * 2, "duplicate"),
        ([{"rule_id": "a", "expectation": "ExpectX", "severity": "high"}], "severity"),
        ([{"rule_id": "a", "expectation": "not_null", "severity": "warning"}], "expectation"),
    ],
)
def test_invalid_rule_files_are_rejected(tmp_path, rules, message):
    path = tmp_path / "x.yml"
    path.write_text(yaml.safe_dump({"rules": rules}))
    with pytest.raises(RuleFileError, match=message):
        load_rules(path)


def test_missing_rule_file_is_rejected(tmp_path):
    with pytest.raises(RuleFileError, match="missing"):
        load_rules(tmp_path / "absent.yml")


def test_run_id_is_visible_only_inside_run():
    with fc.run("unified/orders", {"mode": "full"}) as run:
        assert data_quality.current_run_id() == run.run_id
    with pytest.raises(RuntimeError):
        data_quality.current_run_id()


RULES = [
    {"rule_id": "id_unique", "expectation": "ExpectColumnValuesToBeUnique", "kwargs": {"column": "id"}},
    {"rule_id": "value_not_null", "expectation": "ExpectColumnValuesToNotBeNull", "kwargs": {"column": "value"}},
]


@pytest.fixture
def gx_rules(monkeypatch, tmp_path):
    pytest.importorskip("great_expectations")
    path = tmp_path / "orders.yml"
    rules = [{**RULES[0], "severity": "critical"}, {**RULES[1], "severity": "warning"}]
    path.write_text(yaml.safe_dump({"rules": rules}))
    monkeypatch.setattr(data_quality, "rules_path", lambda dataset_id: path)


def frame(spark, rows):
    return spark.createDataFrame(rows, "id INT, value STRING, day INT")


def test_check_passes_clean_frame(spark, gx_rules):
    result = fc.check("unified/orders", frame(spark, [(1, "a", 1), (2, "b", 2)]), {"mode": "full"})
    assert [(r.rule_id, r.passed) for r in result.rules] == [("id_unique", True), ("value_not_null", True)]
    assert fc.score(result) == (100.0, "Green")


def test_check_duplicate_key_is_red_with_detail(spark, gx_rules):
    result = fc.check("unified/orders", frame(spark, [(1, "a", 1), (1, "b", 2)]), {"mode": "full"})
    unique = result.rules[0]
    assert (unique.passed, unique.detail) == (False, "2 unexpected")
    assert fc.score(result) == (50.0, "Red")
    with pytest.raises(fc.GateFailed, match="id_unique"):
        fc.gate(result)


def test_check_warning_failure_is_amber(spark, gx_rules):
    result = fc.check("unified/orders", frame(spark, [(1, None, 1), (2, "b", 2)]), {"mode": "full"})
    assert fc.score(result) == (50.0, "Amber")


def test_scope_mode_checks_uniqueness_on_post_merge_image(spark, gx_rules, monkeypatch):
    from pipelines import io

    # Day 1 is outside the scope; its NULL value was already reported when it was written.
    current = frame(spark, [(1, None, 1), (2, "b", 2)])
    monkeypatch.setattr(io, "read_delta", lambda dataset_id, version=None: current)
    scope = {"mode": "scope", "keys": {"day": [2]}}

    replaced = fc.check("unified/orders", frame(spark, [(2, "c", 2)]), scope)
    assert [(r.rule_id, r.passed) for r in replaced.rules] == [("id_unique", True), ("value_not_null", True)]

    clash = fc.check("unified/orders", frame(spark, [(1, "c", 2)]), scope)
    assert [(r.rule_id, r.passed) for r in clash.rules] == [("id_unique", False), ("value_not_null", True)]


def test_scope_mode_reads_serving_tables_for_post_merge_image(spark, gx_rules, monkeypatch):
    from pipelines import io

    current = frame(spark, [(1, "a", 1)])
    monkeypatch.setattr(io, "read_pg", lambda table: current)
    clash = fc.check(
        "mart_shared.campaign_attributed_daily", frame(spark, [(1, "c", 2)]), {"mode": "scope", "keys": {"day": [2]}}
    )
    assert [(r.rule_id, r.passed) for r in clash.rules] == [("id_unique", False), ("value_not_null", True)]

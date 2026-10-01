import pytest

from fabric_control import DataQualityResult, GateFailed, RuleResult, gate, score


def result(*rules: tuple[str, bool]) -> DataQualityResult:
    return DataQualityResult("unified/orders", {"mode": "full"}, [RuleResult(f"r{i}", sev, ok) for i, (sev, ok) in enumerate(rules)])


def test_no_rules_is_green():
    assert score(result()) == (100.0, "Green")


def test_all_pass_is_green():
    assert score(result(("critical", True), ("warning", True))) == (100.0, "Green")


def test_critical_failure_is_red():
    assert score(result(("critical", False), *[("warning", True)] * 9)) == (90.0, "Red")


def test_ninety_percent_is_green():
    assert score(result(("warning", False), *[("critical", True)] * 9)) == (90.0, "Green")


def test_below_ninety_percent_is_amber():
    assert score(result(("warning", False), ("warning", False), *[("critical", True)] * 8)) == (80.0, "Amber")


def test_gate_raises_on_red():
    with pytest.raises(GateFailed):
        gate(result(("critical", False)))


def test_gate_passes_on_amber():
    gate(result(("warning", False), ("critical", True)))

from typing import Any

from fabric_control.clients import openmetadata
from fabric_control.clients.http import HttpError
from fabric_control.config import log, mode, stub
from fabric_control.decisions.scoring import score
from fabric_control.models import DataQualityResult, GateFailed, Scope
from fabric_control.registry import load_registry


def check(dataset_id: str, df: Any, scope: Scope) -> DataQualityResult:
    return stub("check", DataQualityResult(dataset_id, scope), dataset_id=dataset_id)


def report_data_quality(result: DataQualityResult) -> None:
    if mode() == "offline":
        stub("report_data_quality", dataset_id=result.dataset_id, score=score(result))
        return
    table_fqn = load_registry()[result.dataset_id]["om_fqn"]
    try:
        for rule in result.rules:
            outcome = "passed" if rule.passed else "failed"
            case = openmetadata.put_test_case(table_fqn, rule.rule_id, f"{rule.severity} rule")
            openmetadata.add_test_result(case, rule.passed, f"{rule.rule_id} {outcome} ({rule.severity})")
    except (HttpError, OSError) as e:
        log.warning("quality results for %s not pushed to OpenMetadata: %s", result.dataset_id, e)


def gate(result: DataQualityResult) -> None:
    pct, status = score(result)
    if status == "Red":
        failed = [r.rule_id for r in result.rules if r.severity == "critical" and not r.passed]
        raise GateFailed(f"{result.dataset_id}: critical rules failed {failed} ({pct}%)")

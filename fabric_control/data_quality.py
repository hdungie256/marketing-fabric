from typing import Any

from fabric_control.config import stub
from fabric_control.decisions.scoring import score
from fabric_control.models import DataQualityResult, GateFailed, Scope


def check(dataset_id: str, df: Any, scope: Scope) -> DataQualityResult:
    return stub("check", DataQualityResult(dataset_id, scope), dataset_id=dataset_id)


def report_data_quality(result: DataQualityResult) -> None:
    stub("report_data_quality", dataset_id=result.dataset_id, score=score(result))


def gate(result: DataQualityResult) -> None:
    pct, status = score(result)
    if status == "Red":
        failed = [r.rule_id for r in result.rules if r.severity == "critical" and not r.passed]
        raise GateFailed(f"{result.dataset_id}: critical rules failed {failed} ({pct}%)")

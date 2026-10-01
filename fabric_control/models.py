from dataclasses import dataclass, field
from typing import Any, Literal

Scope = dict[str, Any]
Event = dict[str, Any]
Severity = Literal["critical", "warning"]
Status = Literal["Green", "Amber", "Red"]


class GateFailed(Exception):
    pass


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    severity: Severity
    passed: bool


@dataclass
class DQResult:
    dataset_id: str
    scope: Scope
    rules: list[RuleResult] = field(default_factory=list)

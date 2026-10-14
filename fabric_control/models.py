from dataclasses import dataclass, field
from typing import Any, Literal

Scope = dict[str, Any]
Event = dict[str, Any]
Severity = Literal["critical", "warning"]
Status = Literal["Green", "Amber", "Red"]


class GateFailed(Exception):
    def __init__(self, message: str, rules: list[str] | None = None):
        super().__init__(message)
        self.rules = rules or []


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    severity: Severity
    passed: bool
    detail: str | None = None


@dataclass
class DataQualityResult:
    dataset_id: str
    scope: Scope
    rules: list[RuleResult] = field(default_factory=list)

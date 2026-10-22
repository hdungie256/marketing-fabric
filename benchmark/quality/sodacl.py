"""Translate the platform's dq/*.yml rules (GX expectation names) into SodaCL checks (Story 9.2)."""

from __future__ import annotations

from typing import Any

import yaml


def _bounds(kwargs: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v
        for k, v in (("valid min", kwargs.get("min_value")), ("valid max", kwargs.get("max_value")))
        if v is not None
    }


def check(rule: dict[str, Any]) -> dict[str, Any]:
    """One SodaCL check named after the rule_id; raises for expectations with no SodaCL twin."""
    kind, kw, name = rule["expectation"], rule.get("kwargs") or {}, {"name": rule["rule_id"]}
    if kind == "ExpectColumnValuesToNotBeNull":
        return {f"missing_count({kw['column']}) = 0": name}
    if kind == "ExpectColumnValuesToBeUnique":
        return {f"duplicate_count({kw['column']}) = 0": name}
    if kind == "ExpectCompoundColumnsToBeUnique":
        return {f"duplicate_count({', '.join(kw['column_list'])}) = 0": name}
    if kind == "ExpectColumnValuesToBeBetween":
        return {f"invalid_count({kw['column']}) = 0": {**name, **_bounds(kw)}}
    if kind == "ExpectColumnPairValuesAToBeGreaterThanB":
        op = "<" if kw.get("or_equal") else "<="
        return {"failed rows": {**name, "fail condition": f"{kw['column_A']} {op} {kw['column_B']}"}}
    raise ValueError(f"{rule['rule_id']}: no SodaCL translation for {kind}")


def checks_yaml(table: str, rules: list[dict[str, Any]]) -> str:
    return yaml.safe_dump({f"checks for {table}": [check(r) for r in rules]}, sort_keys=False)

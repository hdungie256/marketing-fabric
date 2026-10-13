from pathlib import Path
from typing import Any

import yaml

from fabric_control.clients import openmetadata, postgres
from fabric_control.clients.http import HttpError
from fabric_control.config import ROOT, log, mode, stub
from fabric_control.decisions.scoring import score
from fabric_control.models import DataQualityResult, GateFailed, RuleResult, Scope
from fabric_control.registry import load_registry
from fabric_control.run import current_run_id

SEVERITIES = ("critical", "warning")
# Rules over the whole table rather than single rows; in scope mode they see the post-merge image (AD-7).
TABLE_LEVEL = {
    "ExpectColumnValuesToBeUnique",
    "ExpectCompoundColumnsToBeUnique",
    "ExpectTableRowCountToEqual",
    "ExpectTableRowCountToBeBetween",
}


class RuleFileError(Exception):
    pass


def rules_path(dataset_id: str, registry: dict[str, dict] | None = None) -> Path:
    job_id = (registry or load_registry())[dataset_id]["job_id"]
    table = dataset_id.rsplit("/", 1)[-1].rsplit(".", 1)[-1]
    return ROOT / "pipelines" / "jobs" / job_id / "data_quality" / f"{table}.yml"


def load_rules(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise RuleFileError(f"{path}: quality rule file missing")
    rules = (yaml.safe_load(path.read_text()) or {}).get("rules") or []
    seen: set[str] = set()
    for rule in rules:
        rule_id = rule.get("rule_id")
        if not rule_id or rule_id in seen:
            raise RuleFileError(f"{path}: missing or duplicate rule_id {rule_id!r}")
        seen.add(rule_id)
        if rule.get("severity") not in SEVERITIES:
            raise RuleFileError(f"{path}: {rule_id} severity must be one of {SEVERITIES}")
        if not str(rule.get("expectation", "")).startswith("Expect"):
            raise RuleFileError(f"{path}: {rule_id} has no GX expectation")
    return rules


def post_merge(dataset_id: str, df: Any, scope: Scope) -> Any:
    from pyspark.sql import functions as F

    from pipelines import io
    from pipelines.io.scope import scope_predicate

    if not dataset_id.startswith("unified/"):
        # ponytail: serving marts need a PG read; add it with io.upsert_pg (Story 8.3)
        raise NotImplementedError(f"post-merge quality check for {dataset_id}")
    in_scope = F.coalesce(F.expr(scope_predicate(scope)), F.lit(False))
    current = io.read_delta(dataset_id).filter(~in_scope).select(*df.columns)
    return current.unionByName(df)


def validate(df: Any, rules: list[dict[str, Any]]) -> list[RuleResult]:
    import great_expectations as gx

    if not rules:
        return []
    context = gx.get_context(mode="ephemeral")
    batch = (
        context.data_sources.add_spark("fabric")
        .add_dataframe_asset("frame")
        .add_batch_definition_whole_dataframe("whole")
        .get_batch(batch_parameters={"dataframe": df})
    )
    results = []
    for rule in rules:
        expectation = getattr(gx.expectations, rule["expectation"])(**(rule.get("kwargs") or {}))
        outcome = batch.validate(expectation)
        unexpected = (outcome.result or {}).get("unexpected_count")
        error = (outcome.exception_info or {}).get("exception_message")
        detail = error or (f"{unexpected} unexpected" if unexpected else None)
        results.append(RuleResult(rule["rule_id"], rule["severity"], bool(outcome.success), detail))
    return results


def check(dataset_id: str, df: Any, scope: Scope) -> DataQualityResult:
    rules = load_rules(rules_path(dataset_id))
    if scope.get("mode") != "scope":
        return DataQualityResult(dataset_id, scope, validate(df, rules))
    row_rules = [r for r in rules if r["expectation"] not in TABLE_LEVEL]
    table_rules = [r for r in rules if r["expectation"] in TABLE_LEVEL]
    by_id = {r.rule_id: r for r in validate(df, row_rules)}
    if table_rules:
        by_id |= {r.rule_id: r for r in validate(post_merge(dataset_id, df, scope), table_rules)}
    return DataQualityResult(dataset_id, scope, [by_id[r["rule_id"]] for r in rules])


def report_data_quality(result: DataQualityResult) -> None:
    pct, status = score(result)
    if mode() == "offline":
        stub("report_data_quality", dataset_id=result.dataset_id, score=(pct, status))
        return
    postgres.write_dq_results(current_run_id(), result.dataset_id, result.scope, pct, status, result.rules)
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

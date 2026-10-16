import argparse
import json

import yaml

import fabric_control as fc
from fabric_control.glossary import governance_dir
from fabric_control.models import RuleResult
from pipelines import io
from pipelines.jobs.marts.shared.exceptions import transforms

JOB_ID = "marts/shared/exceptions"
INPUTS = [
    "unified/exceptions_shared_transaction_id",
    "unified/exceptions_coupon_mismatch",
    "unified/exceptions_coupon_plan_duplicate",
]
OUTPUTS = ["mart_shared.exceptions"]


def exception_marks() -> dict[str, int]:
    doc = yaml.safe_load((governance_dir() / "baselines.yml").read_text()) or {}
    return {key: int(value) for key, value in (doc.get("exceptions") or {}).items() if isinstance(value, int)}


def class_counts(df) -> dict[str, int]:
    return {row["class"]: row["n"] for row in df.groupBy("class").count().withColumnRenamed("count", "n").collect()}


def main(scope: dict) -> None:
    if scope.get("mode") != "full":
        raise ValueError(f"{JOB_ID} supports full refresh only, got {scope}")
    with fc.run(JOB_ID, scope) as run:
        merged = transforms.merge(*(io.read_delta(dataset_id) for dataset_id in INPUTS)).cache()
        marks = exception_marks()
        counts = class_counts(merged)
        rules = [
            RuleResult(
                f"{name}_count",
                "critical",
                marks.get(baseline) is not None and counts.get(name, 0) == marks[baseline],
            )
            for name, baseline in [
                ("shared_transaction_id", "shared_transaction_id"),
                ("coupon_plan_mismatch", "coupon_mismatch"),
            ]
        ]
        result = fc.check(OUTPUTS[0], merged, scope)
        result.rules += rules
        fc.report_data_quality(result)
        fc.gate(result)
        io.write_pg_full(OUTPUTS[0], merged, run.run_id, io.source_versions(INPUTS))
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

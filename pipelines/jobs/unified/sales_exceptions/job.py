import argparse
import json
from datetime import UTC, datetime

import yaml

import fabric_control as fc
from fabric_control.glossary import governance_dir
from fabric_control.models import RuleResult
from pipelines import io
from pipelines.jobs.unified._common import load_mapping
from pipelines.jobs.unified.sales_exceptions import transforms

JOB_ID = "unified/sales_exceptions"
INPUTS = ["raw/sales/sales_lines", "unified/coupon_plan"]
OUTPUTS = ["unified/exceptions_shared_transaction_id", "unified/exceptions_coupon_mismatch"]


def exception_marks() -> dict[str, int]:
    doc = yaml.safe_load((governance_dir() / "baselines.yml").read_text()) or {}
    return {key: int(value) for key, value in (doc.get("exceptions") or {}).items() if isinstance(value, int)}


def count_rules(shared_count: int, mismatch_count: int) -> dict[str, list[RuleResult]]:
    marks = exception_marks()
    return {
        OUTPUTS[0]: [
            RuleResult(
                "shared_transaction_count",
                "critical",
                marks.get("shared_transaction_id") is not None and shared_count == marks["shared_transaction_id"],
            )
        ],
        OUTPUTS[1]: [
            RuleResult(
                "coupon_mismatch_count",
                "critical",
                marks.get("coupon_mismatch") is not None and mismatch_count == marks["coupon_mismatch"],
            )
        ],
    }


def main(scope: dict) -> None:
    if scope.get("mode") != "full":
        raise ValueError(f"{JOB_ID} supports full refresh only, got {scope}")
    with fc.run(JOB_ID, scope) as run:
        detected_at = datetime.now(UTC)
        sales = io.read_raw(INPUTS[0])
        shared = transforms.shared_transaction_ids(sales, detected_at)
        mismatch = transforms.coupon_mismatches(sales, io.read_delta(INPUTS[1]), load_mapping(), detected_at)
        outputs = dict(zip(OUTPUTS, (shared, mismatch), strict=True))
        counts = {dataset_id: df.count() for dataset_id, df in outputs.items()}
        extra = count_rules(counts[OUTPUTS[0]], counts[OUTPUTS[1]])
        for dataset_id, df in outputs.items():
            result = fc.check(dataset_id, df, scope)
            result.rules += extra[dataset_id]
            fc.report_data_quality(result)
            fc.gate(result)
        for dataset_id, df in outputs.items():
            io.write_delta(dataset_id, df, run.run_id)
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

import argparse
import json

import fabric_control as fc
from fabric_control.models import RuleResult
from pipelines import io
from pipelines.jobs.marts.shared.campaign_spend import transforms

JOB_ID = "marts/shared/campaign_spend"
INPUTS = ["unified/campaign_spend", "unified/daily_spend"]
OUTPUTS = ["mart_shared.campaign_spend_allocated", "mart_shared.spend_reconciliation"]


def allocated_rules(allocated, spend, recon) -> list[RuleResult]:
    mart = transforms.total(allocated, "allocated")
    return [
        RuleResult(
            "allocated_total_matches_unified", "critical", mart == transforms.total(spend, "allocated_online_spend")
        ),
        RuleResult("allocated_total_matches_reconciliation", "critical", mart == transforms.total(recon, "allocated")),
    ]


def reconciliation_rules(recon, daily) -> list[RuleResult]:
    return [
        RuleResult("allocated_plus_unallocated_is_online", "critical", transforms.unbalanced_days(recon).isEmpty()),
        RuleResult("one_row_per_daily_spend_day", "critical", recon.count() == daily.count()),
    ]


def main(scope: dict) -> None:
    if scope.get("mode") != "full":
        raise ValueError(f"{JOB_ID} supports full refresh only, got {scope}")
    with fc.run(JOB_ID, scope) as run:
        spend, daily = (io.read_delta(d) for d in INPUTS)
        allocated = transforms.allocated(spend).cache()
        recon = transforms.reconciliation(daily, spend).cache()
        extra = {OUTPUTS[0]: allocated_rules(allocated, spend, recon), OUTPUTS[1]: reconciliation_rules(recon, daily)}
        outputs = dict(zip(OUTPUTS, (allocated, recon), strict=True))
        for dataset_id, df in outputs.items():
            result = fc.check(dataset_id, df, scope)
            result.rules += extra[dataset_id]
            fc.report_data_quality(result)
            fc.gate(result)
        versions = io.source_versions(INPUTS)
        for dataset_id, df in outputs.items():
            io.write_pg_full(dataset_id, df, run.run_id, versions)
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

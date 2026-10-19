import argparse
import json

import fabric_control as fc
from fabric_control.models import RuleResult
from pipelines import io
from pipelines.jobs.marts.campaign.target_achievement import transforms

JOB_ID = "marts/campaign/target_achievement"
INPUTS = [
    "unified/campaign_targets",
    "unified/campaigns",
    "mart_shared.campaign_attributed_daily",
    "mart_shared.campaign_spend_allocated",
]
OUTPUTS = ["mart_campaign.target_achievement"]


def target_rules(df, targets) -> list[RuleResult]:
    from pyspark.sql import functions as F

    ratio = F.col("actual").cast("double") / F.col("target_value").cast("double")
    expected = (
        F.when(ratio >= transforms.CONTINUE_AT, "continue").when(ratio >= transforms.STOP_BELOW, "adjust").otherwise("stop")
    )
    return [
        RuleResult("recommendation_matches_thresholds", "critical", df.filter(F.col("recommendation") != expected).isEmpty()),
        RuleResult("one_row_per_target", "critical", df.count() == targets.count()),
    ]


def main(scope: dict) -> None:
    if scope.get("mode") not in ("full", "scope"):
        raise ValueError(f"{JOB_ID}: unknown scope {scope}")
    with fc.run(JOB_ID, scope) as run:
        targets, campaigns = (transforms.narrow(io.read_delta(d), scope) for d in INPUTS[:2])
        daily, spend = (transforms.narrow(io.read_pg(d), scope) for d in INPUTS[2:])
        df = transforms.build(targets, campaigns, daily, spend).cache()
        result = fc.check(OUTPUTS[0], df, scope)
        result.rules += target_rules(df, targets)
        fc.report_data_quality(result)
        fc.gate(result)
        if scope["mode"] == "full":
            io.write_pg_full(OUTPUTS[0], df, run.run_id, io.source_versions(INPUTS))
        else:
            before, after = io.upsert_pg(OUTPUTS[0], df, scope, run.run_id)
            run.record_change(OUTPUTS[0], before, after)
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

import argparse
import json

import fabric_control as fc
from fabric_control.models import RuleResult
from pipelines import io
from pipelines.jobs.unified.campaign_spend import transforms
from pipelines.jobs.unified.campaigns.transforms import unknown_campaigns

JOB_ID = "unified/campaign_spend"
INPUTS = ["raw/spend/campaign_spend", "raw/spend/daily_spend", "unified/campaigns"]
OUTPUTS = ["unified/campaign_spend", "unified/daily_spend"]


def spend_rules(spend, daily, campaigns) -> list[RuleResult]:
    return [
        RuleResult("campaign_id_in_campaigns", "critical", unknown_campaigns(spend, campaigns).isEmpty()),
        RuleResult("date_in_daily_spend", "critical", transforms.days_without_daily_spend(spend, daily).isEmpty()),
        RuleResult("allocated_not_above_online", "critical", transforms.days_over_allocated(spend, daily).isEmpty()),
        RuleResult("date_in_campaign_window", "warning", transforms.outside_campaign_dates(spend, campaigns).isEmpty()),
    ]


def main(scope: dict) -> None:
    if scope.get("mode") != "full":
        raise ValueError(f"{JOB_ID} supports full refresh only, got {scope}")
    with fc.run(JOB_ID, scope) as run:
        spend = transforms.campaign_spend(io.read_raw(INPUTS[0])).cache()
        daily = transforms.daily_spend(io.read_raw(INPUTS[1])).cache()
        extra = {OUTPUTS[0]: spend_rules(spend, daily, io.read_delta(INPUTS[2])), OUTPUTS[1]: []}
        outputs = dict(zip(OUTPUTS, (spend, daily), strict=True))
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

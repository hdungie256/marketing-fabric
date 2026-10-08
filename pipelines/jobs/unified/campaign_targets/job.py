import argparse
import json

import fabric_control as fc
from fabric_control.models import RuleResult
from pipelines import io
from pipelines.jobs.unified.campaign_targets import transforms
from pipelines.jobs.unified.campaigns.transforms import unknown_campaigns

JOB_ID = "unified/campaign_targets"
INPUTS = ["raw/campaign/targets", "unified/campaigns"]
OUTPUTS = ["unified/campaign_targets"]


def cross_rules(df, campaigns) -> list[RuleResult]:
    return [RuleResult("campaign_id_in_campaigns", "critical", unknown_campaigns(df, campaigns).isEmpty())]


def main(scope: dict) -> None:
    if scope.get("mode") != "full":
        raise ValueError(f"{JOB_ID} supports full refresh only, got {scope}")
    with fc.run(JOB_ID, scope) as run:
        df = transforms.transform(io.read_raw(INPUTS[0]))
        result = fc.check(OUTPUTS[0], df, scope)
        result.rules += cross_rules(df, io.read_delta(INPUTS[1]))
        fc.report_data_quality(result)
        fc.gate(result)
        io.write_delta(OUTPUTS[0], df, run.run_id)
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

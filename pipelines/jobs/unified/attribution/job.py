import argparse
import json

import fabric_control as fc
from fabric_control.models import RuleResult
from pipelines import io
from pipelines.jobs.ingest.reconciliation import load_baselines
from pipelines.jobs.unified.attribution import transforms
from pipelines.jobs.unified.campaigns.transforms import unknown_campaigns

JOB_ID = "unified/attribution"
INPUTS = ["raw/campaign/attribution", "unified/ref_category_map", "unified/orders", "unified/campaigns"]
OUTPUTS = ["unified/attribution"]


def cross_rules(df, orders, campaigns, baseline: int | None) -> list[RuleResult]:
    return [
        RuleResult("order_key_in_orders", "critical", transforms.orphan_links(df, orders).isEmpty()),
        RuleResult("campaign_id_in_campaigns", "critical", unknown_campaigns(df, campaigns).isEmpty()),
        RuleResult("row_count_baseline", "critical", baseline is not None and df.count() == baseline),
        RuleResult(
            "order_date_in_campaign_window", "warning", transforms.outside_campaign_window(df, campaigns).isEmpty()
        ),
    ]


def main(scope: dict) -> None:
    if scope.get("mode") != "full":
        raise ValueError(f"{JOB_ID} supports full refresh only, got {scope}")
    with fc.run(JOB_ID, scope) as run:
        df = transforms.transform(io.read_raw(INPUTS[0]), io.read_delta(INPUTS[1])).cache()
        result = fc.check(OUTPUTS[0], df, scope)
        result.rules += cross_rules(
            df, io.read_delta(INPUTS[2]), io.read_delta(INPUTS[3]), load_baselines().get(INPUTS[0])
        )
        fc.report_data_quality(result)
        fc.gate(result)
        io.write_delta(OUTPUTS[0], df, run.run_id)
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

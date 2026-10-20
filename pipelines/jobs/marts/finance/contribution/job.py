import argparse
import json

import fabric_control as fc
from fabric_control.models import RuleResult
from pipelines import io
from pipelines.jobs.marts.finance.budget_daily.transforms import in_scope
from pipelines.jobs.marts.finance.contribution import transforms

JOB_ID = "marts/finance/contribution"
INPUTS = [
    "unified/order_lines",
    "unified/attribution",
    "unified/product_cost",
    "unified/campaigns",
    "mart_shared.campaign_spend_allocated",
    "mart_shared.campaign_attributed_daily",
]
OUTPUTS = ["mart_finance.contribution", "mart_finance.contribution_sku"]


def main(scope: dict) -> None:
    if scope.get("mode") not in ("full", "scope"):
        raise ValueError(f"{JOB_ID}: unknown scope {scope}")
    with fc.run(JOB_ID, scope) as run:
        lines, attribution, product_cost, campaigns = (io.read_delta(d) for d in INPUTS[:4])
        spend, attributed_daily = (in_scope(io.read_pg(d), scope) for d in INPUTS[4:])
        attribution, campaigns = in_scope(attribution, scope), in_scope(campaigns, scope)
        skus = transforms.contribution_sku(lines, attribution, product_cost).cache()
        per_campaign = transforms.contribution(skus, campaigns, spend, attributed_daily).cache()
        extra = {
            OUTPUTS[0]: [
                RuleResult(
                    "sku_gross_matches_shared", "warning", transforms.gross_mismatch(skus, attributed_daily).isEmpty()
                )
            ],
            OUTPUTS[1]: [],
        }
        outputs = dict(zip(OUTPUTS, (per_campaign, skus), strict=True))
        for dataset_id, df in outputs.items():
            result = fc.check(dataset_id, df, scope)
            result.rules += extra[dataset_id]
            fc.report_data_quality(result)
            fc.gate(result)
        if scope["mode"] == "full":
            versions = io.source_versions(INPUTS)
            for dataset_id, df in outputs.items():
                io.write_pg_full(dataset_id, df, run.run_id, versions)
        else:
            versions = io.source_versions(INPUTS)
            for dataset_id, df in outputs.items():
                before, after = io.upsert_pg(dataset_id, df, scope, run.run_id, versions)
                run.record_change(dataset_id, before, after)
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

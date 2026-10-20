import argparse
import json

import fabric_control as fc
from fabric_control.models import RuleResult
from pipelines import io
from pipelines.jobs.marts.finance.budget_daily import transforms

JOB_ID = "marts/finance/budget_daily"
INPUTS = ["mart_shared.campaign_spend_allocated", "mart_shared.campaign_attributed_daily", "unified/campaigns"]
OUTPUTS = ["mart_finance.budget_daily"]


def rules(df, spend, attributed) -> list[RuleResult]:
    return [
        RuleResult("campaign_id_in_campaigns", "critical", df.filter("campaign_name IS NULL").isEmpty()),
        RuleResult(
            "allocated_total_matches_shared",
            "critical",
            transforms.total(df, "allocated") == transforms.total(spend, "allocated"),
        ),
        RuleResult(
            "orders_total_matches_shared",
            "critical",
            transforms.total(df, "attributed_orders") == transforms.total(attributed, "attributed_orders"),
        ),
    ]


def main(scope: dict) -> None:
    if scope.get("mode") not in ("full", "scope"):
        raise ValueError(f"{JOB_ID}: unknown scope {scope}")
    with fc.run(JOB_ID, scope) as run:
        spend, attributed = (transforms.in_scope(io.read_pg(d), scope) for d in INPUTS[:2])
        campaigns = transforms.in_scope(io.read_delta(INPUTS[2]), scope)
        df = transforms.budget_daily(spend, attributed, campaigns).cache()
        result = fc.check(OUTPUTS[0], df, scope)
        result.rules += rules(df, spend, attributed)
        fc.report_data_quality(result)
        fc.gate(result)
        if scope["mode"] == "full":
            io.write_pg_full(OUTPUTS[0], df, run.run_id, io.source_versions(INPUTS))
        else:
            before, after = io.upsert_pg(OUTPUTS[0], df, scope, run.run_id, io.source_versions(INPUTS))
            run.record_change(OUTPUTS[0], before, after)
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

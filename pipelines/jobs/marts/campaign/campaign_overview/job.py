import argparse
import json

import fabric_control as fc
from fabric_control.models import RuleResult
from pipelines import io
from pipelines.jobs.marts.campaign.campaign_overview import transforms

JOB_ID = "marts/campaign/campaign_overview"
INPUTS = ["mart_shared.campaign_attributed_daily", "mart_shared.campaign_attributed_orders", "unified/campaigns"]
OUTPUTS = ["mart_campaign.campaign_overview"]


def overview_rules(overview, daily, campaigns) -> list[RuleResult]:
    from pyspark.sql import functions as F

    totals = overview.filter(F.col("campaign_id") == transforms.ALL)
    fy = {r.period_id: r.attributed_orders for r in totals.filter(F.col("period_id").startswith("FY")).collect()}
    by_year = daily.groupBy(F.year("date").alias("y")).agg(F.sum("attributed_orders").alias("n")).collect()
    expected = {f"FY{r.y}": r.n for r in by_year}
    per_campaign = (
        overview.filter(F.col("campaign_id") != transforms.ALL)
        .groupBy("period_id")
        .agg(F.sum("attributed_buyers").alias("campaign_buyers"))
    )
    buyers_ok = totals.join(per_campaign, "period_id").filter(F.col("attributed_buyers") > F.col("campaign_buyers")).isEmpty()
    grid = len(transforms.periods(r.y for r in by_year)) * (campaigns.count() + 1)
    return [
        RuleResult("fy_orders_match_daily", "critical", fy == expected),
        RuleResult("all_buyers_not_above_campaign_sum", "critical", buyers_ok),
        RuleResult("full_grid", "critical", overview.count() == grid),
    ]


def main(scope: dict) -> None:
    if scope.get("mode") != "full":
        raise ValueError(f"{JOB_ID} supports full refresh only, got {scope}")
    with fc.run(JOB_ID, scope) as run:
        daily, orders = (io.read_pg(d) for d in INPUTS[:2])
        campaigns = io.read_delta(INPUTS[2])
        overview = transforms.build(daily, orders, campaigns).cache()
        result = fc.check(OUTPUTS[0], overview, scope)
        result.rules += overview_rules(overview, daily, campaigns)
        fc.report_data_quality(result)
        fc.gate(result)
        io.write_pg_full(OUTPUTS[0], overview, run.run_id, io.source_versions(INPUTS))
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

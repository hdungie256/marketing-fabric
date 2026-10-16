import argparse
import json

import fabric_control as fc
from fabric_control.models import RuleResult
from pipelines import io
from pipelines.jobs.marts.campaign.comparison import transforms

JOB_ID = "marts/campaign/comparison"
INPUTS = ["mart_shared.campaign_attributed_daily", "mart_shared.campaign_attributed_orders", "unified/campaigns"]
OUTPUTS = ["mart_campaign.comparison"]


def comparison_rules(df, daily, campaigns) -> list[RuleResult]:
    from pyspark.sql import functions as F

    campaign_rows = df.filter(F.col("compare_by") == "campaign")
    channel_rows = df.filter(F.col("compare_by") == "channel")
    campaign_orders = campaign_rows.groupBy("period_id").agg(F.sum("attributed_orders").alias("campaign_orders"))
    channel_orders = channel_rows.groupBy("period_id").agg(F.sum("attributed_orders").alias("channel_orders"))
    orders_ok = (
        campaign_orders.join(channel_orders, "period_id")
        .filter(F.col("campaign_orders") != F.col("channel_orders"))
        .isEmpty()
    )
    fy = {r.period_id: r.campaign_orders for r in campaign_orders.filter(F.col("period_id").startswith("FY")).collect()}
    by_year = daily.groupBy(F.year("date").alias("y")).agg(F.sum("attributed_orders").alias("n")).collect()
    campaign_buyers = campaign_rows.groupBy("period_id", "channel").agg(F.sum("attributed_buyers").alias("sum_buyers"))
    buyers_ok = (
        channel_rows.join(campaign_buyers, ["period_id", "channel"])
        .filter(F.col("attributed_buyers") > F.col("sum_buyers"))
        .isEmpty()
    )
    n_channels = campaigns.select("channel").distinct().count()
    grid = len(transforms.periods(r.y for r in by_year)) * (campaigns.count() + n_channels)
    return [
        RuleResult("campaign_orders_equal_channel_orders", "critical", orders_ok),
        RuleResult("fy_orders_match_daily", "critical", fy == {f"FY{r.y}": r.n for r in by_year}),
        RuleResult("channel_buyers_not_above_campaign_sum", "critical", buyers_ok),
        RuleResult("full_grid", "critical", df.count() == grid),
    ]


def main(scope: dict) -> None:
    if scope.get("mode") != "full":
        raise ValueError(f"{JOB_ID} supports full refresh only, got {scope}")
    with fc.run(JOB_ID, scope) as run:
        daily, orders = (io.read_pg(d) for d in INPUTS[:2])
        campaigns = io.read_delta(INPUTS[2])
        df = transforms.build(daily, orders, campaigns).cache()
        result = fc.check(OUTPUTS[0], df, scope)
        result.rules += comparison_rules(df, daily, campaigns)
        fc.report_data_quality(result)
        fc.gate(result)
        io.write_pg_full(OUTPUTS[0], df, run.run_id, io.source_versions(INPUTS))
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

import argparse
import json

import fabric_control as fc
from fabric_control.models import RuleResult
from pipelines import io
from pipelines.jobs.marts.campaign.new_returning import transforms

JOB_ID = "marts/campaign/new_returning"
INPUTS = ["mart_shared.campaign_attributed_orders", "unified/campaigns"]
OUTPUTS = ["mart_campaign.new_returning"]


def new_returning_rules(df, campaigns) -> list[RuleResult]:
    from pyspark.sql import functions as F

    identity = df.filter(F.col("first_observed_buyers") + F.col("returning_buyers") != F.col("attributed_buyers"))
    years = [r.y for r in df.select(F.year("period_start").alias("y")).distinct().collect()]
    grid = len(transforms.periods(years)) * (campaigns.count() + 1)
    return [
        RuleResult("first_plus_returning_equals_buyers", "critical", identity.isEmpty()),
        RuleResult("full_grid", "critical", df.count() == grid),
    ]


def main(scope: dict) -> None:
    if scope.get("mode") != "full":
        raise ValueError(f"{JOB_ID} supports full refresh only, got {scope}")
    with fc.run(JOB_ID, scope) as run:
        orders = io.read_pg(INPUTS[0])
        campaigns = io.read_delta(INPUTS[1])
        df = transforms.build(orders, campaigns).cache()
        result = fc.check(OUTPUTS[0], df, scope)
        result.rules += new_returning_rules(df, campaigns)
        fc.report_data_quality(result)
        fc.gate(result)
        io.write_pg_full(OUTPUTS[0], df, run.run_id, io.source_versions(INPUTS))
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

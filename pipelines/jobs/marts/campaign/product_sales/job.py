import argparse
import json

import fabric_control as fc
from fabric_control.models import RuleResult
from pipelines import io
from pipelines.jobs.marts.campaign.product_sales import transforms

JOB_ID = "marts/campaign/product_sales"
INPUTS = ["unified/order_lines", "unified/ref_category_map", "unified/attribution", "unified/campaigns"]
OUTPUTS = ["mart_campaign.product_sales"]
NEST = ["Nest", "Nest-USA", "Nest-Canada"]


def product_rules(sales, lines) -> list[RuleResult]:
    from pyspark.sql import functions as F

    all_rows = sales.filter(F.col("campaign_id") == transforms.ALL)
    sold = all_rows.agg(F.sum("gross_value")).first()[0]
    expected = lines.agg(F.sum("line_gross_value")).first()[0]
    totals = all_rows.select("month", "product_sku", F.col("gross_value").alias("all_gross"))
    campaign_above = (
        sales.filter(F.col("campaign_id") != transforms.ALL)
        .join(totals, ["month", "product_sku"], "left")
        .filter(F.col("all_gross").isNull() | (F.col("gross_value") > F.col("all_gross")))
        .isEmpty()
    )
    in_lines = {
        r[0] for r in lines.filter(F.col("product_category").isin(NEST)).select("product_category").distinct().collect()
    }
    in_sales = {r[0] for r in sales.select("canonical_category").distinct().collect()}
    return [
        RuleResult("all_gross_matches_lines", "critical", sold == expected),
        RuleResult("campaign_not_above_all", "critical", campaign_above),
        RuleResult("nest_categories_separate", "critical", in_lines <= in_sales),
    ]


def main(scope: dict) -> None:
    if scope.get("mode") != "full":
        raise ValueError(f"{JOB_ID} supports full refresh only, got {scope}")
    with fc.run(JOB_ID, scope) as run:
        lines, category_map, attribution, campaigns = (io.read_delta(d) for d in INPUTS)
        sales = transforms.build(lines, attribution, category_map, campaigns).cache()
        result = fc.check(OUTPUTS[0], sales, scope)
        result.rules += product_rules(sales, lines)
        fc.report_data_quality(result)
        fc.gate(result)
        io.write_pg_full(OUTPUTS[0], sales, run.run_id, io.source_versions(INPUTS))
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

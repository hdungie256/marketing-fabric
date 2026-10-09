import argparse
import json

import fabric_control as fc
from fabric_control.models import RuleResult
from pipelines import io
from pipelines.jobs.ingest.reconciliation import load_baselines
from pipelines.jobs.marts.shared.campaign_attributed_daily import transforms

JOB_ID = "marts/shared/campaign_attributed_daily"
INPUTS = ["unified/attribution", "unified/orders", "unified/customers"]
OUTPUTS = ["mart_shared.campaign_attributed_orders", "mart_shared.campaign_attributed_daily"]
BASELINE = "raw/campaign/attribution"


def order_rules(per_order, attribution, orders, customers, baseline: int | None) -> list[RuleResult]:
    return [
        RuleResult("orders_row_count", "critical", baseline is not None and per_order.count() == baseline),
        RuleResult("order_key_in_orders", "critical", transforms.missing_orders(attribution, orders).isEmpty()),
        RuleResult(
            "customer_id_in_customers", "critical", transforms.missing_customers(attribution, customers).isEmpty()
        ),
    ]


def daily_rules(per_day, per_order) -> list[RuleResult]:
    total = per_day.agg({"attributed_orders": "sum"}).first()[0] or 0
    return [RuleResult("daily_orders_total", "critical", total == per_order.count())]


def main(scope: dict) -> None:
    if scope.get("mode") != "full":
        raise ValueError(f"{JOB_ID} supports full refresh only, got {scope}")
    with fc.run(JOB_ID, scope) as run:
        attribution, orders, customers = (io.read_delta(d) for d in INPUTS)
        per_order = transforms.attributed_orders(attribution, orders, customers).cache()
        per_day = transforms.daily(per_order).cache()
        extra = {
            OUTPUTS[0]: order_rules(per_order, attribution, orders, customers, load_baselines().get(BASELINE)),
            OUTPUTS[1]: daily_rules(per_day, per_order),
        }
        outputs = dict(zip(OUTPUTS, (per_order, per_day), strict=True))
        for dataset_id, df in outputs.items():
            result = fc.check(dataset_id, df, scope)
            result.rules += extra[dataset_id]
            fc.report_data_quality(result)
            fc.gate(result)
        versions = io.source_versions(INPUTS)
        for dataset_id, df in outputs.items():
            io.write_pg_full(dataset_id, df, run.run_id, versions)
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

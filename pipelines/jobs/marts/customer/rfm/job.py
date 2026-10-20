import argparse
import json
from pathlib import Path

import yaml

import fabric_control as fc
from fabric_control.config import contracts_dir
from fabric_control.glossary import governance_dir
from fabric_control.models import RuleResult
from pipelines import io

from . import transforms

JOB_ID = "marts/customer/rfm"
INPUTS = ["unified/orders", "unified/customers", "unified/order_lines"]
OUTPUTS = ["mart_customer.rfm"]
MART_DIR = Path(__file__).resolve().parent


def load_params() -> tuple[str, list[dict]]:
    as_of = yaml.safe_load((contracts_dir() / "constants.yml").read_text())["AS_OF_DATE"]
    segments = yaml.safe_load((governance_dir() / "mappings" / "rfm_segments.yml").read_text())["segments"]
    return str(as_of), segments


def main(scope: dict) -> None:
    if scope.get("mode") != "full":
        raise ValueError(f"{JOB_ID} supports full refresh only, got {scope}")
    with fc.run(JOB_ID, scope) as run:
        orders, customers, lines = (io.read_delta(d) for d in INPUTS)
        as_of, rules = load_params()
        df = transforms.build_rfm(orders, customers, lines, as_of, rules).cache()
        result = fc.check(OUTPUTS[0], df, scope)
        buyers = df.count()
        distinct = orders.select("customer_id").distinct().count()
        result.rules += [
            RuleResult("buyers_match_unified_orders", "critical", buyers == distinct),
            RuleResult("every_buyer_has_segment", "critical", df.filter("segment IS NULL").isEmpty()),
        ]
        fc.report_data_quality(result)
        fc.gate(result)
        io.write_pg_full(OUTPUTS[0], df, run.run_id, io.source_versions(INPUTS))
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

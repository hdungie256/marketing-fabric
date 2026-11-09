import argparse
import json

import fabric_control as fc
from pipelines import io
from pipelines.jobs.unified._common import load_mapping

from . import transforms

JOB_ID = "unified/product_cost"
INPUTS = ["raw/erp/product_costs"]
OUTPUTS = ["unified/product_cost"]


def main(scope: dict) -> None:
    with fc.run(JOB_ID, scope) as run:
        df = transforms.build_product_cost(io.read_raw(INPUTS[0]), load_mapping())
        result = fc.check(OUTPUTS[0], df, scope)
        fc.report_data_quality(result)
        fc.gate(result)
        io.write_delta(OUTPUTS[0], df, run.run_id, replace_where=None if scope["mode"] == "full" else scope)
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

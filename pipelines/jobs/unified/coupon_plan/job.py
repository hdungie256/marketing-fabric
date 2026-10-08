import argparse
import json
from datetime import UTC, datetime

import fabric_control as fc
from pipelines import io
from pipelines.jobs.unified.coupon_plan import transforms

JOB_ID = "unified/coupon_plan"
INPUTS = ["raw/promotion/coupon_plan", "unified/ref_category_map"]
OUTPUTS = ["unified/coupon_plan", "unified/exceptions_coupon_plan_duplicate"]


def main(scope: dict) -> None:
    if scope.get("mode") != "full":
        raise ValueError(f"{JOB_ID} supports full refresh only, got {scope}")
    with fc.run(JOB_ID, scope) as run:
        kept, dropped = transforms.transform(io.read_raw(INPUTS[0]), io.read_delta(INPUTS[1]))
        found = transforms.exceptions(dropped, kept, datetime.now(UTC))
        outputs = dict(zip(OUTPUTS, (kept, found), strict=True))
        for dataset_id, df in outputs.items():
            result = fc.check(dataset_id, df, scope)
            fc.report_data_quality(result)
            fc.gate(result)
        for dataset_id, df in outputs.items():
            io.write_delta(dataset_id, df, run.run_id)
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

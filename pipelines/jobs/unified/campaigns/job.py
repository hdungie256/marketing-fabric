import argparse
import json

import fabric_control as fc
from pipelines import io
from pipelines.jobs.unified.campaigns import transforms

JOB_ID = "unified/campaigns"
INPUTS = ["raw/campaign/campaigns", "unified/ref_category_map"]
OUTPUTS = ["unified/campaigns"]


def main(scope: dict) -> None:
    if scope.get("mode") != "full":
        raise ValueError(f"{JOB_ID} supports full refresh only, got {scope}")
    with fc.run(JOB_ID, scope) as run:
        df = transforms.transform(io.read_raw(INPUTS[0]), io.read_delta(INPUTS[1]))
        result = fc.check(OUTPUTS[0], df, scope)
        fc.report_data_quality(result)
        fc.gate(result)
        io.write_delta(OUTPUTS[0], df, run.run_id)
        fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

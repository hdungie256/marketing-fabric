import argparse
import json

import fabric_control as fc
from pipelines import io

from . import transforms

JOB_ID = "marts/example/example_daily"
INPUTS = ["unified/example"]
OUTPUTS = ["mart_example.example_daily"]


def main(scope: dict) -> None:
    with fc.run(JOB_ID, scope) as run:
        df = transforms.transform(io.read_delta(INPUTS[0]))
        result = fc.check(OUTPUTS[0], df, scope)
        fc.report_data_quality(result)
        fc.gate(result)
        if scope["mode"] == "full":
            io.write_pg_full(OUTPUTS[0], df, run.run_id)
        else:
            before, after = io.upsert_pg(OUTPUTS[0], df, scope, run.run_id)
            run.record_change(OUTPUTS[0], before, after)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", type=json.loads, default={"mode": "full"})
    main(parser.parse_args().scope)

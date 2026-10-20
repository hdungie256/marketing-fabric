import argparse
import json

import fabric_control as fc
from pipelines.io.result import write_result

OUTPUTS = []


def main(event: dict) -> list[dict]:
    plan = fc.refresh_plan(fc.affected_by(event))
    for step in plan:
        print(f"{step['job_id']} {json.dumps(step['scope'])} after {step['needs']}", flush=True)
    write_result(plan)
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=json.loads, required=True)
    main(parser.parse_args().event)

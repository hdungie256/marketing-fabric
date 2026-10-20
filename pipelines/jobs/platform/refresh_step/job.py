import argparse
import json
import runpy
import sys

import fabric_control as fc

OUTPUTS = []
SKIPPED = 99


def main(job_id: str, scope: dict, needs: list[str]) -> None:
    blocked = fc.blocked(needs)
    if blocked:
        print(f"skipping {job_id}: {', '.join(blocked)} did not succeed in this run", flush=True)
        sys.exit(SKIPPED)
    sys.argv = [job_id, "--scope", json.dumps(scope)]
    runpy.run_module(f"pipelines.jobs.{job_id.replace('/', '.')}.job", run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("job_id")
    parser.add_argument("--scope", type=json.loads, required=True)
    parser.add_argument("--needs", type=json.loads, default=[])
    args = parser.parse_args()
    main(args.job_id, args.scope, args.needs)

import argparse
import json
import traceback

import fabric_control as fc
from pipelines.io.spark import clear_cache
from pipelines.jobs.platform.refresh_step import job as refresh_step

OUTPUTS = []


def run_step(step: dict) -> bool:
    try:
        refresh_step.main(step["job_id"], step["scope"], step["needs"])
    except SystemExit as exc:
        return exc.code in (None, 0)
    except Exception:
        traceback.print_exc()
        return False
    finally:
        clear_cache()
    return True


def main(event: dict) -> None:
    plan = fc.refresh_plan(fc.affected_by(event))
    for step in plan:
        print(f"{step['job_id']} {json.dumps(step['scope'])} after {step['needs']}", flush=True)
    failed = [step["job_id"] for step in plan if not run_step(step)]
    if failed:
        raise SystemExit(f"did not succeed: {', '.join(failed)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=json.loads, required=True)
    main(parser.parse_args().event)

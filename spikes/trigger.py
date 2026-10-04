import json
import os
import time
import urllib.request

BASE = os.environ["AIRFLOW_URL"]
DAG_ID = "spike_docker"


def call(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=headers
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


if __name__ == "__main__":
    start = time.time()
    token = call(
        "POST",
        "/auth/token",
        {"username": os.environ["AIRFLOW_ADMIN_USER"], "password": os.environ["AIRFLOW_ADMIN_PASSWORD"]},
    )["access_token"]
    run = call("POST", f"/api/v2/dags/{DAG_ID}/dagRuns", {"logical_date": None, "conf": {}}, token)
    run_id = run["dag_run_id"]
    print("triggered", run_id, flush=True)
    while (state := call("GET", f"/api/v2/dags/{DAG_ID}/dagRuns/{run_id}", token=token)["state"]) in (
        "queued",
        "running",
    ):
        time.sleep(2)
    xcom = call(
        "GET", f"/api/v2/dags/{DAG_ID}/dagRuns/{run_id}/taskInstances/check/xcomEntries/return_value", token=token
    )
    print(f"state={state} check_result={xcom['value']} seconds={time.time() - start:.1f}", flush=True)

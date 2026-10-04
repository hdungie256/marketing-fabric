import os
import time
import urllib.parse
from typing import Any

from fabric_control.clients.http import HttpError, request

DONE = ("success", "failed")


def url(path: str) -> str:
    return os.environ["AIRFLOW_URL"].rstrip("/") + path


def token() -> str:
    body = {"username": os.environ["AIRFLOW_USER"], "password": os.environ["AIRFLOW_PASSWORD"]}
    return request("POST", url("/auth/token"), body)["access_token"]


def call(method: str, path: str, body: Any = None) -> Any:
    return request(method, url(path), body, {"Authorization": f"Bearer {token()}"})


def run_path(dag_id: str, run_id: str) -> str:
    return f"/api/v2/dags/{dag_id}/dagRuns/{urllib.parse.quote(run_id, safe='')}"


def trigger_dag(dag_id: str, conf: dict[str, Any]) -> str:
    return call("POST", f"/api/v2/dags/{dag_id}/dagRuns", {"logical_date": None, "conf": conf})["dag_run_id"]


def wait(dag_id: str, run_id: str, timeout: float = 600, poll: float = 2) -> str:
    deadline = time.monotonic() + timeout
    while (state := call("GET", run_path(dag_id, run_id))["state"]) not in DONE:
        if time.monotonic() > deadline:
            raise TimeoutError(f"{dag_id} {run_id} still {state} after {timeout}s")
        time.sleep(poll)
    return state


def xcom(dag_id: str, run_id: str, task_id: str, key: str = "return_value") -> Any:
    return call("GET", f"{run_path(dag_id, run_id)}/taskInstances/{task_id}/xcomEntries/{key}")["value"]


def put_pool(name: str, slots: int) -> None:
    body = {"name": name, "slots": slots, "include_deferred": False}
    try:
        call("POST", "/api/v2/pools", body)
    except HttpError as e:
        if e.status != 409:
            raise
        call("PATCH", f"/api/v2/pools/{name}", body)

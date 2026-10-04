import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

from pipelines.io import read_delta
from pipelines.io.spark import get_spark

OM = os.environ["OM_URL"] + "/v1/"
TOKEN = Path(os.environ.get("OM_BOT_TOKEN_FILE", "/run/om/bot_token")).read_text()
DATASET = "raw/spike/s3_delta"
OM_FQN = "lake_raw.default.lake.s3_delta"
RULE_ID = "row_count_positive"


def call(method: str, path: str, body: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(urllib.request.Request(OM + path, data, headers, method=method)) as response:
        return json.loads(response.read() or "{}")


def report(om_fqn: str, rule_id: str, passed: bool, name: str, value: object, definition: str, params: dict) -> str:
    case = call(
        "PUT",
        "dataQuality/testCases",
        {
            "name": rule_id,
            "entityLink": f"<#E::table::{om_fqn}>",
            "testDefinition": definition,
            "parameterValues": [{"name": k, "value": str(v)} for k, v in params.items()],
        },
    )
    fqn = case["fullyQualifiedName"]
    call(
        "POST",
        f"dataQuality/testCases/testCaseResults/{urllib.parse.quote(fqn, safe='')}",
        {
            "timestamp": int(time.time() * 1000),
            "testCaseStatus": "Success" if passed else "Failed",
            "result": f"{name}={value}",
            "testResultValue": [{"name": name, "value": str(value)}],
        },
    )
    return fqn


if __name__ == "__main__":
    get_spark("spike_dq")
    rows = read_delta(DATASET).count()
    fqn = report(OM_FQN, RULE_ID, rows >= 1, "rowCount", rows, "tableRowCountToBeBetween", {"minValue": 1})
    assert fqn == f"{OM_FQN}.{RULE_ID}", fqn
    latest = call("GET", f"dataQuality/testCases/name/{urllib.parse.quote(fqn, safe='')}?fields=testCaseResult")
    result = latest["testCaseResult"]
    print(f"test case {fqn}: {result['testCaseStatus']} ({result['result']})", flush=True)

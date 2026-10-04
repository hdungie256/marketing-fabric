import base64
import os
import time
import urllib.parse
from pathlib import Path
from typing import Any

from fabric_control.clients.http import HttpError, request

DEFAULT_ADMIN_PASSWORD = "admin"
EMAIL_DOMAIN = "open-metadata.org"
BOT = "ingestion-bot"
PIPELINE_SERVICE = "fabric"
RULE_DEFINITION = "fabricRule"
INGESTION_DONE = ("success", "failed", "partialSuccess")


def url(path: str) -> str:
    return os.environ["OM_URL"].rstrip("/") + "/v1/" + path


def quote(fqn: str) -> str:
    return urllib.parse.quote(fqn, safe="")


def token_file() -> Path:
    return Path(os.environ.get("OM_BOT_TOKEN_FILE", "/run/om/bot_token"))


def call(method: str, path: str, body: Any = None, token: str | None = None) -> Any:
    token = token or token_file().read_text().strip()
    return request(method, url(path), body, {"Authorization": f"Bearer {token}"})


def login(user: str, password: str) -> str | None:
    body = {"email": f"{user}@{EMAIL_DOMAIN}", "password": base64.b64encode(password.encode()).decode()}
    try:
        return request("POST", url("users/login"), body)["accessToken"]
    except HttpError as e:
        if e.status == 401:
            return None
        raise


def admin_token(user: str, password: str) -> str:
    token = login(user, password)
    if token:
        return token
    default = login(user, DEFAULT_ADMIN_PASSWORD)
    if not default:
        raise RuntimeError("OpenMetadata admin login failed with OM_ADMIN_PASSWORD and the default password")
    change = {
        "username": user,
        "oldPassword": DEFAULT_ADMIN_PASSWORD,
        "newPassword": password,
        "confirmPassword": password,
        "requestType": "SELF",
    }
    call("PUT", "users/changePassword", change, token=default)
    token = login(user, password)
    if not token:
        raise RuntimeError("OpenMetadata admin login failed after setting OM_ADMIN_PASSWORD")
    return token


def write_bot_token(admin: str) -> Path:
    bot_user = call("GET", f"bots/name/{BOT}", token=admin)["botUser"]["id"]
    jwt = call("GET", f"users/auth-mechanism/{bot_user}", token=admin)["config"]["JWTToken"]
    path = token_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(jwt)
    path.chmod(0o600)
    return path


def table_id(fqn: str) -> str:
    return call("GET", f"tables/name/{quote(fqn)}")["id"]


def put_pipeline(name: str) -> str:
    service = {
        "name": PIPELINE_SERVICE,
        "serviceType": "CustomPipeline",
        "connection": {"config": {"type": "CustomPipeline"}},
    }
    call("PUT", "services/pipelineServices", service)
    return call("PUT", "pipelines", {"name": name, "service": PIPELINE_SERVICE})["id"]


def add_lineage(from_id: str, to_id: str, pipeline_id: str) -> None:
    edge = {
        "fromEntity": {"id": from_id, "type": "table"},
        "toEntity": {"id": to_id, "type": "table"},
        "lineageDetails": {"pipeline": {"id": pipeline_id, "type": "pipeline"}, "source": "Manual"},
    }
    call("PUT", "lineage", {"edge": edge})


def put_rule_definition() -> None:
    definition = {
        "name": RULE_DEFINITION,
        "displayName": "Fabric rule",
        "description": "Rule declared in dq/<dataset>.yml and evaluated by fabric jobs",
        "entityType": "TABLE",
        "testPlatforms": ["GreatExpectations"],
        "parameterDefinition": [],
    }
    call("PUT", "dataQuality/testDefinitions", definition)


def put_test_case(table_fqn: str, rule_id: str, description: str) -> str:
    case = {
        "name": rule_id,
        "description": description,
        "entityLink": f"<#E::table::{table_fqn}>",
        "testDefinition": RULE_DEFINITION,
        "parameterValues": [],
    }
    return call("PUT", "dataQuality/testCases", case)["fullyQualifiedName"]


def add_test_result(test_case_fqn: str, passed: bool, result: str) -> None:
    body = {
        "timestamp": int(time.time() * 1000),
        "testCaseStatus": "Success" if passed else "Failed",
        "result": result,
        "testResultValue": [{"name": "passed", "value": str(passed).lower()}],
    }
    call("POST", f"dataQuality/testCases/testCaseResults/{quote(test_case_fqn)}", body)


def put_database_service(name: str, service_type: str, config: dict[str, Any]) -> dict[str, Any]:
    body = {"name": name, "serviceType": service_type, "connection": {"config": {"type": service_type, **config}}}
    return call("PUT", "services/databaseServices", body)


def put_ingestion_pipeline(service: dict[str, Any]) -> dict[str, Any]:
    body = {
        "name": f"{service['name']}_metadata",
        "pipelineType": "metadata",
        "service": {"id": service["id"], "type": "databaseService"},
        "sourceConfig": {"config": {"type": "DatabaseMetadata"}},
        "airflowConfig": {},
    }
    return call("PUT", "services/ingestionPipelines", body)


def trigger_ingestion(pipeline_id: str, timeout: float = 120, poll: float = 5) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            call("POST", f"services/ingestionPipelines/trigger/{pipeline_id}")
            return
        except HttpError as e:
            if e.status != 400 or time.monotonic() > deadline:
                raise
            time.sleep(poll)


def run_ingestion(pipeline: dict[str, Any], timeout: float = 600, poll: float = 5) -> str:
    call("POST", f"services/ingestionPipelines/deploy/{pipeline['id']}")
    started = int(time.time() * 1000) - 5000
    trigger_ingestion(pipeline["id"])
    path = f"services/ingestionPipelines/{quote(pipeline['fullyQualifiedName'])}/pipelineStatus"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        end = int(time.time() * 1000) + 60000
        runs = call("GET", f"{path}?startTs={started}&endTs={end}").get("data", [])
        states = [r["pipelineState"] for r in runs if r.get("startDate", 0) >= started]
        if states and states[0] in INGESTION_DONE:
            return states[0]
        time.sleep(poll)
    raise TimeoutError(f"ingestion {pipeline['fullyQualifiedName']} not finished after {timeout}s")


def ingest(service_name: str, timeout: float = 600) -> str:
    fqn = f"{service_name}.{service_name}_metadata"
    return run_ingestion(call("GET", f"services/ingestionPipelines/name/{quote(fqn)}"), timeout)

import base64
import os
import re
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
COLUMN_TYPES = {
    "string": "STRING",
    "int": "INT",
    "bigint": "BIGINT",
    "double": "DOUBLE",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMP",
}


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


def column(name: str, kind: str) -> dict[str, Any]:
    decimal = re.fullmatch(r"decimal\((\d+),(\d+)\)", kind)
    if decimal:
        precision, scale = int(decimal[1]), int(decimal[2])
        return {"name": name, "dataType": "DECIMAL", "precision": precision, "scale": scale, "dataTypeDisplay": kind}
    return {"name": name, "dataType": COLUMN_TYPES[kind], "dataTypeDisplay": kind}


def put_table(table_fqn: str, columns: list[tuple[str, str]]) -> str:
    service, database, schema, name = table_fqn.split(".")
    call("PUT", "databases", {"name": database, "service": service})
    call("PUT", "databaseSchemas", {"name": schema, "database": f"{service}.{database}"})
    body = {
        "name": name,
        "databaseSchema": f"{service}.{database}.{schema}",
        "tableType": "Regular",
        "columns": [column(n, k) for n, k in columns],
    }
    return call("PUT", "tables", body)["id"]


def delete_ingestion_pipeline(fqn: str) -> None:
    try:
        call("DELETE", f"services/ingestionPipelines/name/{quote(fqn)}?hardDelete=true")
    except HttpError as e:
        if e.status != 404:
            raise


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


def put_glossary(name: str, display_name: str, description: str) -> str:
    body = {"name": name, "displayName": display_name, "description": description}
    return call("PUT", "glossaries", body)["id"]


def put_glossary_term(glossary: str, name: str, display_name: str, description: str) -> str:
    body = {"name": name, "displayName": display_name, "description": description, "glossary": glossary}
    return call("PUT", "glossaryTerms", body)["id"]


def put_classification(name: str, description: str) -> None:
    call("PUT", "classifications", {"name": name, "description": description})


def put_tag(classification: str, name: str, description: str) -> None:
    call("PUT", "tags", {"name": name, "description": description, "classification": classification})


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


def latest_state(pipeline: dict[str, Any], since: int) -> str | None:
    path = f"services/ingestionPipelines/{quote(pipeline['fullyQualifiedName'])}/pipelineStatus"
    end = int(time.time() * 1000) + 60000
    runs = call("GET", f"{path}?startTs={since}&endTs={end}").get("data", [])
    states = [r["pipelineState"] for r in runs if r.get("startDate", 0) >= since]
    return states[0] if states else None


def run_ingestion(
    pipeline: dict[str, Any], timeout: float = 600, poll: float = 5, retrigger_after: float = 60, attempts: int = 3
) -> str:
    if not pipeline.get("deployed"):
        call("POST", f"services/ingestionPipelines/deploy/{pipeline['id']}")
    deadline = time.monotonic() + timeout
    for _ in range(attempts):
        since = int(time.time() * 1000) - 5000
        trigger_ingestion(pipeline["id"])
        quiet_until = time.monotonic() + retrigger_after
        while time.monotonic() < min(deadline, quiet_until):
            state = latest_state(pipeline, since)
            if state in INGESTION_DONE:
                return state
            if state:
                quiet_until = deadline
            time.sleep(poll)
    raise TimeoutError(f"ingestion {pipeline['fullyQualifiedName']} not finished after {attempts} attempts")


def ingest(service_name: str, timeout: float = 600) -> str:
    fqn = f"{service_name}.{service_name}_metadata"
    return run_ingestion(call("GET", f"services/ingestionPipelines/name/{quote(fqn)}"), timeout)

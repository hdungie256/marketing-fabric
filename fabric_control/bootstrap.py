import logging
import os
from typing import Any

from psycopg.conninfo import conninfo_to_dict

from fabric_control.clients import airflow, openmetadata
from fabric_control.metadata import register_all, sync_glossary, sync_tags
from fabric_control.migrations import run_migrations
from fabric_control.policy import sync_policies, verify_policies
from pipelines.io.storage import ensure_bucket
from sources.seed import seed

LAYERS = ("raw", "unified")
WRITE_POOL = "fabric_writes"
REFRESH_DAG = "full_refresh"


def delta_service(layer: str) -> tuple[str, str, dict[str, Any]]:
    security = {
        "awsAccessKeyId": os.environ["AWS_ACCESS_KEY_ID"],
        "awsSecretAccessKey": os.environ["AWS_SECRET_ACCESS_KEY"],
        "awsRegion": "us-east-1",
        "endPointURL": os.environ["S3_ENDPOINT"],
    }
    source = {"connection": {"securityConfig": security}, "bucketName": os.environ["S3_BUCKET"], "prefix": f"{layer}/"}
    return f"lake_{layer}", "DeltaLake", {"configSource": source}


def serving_service() -> tuple[str, str, dict[str, Any]]:
    dsn = conninfo_to_dict(os.environ["SERVING_DB_DSN"])
    config = {
        "hostPort": f"{dsn['host']}:{dsn.get('port', 5432)}",
        "username": dsn["user"],
        "authType": {"password": dsn["password"]},
        "database": dsn["dbname"],
    }
    return "serving", "Postgres", config


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log = logging.getLogger("bootstrap")
    airflow.put_pool(WRITE_POOL, 1)
    log.info("airflow pool %s ready", WRITE_POOL)
    log.info("sources seeded, versions %s", seed())
    ensure_bucket()
    admin = openmetadata.admin_token(os.environ["OM_ADMIN_USER"], os.environ["OM_ADMIN_PASSWORD"])
    log.info("bot token written to %s", openmetadata.write_bot_token(admin))
    openmetadata.put_rule_definition()
    run_migrations()
    log.info("migrations applied")
    for name, service_type, config in (delta_service(layer) for layer in LAYERS):
        openmetadata.put_database_service(name, service_type, config)
        openmetadata.delete_ingestion_pipeline(f"{name}.{name}_metadata")
    log.info("registered %s lake tables", len(register_all()))
    name, service_type, config = serving_service()
    service = openmetadata.put_database_service(name, service_type, config)
    state = openmetadata.run_ingestion(openmetadata.put_ingestion_pipeline(service))
    log.info("service %s ingestion %s", name, state)
    if state == "failed":
        raise SystemExit(f"ingestion for {name} failed")
    sync_tags()
    sync_glossary()
    log.info("tags and glossary synced")
    run_id = airflow.trigger_dag(REFRESH_DAG, {}, wait_for_dag=300)
    state = airflow.wait(REFRESH_DAG, run_id, timeout=3600, poll=10)
    log.info("%s %s: %s", REFRESH_DAG, run_id, state)
    if state != "success":
        raise SystemExit(f"{REFRESH_DAG} {run_id} {state}")
    sync_policies()
    verify_policies()
    log.info("policies synced and verified")


if __name__ == "__main__":
    main()

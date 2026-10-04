import logging
import os
from typing import Any

from psycopg.conninfo import conninfo_to_dict

from fabric_control.clients import airflow, openmetadata

LAYERS = ("raw", "unified")
WRITE_POOL = "fabric_writes"


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
    admin = openmetadata.admin_token(os.environ["OM_ADMIN_USER"], os.environ["OM_ADMIN_PASSWORD"])
    log.info("bot token written to %s", openmetadata.write_bot_token(admin))
    openmetadata.put_rule_definition()
    for name, service_type, config in [*(delta_service(layer) for layer in LAYERS), serving_service()]:
        service = openmetadata.put_database_service(name, service_type, config)
        state = openmetadata.run_ingestion(openmetadata.put_ingestion_pipeline(service))
        log.info("service %s ingestion %s", name, state)
        if state == "failed":
            raise SystemExit(f"ingestion for {name} failed")


if __name__ == "__main__":
    main()

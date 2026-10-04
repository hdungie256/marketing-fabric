import json
import os
import urllib.request

import psycopg

from pipelines.io import read_delta
from pipelines.io.spark import get_spark

SOURCE = "raw/spike/s3_delta"
TARGET = "spike.s3_delta"
SOURCE_FQN = "lake_raw.default.lake.s3_delta"
TARGET_FQN = "serving.serving.spike.s3_delta"
PIPELINE_SERVICE = "fabric"
JOB_ID = "spike_lineage"


def om(method: str, path: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        os.environ["OM_URL"] + "/v1/" + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {os.environ['OM_JWT']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or "{}")


def emit_lineage(job_id: str, inputs: list[str], outputs: list[str]) -> None:
    om(
        "PUT",
        "services/pipelineServices",
        {
            "name": PIPELINE_SERVICE,
            "serviceType": "CustomPipeline",
            "connection": {"config": {"type": "CustomPipeline"}},
        },
    )
    pipeline = om("PUT", "pipelines", {"name": job_id, "service": PIPELINE_SERVICE})
    for source in inputs:
        for target in outputs:
            edge = {
                "fromEntity": {"id": om("GET", f"tables/name/{source}")["id"], "type": "table"},
                "toEntity": {"id": om("GET", f"tables/name/{target}")["id"], "type": "table"},
                "lineageDetails": {"pipeline": {"id": pipeline["id"], "type": "pipeline"}, "source": "Manual"},
            }
            om("PUT", "lineage", {"edge": edge})


if __name__ == "__main__":
    info = psycopg.conninfo.conninfo_to_dict(os.environ["SERVING_DB_DSN"])
    with psycopg.connect(os.environ["SERVING_DB_DSN"], autocommit=True) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS spike")
    get_spark("spike_lineage")
    (
        read_delta(SOURCE)
        .write.format("jdbc")
        .option("url", f"jdbc:postgresql://{info['host']}:{info.get('port', 5432)}/{info['dbname']}")
        .option("dbtable", TARGET)
        .option("user", info["user"])
        .option("password", info["password"])
        .option("driver", "org.postgresql.Driver")
        .mode("overwrite")
        .save()
    )
    emit_lineage(JOB_ID, [SOURCE_FQN], [TARGET_FQN])
    print("lineage", SOURCE_FQN, "->", TARGET_FQN, flush=True)

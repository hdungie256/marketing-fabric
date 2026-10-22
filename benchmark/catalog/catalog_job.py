"""Register the platform's lake tables in a catalog, add job lineage, then query it (Story 9.2).

Usage: python -m benchmark.catalog.catalog_job <om|uc>
om uses the platform's own fabric_control calls (as bootstrap does); uc uses the Unity Catalog OSS REST API.
Unity Catalog OSS has no lineage API, so its lineage step is reported as unsupported.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
from pathlib import Path

from benchmark.processing.common import report

QUERIES = 10
UC_TYPES = {
    "string": "STRING",
    "int": "INT",
    "bigint": "LONG",
    "double": "DOUBLE",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMP",
}
DELTA_TYPES = {"int": "integer", "bigint": "long"}  # type_json uses Delta primitive names


def lake_datasets() -> list[str]:
    from fabric_control import load_registry

    return [d for d, entry in load_registry().items() if entry["om_fqn"].startswith("lake_")]


def job_edges(datasets: set[str]) -> list[tuple[str, list[str], list[str]]]:
    from fabric_control.config import ROOT
    from pipelines.dags.job_graph import declared, writers

    edges = []
    for job_id in sorted(set(writers(ROOT).values())):
        path = ROOT / "pipelines" / "jobs" / job_id / "job.py"
        inputs = [d for d in declared(path, "INPUTS") if d in datasets]
        outputs = [d for d in declared(path, "OUTPUTS") if d in datasets]
        if inputs and outputs:
            edges.append((job_id, inputs, outputs))
    return edges


def timed(steps: dict, name: str, action) -> None:
    started = time.perf_counter()
    action()
    steps[name] = round(time.perf_counter() - started, 2)


def om(steps: dict) -> dict:
    from fabric_control import emit_lineage, register_all
    from fabric_control.bootstrap import LAYERS, delta_service
    from fabric_control.clients import openmetadata

    admin = openmetadata.admin_token(os.environ["OM_ADMIN_USER"], os.environ["OM_ADMIN_PASSWORD"])
    openmetadata.write_bot_token(admin)
    for name, service_type, config in (delta_service(layer) for layer in LAYERS):
        openmetadata.put_database_service(name, service_type, config)
    datasets = lake_datasets()
    edges = job_edges(set(datasets))
    timed(steps, "register", register_all)
    timed(steps, "lineage", lambda: [emit_lineage(*edge) for edge in edges])
    path = "search/query?q=orders&index=table_search_index&size=10"
    timed(steps, "query_x10", lambda: [openmetadata.call("GET", path) for _ in range(QUERIES)])
    hits = openmetadata.call("GET", path)["hits"]["total"]["value"]
    return {"tables": len(datasets), "edges": sum(len(i) * len(o) for _, i, o in edges), "query_hits": hits}


def uc_call(method: str, path: str, body: dict | None = None):
    from fabric_control.clients.http import request

    return request(method, os.environ["UC_URL"].rstrip("/") + path, body)


def uc_column(position: int, name: str, kind: str) -> dict:
    type_name = "DECIMAL" if kind.startswith("decimal") else UC_TYPES[kind]
    column = {
        "name": name,
        "type_name": type_name,
        "type_text": kind,
        "position": position,
        "nullable": True,
        "type_json": json.dumps({"name": name, "type": DELTA_TYPES.get(kind, kind), "nullable": True, "metadata": {}}),
    }
    if type_name == "DECIMAL":
        precision, scale = kind[8:-1].split(",")
        column |= {"type_precision": int(precision), "type_scale": int(scale)}
    return column


def uc(steps: dict) -> dict:
    from fabric_control import load_registry
    from fabric_control.metadata import delta_columns

    registry = load_registry()
    datasets = lake_datasets()
    uc_call("POST", "/catalogs", {"name": "fabric"})
    for layer in ("lake_raw", "lake_unified"):
        uc_call("POST", "/schemas", {"name": layer, "catalog_name": "fabric"})

    def register() -> None:
        for dataset_id in datasets:
            schema = registry[dataset_id]["om_fqn"].split(".")[0]
            columns = [uc_column(i, n, k) for i, (n, k) in enumerate(delta_columns(dataset_id))]
            uc_call(
                "POST",
                "/tables",
                {
                    "name": dataset_id.rsplit("/", 1)[-1],
                    "catalog_name": "fabric",
                    "schema_name": schema,
                    "table_type": "EXTERNAL",
                    "data_source_format": "DELTA",
                    "storage_location": f"file:///tmp/lake/{dataset_id}",
                    "columns": columns,
                },
            )

    query = "/tables?" + urllib.parse.urlencode({"catalog_name": "fabric", "schema_name": "lake_unified"})
    timed(steps, "register", register)
    steps["lineage"] = None  # no lineage API in Unity Catalog OSS
    timed(steps, "query_x10", lambda: [uc_call("GET", query) for _ in range(QUERIES)])
    hits = sum("orders" in t["name"] for t in uc_call("GET", query)["tables"])
    return {"tables": len(datasets), "edges": 0, "query_hits": hits}


def main(tool: str) -> None:
    steps: dict = {}
    started = time.perf_counter()
    extra = om(steps) if tool == "om" else uc(steps)
    report(tool, Path("catalog"), started, steps=steps, **extra)


if __name__ == "__main__":
    main(sys.argv[1])

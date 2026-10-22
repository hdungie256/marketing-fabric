"""Shared settings and peak-memory probe for the processing benchmark (Story 9.1)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PARALLELISM = 2  # matches the container's --cpus
AS_OF = str(yaml.safe_load((ROOT / "contracts" / "constants.yml").read_text())["AS_OF_DATE"])
SEGMENTS = yaml.safe_load((ROOT / "governance" / "mappings" / "rfm_segments.yml").read_text())["segments"]
CATEGORY_MAP = {
    m["raw"]: m["canonical"]
    for m in yaml.safe_load((ROOT / "governance" / "mappings" / "category.yml").read_text())["mappings"]
}
RFM_COLUMNS = ["customer_id", "recency_days", "recency_score", "frequency_orders", "frequency_score", "monetary_value",
               "monetary_score", "segment", "categories", "gender", "location", "tenure_months"]  # fmt: skip
ORDER_COLUMNS = [
    "order_key",
    "customer_id",
    "transaction_id",
    "order_date",
    "gross_value",
    "shipping_fee",
    "line_count",
]


def peak_bytes() -> int | None:
    """Peak memory of the whole container (driver, JVM and workers) from cgroup v2."""
    path = Path("/sys/fs/cgroup/memory.peak")
    return int(path.read_text()) if path.exists() else None


def report(engine: str, data: Path, started: float, **extra) -> None:
    print("RESULT " + json.dumps({"engine": engine, "data": data.name, "job_s": round(time.perf_counter() - started, 2),
                                  "peak_bytes": peak_bytes(), **extra}))  # fmt: skip

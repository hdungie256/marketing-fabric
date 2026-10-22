"""Streamlit page render time and server footprint (Story 9.2). Runs in the dev image.

Usage: python -m benchmark.serving.serving_job
Renders Budget & Spend RENDERS times through streamlit.testing with demo-sized data (5 campaigns x 27 spend days,
365 reconciliation days), then starts `streamlit run app/main.py` and records time to /_stcore/health.
"""

from __future__ import annotations

import os
import statistics
import subprocess
import time
import urllib.request
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from benchmark.processing.common import report

RENDERS = 20
FRESH = datetime(2026, 10, 22, tzinfo=UTC)


class Source:
    def read(self, dataset_id):
        import pandas as pd

        if dataset_id == "mart_finance.budget_daily":
            rows = [
                (
                    f"CMP19_0{c}",
                    date(2019, 2 * c, 1) + timedelta(days=d),
                    f"Campaign {c}",
                    "Paid Search",
                    Decimal("18000.00"),
                    Decimal("730.15"),
                    9,
                    Decimal("1812.40"),
                    "synthetic",
                    FRESH,
                )
                for c in range(1, 6)
                for d in range(27)
            ]
            return pd.DataFrame(
                rows,
                columns=[
                    "campaign_id",
                    "date",
                    "campaign_name",
                    "channel",
                    "campaign_budget",
                    "allocated",
                    "attributed_orders",
                    "attributed_gross_value",
                    "provenance",
                    "_refreshed_at",
                ],
            )
        rows = [
            (
                date(2019, 1, 1) + timedelta(days=d),
                Decimal("1905.88"),
                Decimal("4500.00"),
                Decimal("270.05"),
                Decimal("1635.83"),
                "synthetic",
                FRESH,
            )
            for d in range(365)
        ]
        return pd.DataFrame(
            rows,
            columns=[
                "date",
                "online_spend",
                "offline_spend",
                "allocated",
                "unallocated",
                "provenance",
                "_refreshed_at",
            ],
        )


def page() -> None:
    import fabric_control
    from app.pages.finance import budget_spend
    from app.shell import session
    from benchmark.serving.serving_job import Source
    from fabric_control.glossary import load_terms

    terms = load_terms()
    fabric_control.term = terms.get
    fabric_control.effective_matrix = list
    budget_spend.current_source = Source
    session.set_role("UG04")
    budget_spend.render()


def render_ms() -> list[float]:
    from streamlit.testing.v1 import AppTest

    times = []
    for _ in range(RENDERS):
        started = time.perf_counter()
        app = AppTest.from_function(page).run(timeout=30)
        times.append((time.perf_counter() - started) * 1000)
        assert not app.exception, app.exception
    return times


def server_start_s() -> float:
    env = {**os.environ, "APP_DATA_MODE": "fixture", "FABRIC_CONTROL_MODE": "offline"}
    started = time.perf_counter()
    proc = subprocess.Popen(
        ["streamlit", "run", "app/main.py", "--server.headless=true", "--server.port=8599"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        while True:
            try:
                urllib.request.urlopen("http://localhost:8599/_stcore/health", timeout=1)
                return round(time.perf_counter() - started, 2)
            except OSError:
                time.sleep(0.1)
    finally:
        proc.terminate()
        proc.wait()


def main() -> None:
    started = time.perf_counter()
    times = render_ms()
    q = statistics.quantiles(times, n=20)
    report(
        "streamlit",
        Path("serving"),
        started,
        renders=RENDERS,
        p50_ms=round(statistics.median(times)),
        p95_ms=round(q[18]),
        first_ms=round(times[0]),
        server_start_s=server_start_s(),
    )


if __name__ == "__main__":
    main()

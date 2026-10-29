import re
from pathlib import Path

from tests.e2e.conftest import PURGE_E2E

ROOT = Path(__file__).resolve().parents[2]


def test_e2e_purge_deletes_run_children_before_the_runs():
    referencing = {
        re.search(r"TABLE (\S+)", statement)[1]
        for path in (ROOT / "migrations").rglob("*.sql")
        for statement in path.read_text().split(";")
        if "REFERENCES ops.runs" in statement
    }
    tables = [statement.split()[2] for statement in PURGE_E2E]
    assert referencing and tables[-1] == "ops.runs"
    assert referencing | {"ops.dq_results"} <= set(tables[:-1])

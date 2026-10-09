"""AD-17: jobs never run DDL and never overwrite over JDBC."""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
JOBS = ROOT / "pipelines" / "jobs"
DDL = re.compile(
    r"\b(?:(?:DROP|CREATE|ALTER)\s+(?:TABLE|SCHEMA|VIEW|INDEX|SEQUENCE|FUNCTION|MATERIALIZED|EXTENSION|TYPE)"
    r"|TRUNCATE\s+(?:TABLE\s+)?\w+\.\w+)",
    re.IGNORECASE,
)


def violations(source: str) -> list[str]:
    tree = ast.parse(source)
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    found = [f"DDL: {s.strip()[:60]}" for s in strings if DDL.search(s)]
    jdbc = "jdbc" in strings or any(isinstance(n, ast.Attribute) and n.attr == "jdbc" for n in ast.walk(tree))
    if jdbc and "overwrite" in strings:
        found.append("JDBC overwrite")
    return found


@pytest.mark.parametrize(
    "source",
    [
        'conn.execute("DROP TABLE mart_shared.x")',
        'conn.execute("create table if not exists mart_shared.x (a int)")',
        'conn.execute("ALTER TABLE mart_shared.x ADD COLUMN b int")',
        'conn.execute("TRUNCATE mart_shared.x")',
        'df.write.format("jdbc").mode("overwrite").save()',
        'df.write.jdbc(url, "t", mode="overwrite")',
    ],
)
def test_checker_flags_violations(source):
    assert violations(source)


@pytest.mark.parametrize(
    "source",
    [
        'F.create_map(F.lit("a"), F.lit(1))',
        'df.dropDuplicates(["a"]).drop("b")',
        'df.write.format("delta").mode("overwrite").save(path)',
        'io.write_pg_full("mart_shared.x", df, run_id, versions)',
    ],
)
def test_checker_allows_normal_code(source):
    assert violations(source) == []


def test_jobs_have_no_ddl_or_jdbc_overwrite():
    paths = [p for p in JOBS.rglob("*.py") if "_templates" not in p.parts]
    assert paths
    found = {str(p.relative_to(ROOT)): v for p in paths if (v := violations(p.read_text()))}
    assert found == {}

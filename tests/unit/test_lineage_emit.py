"""Every unified and mart job records its lineage in OpenMetadata (BR13, BR16).

Six unified jobs never called fc.emit_lineage, so live lineage stopped at unified/* and never reached raw/sales,
raw/crm or raw/erp, whatever depth the catalog asked for. Ingest and platform jobs have no upstream table.
"""

from pathlib import Path

JOBS = Path(__file__).resolve().parents[2] / "pipelines" / "jobs"


def test_unified_and_mart_jobs_emit_lineage():
    files = sorted([*JOBS.glob("unified/*/job.py"), *JOBS.glob("marts/*/*/job.py")])
    assert files
    missing = [
        str(f.relative_to(JOBS)) for f in files if "fc.emit_lineage(JOB_ID, INPUTS, OUTPUTS)" not in f.read_text()
    ]
    assert missing == []

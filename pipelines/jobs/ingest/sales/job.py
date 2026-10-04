from pipelines.io import sources
from pipelines.jobs.ingest.load import run_ingest

JOB_ID = "ingest/sales"
SOURCE = "sales"
OUTPUTS = [
    "raw/sales/sales_lines",
]

if __name__ == "__main__":
    run_ingest(
        JOB_ID,
        SOURCE,
        {
            OUTPUTS[0]: lambda: sources.read_db(SOURCE, "sales_lines"),
        },
    )

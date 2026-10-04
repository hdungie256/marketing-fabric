from pipelines.io import sources
from pipelines.jobs.ingest.load import run_ingest

JOB_ID = "ingest/crm"
SOURCE = "crm"
OUTPUTS = [
    "raw/crm/customers",
]

if __name__ == "__main__":
    run_ingest(
        JOB_ID,
        SOURCE,
        {
            OUTPUTS[0]: lambda: sources.read_db(SOURCE, "customers"),
        },
    )

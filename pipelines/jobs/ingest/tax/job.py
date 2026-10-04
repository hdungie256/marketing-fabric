from pipelines.io import sources
from pipelines.jobs.ingest.load import run_ingest

JOB_ID = "ingest/tax"
SOURCE = "tax"
OUTPUTS = [
    "raw/tax/tax_rates",
]

if __name__ == "__main__":
    run_ingest(
        JOB_ID,
        SOURCE,
        {
            OUTPUTS[0]: lambda: sources.read_csv(SOURCE, "tax_rates"),
        },
    )

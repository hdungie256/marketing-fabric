from pipelines.io import sources
from pipelines.jobs.ingest.load import run_ingest

JOB_ID = "ingest/promotion"
SOURCE = "promotion"
OUTPUTS = [
    "raw/promotion/coupon_plan",
]

if __name__ == "__main__":
    run_ingest(
        JOB_ID,
        SOURCE,
        {
            OUTPUTS[0]: lambda: sources.read_api(SOURCE, "coupon_plan"),
        },
    )

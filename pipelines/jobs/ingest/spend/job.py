from pipelines.io import sources
from pipelines.jobs.ingest.load import run_ingest

JOB_ID = "ingest/spend"
SOURCE = "spend"
OUTPUTS = [
    "raw/spend/campaign_spend",
    "raw/spend/daily_spend",
    "raw/spend/spend_recon",
]

if __name__ == "__main__":
    run_ingest(
        JOB_ID,
        SOURCE,
        {
            OUTPUTS[0]: lambda: sources.read_api(SOURCE, "campaign_spend"),
            OUTPUTS[1]: lambda: sources.read_csv(SOURCE, "daily_spend"),
            OUTPUTS[2]: lambda: sources.read_csv(SOURCE, "spend_recon"),
        },
    )

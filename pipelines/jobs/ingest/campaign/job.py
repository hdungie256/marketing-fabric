from pipelines.io import sources
from pipelines.jobs.ingest.load import run_ingest

JOB_ID = "ingest/campaign"
SOURCE = "campaign"
OUTPUTS = [
    "raw/campaign/campaigns",
    "raw/campaign/targets",
    "raw/campaign/attribution",
]

if __name__ == "__main__":
    run_ingest(
        JOB_ID,
        SOURCE,
        {
            OUTPUTS[0]: lambda: sources.read_api(SOURCE, "campaigns"),
            OUTPUTS[1]: lambda: sources.read_api(SOURCE, "targets"),
            OUTPUTS[2]: lambda: sources.read_api(SOURCE, "attribution"),
        },
    )

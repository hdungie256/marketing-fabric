from fabric_control.clients import openmetadata

OUTPUTS = []
SERVICES = ("lake_raw", "lake_unified", "serving")

if __name__ == "__main__":
    for service in SERVICES:
        state = openmetadata.ingest(service)
        print(f"{service}: {state}", flush=True)
        if state == "failed":
            raise SystemExit(f"catalog ingestion for {service} failed")

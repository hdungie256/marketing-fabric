import fabric_control as fc
from fabric_control.clients import openmetadata

OUTPUTS = []
SCANNED_SERVICES = ("serving",)

if __name__ == "__main__":
    print(f"registered {len(fc.register_all())} lake tables", flush=True)
    for service in SCANNED_SERVICES:
        state = openmetadata.ingest(service)
        print(f"{service}: {state}", flush=True)
        if state == "failed":
            raise SystemExit(f"catalog ingestion for {service} failed")

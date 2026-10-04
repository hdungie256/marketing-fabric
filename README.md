# Marketing Data Fabric

Demo data platform for campaign intelligence.

## Setup

Python 3.11, pip ≥ 25.1.

```bash
cp compose/.env.example compose/.env
pip install --group dev
```

Docker Desktop memory ≥ 12GB.

## Commands

| Command | Action |
|---|---|
| `make up` | Start full stack |
| `make up-dev` | Start Postgres, SeaweedFS, Streamlit (offline) |
| `make up-benchmark` | Start benchmark stack (pinned MinIO) |
| `make down` | Stop stack |
| `make reset` | Delete volumes and restart |
| `make migrate` | Run migrations, sync tags and policies |
| `make test` | Run tests |
| `make format` | Format and fix lint |
| `make lint` | Check format and lint |

## Local URLs

| Service | URL |
|---|---|
| Streamlit | http://localhost:8501 |
| API | http://localhost:8000/docs |
| OpenMetadata | http://localhost:8585 |
| Airflow | http://localhost:8080 |
| SeaweedFS S3 | http://localhost:8333 (S3 clients only) |
| SeaweedFS Filer | http://localhost:8888 |
| Postgres | localhost:5432 |
| MinIO (benchmark) | http://localhost:9001 |

OpenMetadata login: `admin@open-metadata.org` / `OM_ADMIN_PASSWORD` from `compose/.env` (`admin` until `python -m spikes.om_token` has run once).
Airflow login: `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` from `compose/.env`.

## Storage

Delta 3.3.3 on SeaweedFS via `s3a://` (path-style, static keys). Verified: write, overwrite, `replaceWhere`, time travel, VACUUM, append-only `raw/*` (`python -m spikes.s3_delta` in `fabric-jobs`).

OpenMetadata indexes Delta tables with its DeltaLake connector, one service per layer (`lake_raw`, `lake_unified`), so `om_fqn` = `lake_<layer>.default.lake.<table>`. Table names (last path segment) must be unique within a layer (`spikes/om_delta.yaml`).

Lineage is written by `emit_lineage()` via the OpenMetadata REST API using `om_fqn` from the registry, one pipeline per `job_id` under pipeline service `fabric` (`spikes/lineage.py`). Spark OpenLineage is not used: OpenMetadata cannot map `s3a://` Delta paths to tables without a Hive or Glue catalog.

SeaweedFS runs with `-volume.max=0` (the default of 8 volumes allows only one bucket) and `-s3.concurrentFileUploadLimit=2` (unlimited parallel uploads exhaust its 1 GB).

## Orchestration

Airflow runs each job as a `fabric-jobs` container via `DockerOperator` (`spark-submit --master local[*]`, `auto_remove`, `mount_tmp_dir=False`) on the compose network, forwarding fabric env vars. A job returns a value by writing a pickle that `retrieve_output` turns into XCom. Other services trigger DAGs with a JWT from `/auth/token` and `POST /api/v2/dags/<dag_id>/dagRuns` (`pipelines/dags/spike_docker.py`, `spikes/trigger.py`).

## Metadata access

Bootstrap logs in to OpenMetadata with `OM_ADMIN_USER`/`OM_ADMIN_PASSWORD`, replacing the default `admin` password on first run (OpenMetadata requires upper, lower, digit and special character), and writes the `ingestion-bot` JWT to volume `om-secrets` at `/run/om/bot_token` (`spikes/om_token.py`). Quality results go to OpenMetadata as test cases `<om_fqn>.<rule_id>` with one result per run (`spikes/dq.py`).

## Resources

Core memory limits total 11.25 GB. Measured peak 6.6 GB with a 10M-row Spark job running (`sh spikes/ram.sh`).

## Structure

```text
api/              Simulated Campaign, Coupon and Spend API
app/              Streamlit shell, pages, services, repositories
benchmark/        Benchmark profile work
compose/          Docker Compose, images, Postgres init
contracts/        Dataset registry, schemas, constants, fixtures
fabric_control/   Client for OpenMetadata, Airflow and Postgres admin
governance/       Glossary, tags, mappings
migrations/       Serving database migrations
pipelines/        DAGs, IO and jobs
scripts/          Repo checks
sources/          Source seeds and fault toggles
spikes/           Throwaway spike jobs
tests/            Unit, reconcile and e2e tests
```

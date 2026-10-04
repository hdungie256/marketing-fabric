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
| `make bootstrap` | Rerun bootstrap (also runs on `make up`): seed, catalog, migrations, `full_refresh` |
| `make seed` | Reseed sources from `sources/data/*.xlsx` (bumps `source_version`) |
| `make migrate` | Run migrations, sync tags and policies |
| `make test` | Run unit and reconcile tests |
| `make test-jobs` | Run unit tests in `fabric-jobs`, including Spark tests |
| `make test-e2e` | Run e2e tests against the running stack |
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

OpenMetadata login: `admin@open-metadata.org` / `OM_ADMIN_PASSWORD` from `compose/.env` (`admin` until bootstrap has run once).
Airflow login: `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` from `compose/.env`.

## Platform

- **Storage:** Delta 3.3.3 on SeaweedFS via `s3a://` (path-style, static keys). SeaweedFS runs with `-volume.max=0` (default 8 volumes allow one bucket) and `-s3.concurrentFileUploadLimit=2` (unlimited parallel uploads exhaust its 1 GB). Check: `scripts/check_storage.py`.
- **Bootstrap** (`fabric_control/bootstrap.py`): creates Airflow pool `fabric_writes`, sets the OpenMetadata admin password from `OM_ADMIN_PASSWORD` (needs upper, lower, digit, special), writes the `ingestion-bot` JWT to volume `om-secrets` (`/run/om/bot_token`), and registers and ingests services `lake_raw`, `lake_unified` (Delta) and `serving` (Postgres).
- **`om_fqn`:** `lake_<layer>.default.lake.<table>` for Delta, `serving.serving.<schema>.<table>` for Postgres. Delta table names (last path segment) must be unique within a layer.
- **Lineage:** `fabric_control.emit_lineage()` via REST, one pipeline per `job_id` under service `fabric`. Spark OpenLineage is not used: OpenMetadata cannot map `s3a://` paths to tables without a Hive or Glue catalog.
- **Quality:** `fabric_control.report_data_quality()` pushes each rule as test case `<om_fqn>.<rule_id>`. Lineage and quality failures log a warning and never fail the job.
- **Orchestration:** DAGs build tasks with `job_task(job_id)` from `pipelines/dags/job_task.py`: a `fabric-jobs` container per job (`python -m pipelines.jobs.<job>.job`, Spark `local[*]`, pool `fabric_writes`, `om-secrets` mounted). Task id is `job_id` with `/` replaced by `.`. A job returns an XCom value with `pipelines.io.result.write_result()`. Other services start DAGs with `fabric_control.trigger()`. Check: DAG `platform_smoke`.
- **Runs:** `fabric_control.run()` writes `ops.runs` (status `success`, `failed` or `gated`, rows in/out, failing step from `run.step`, Delta version) and `ops.alerts` on error.
- **Sources:** `sources/seed.py` loads the sample workbooks into 7 sources: Postgres `sources` DB (`sales`, `crm`, `erp`), mock API `GET /<source>/<table>` (`campaign`, `promotion`, `spend.campaign_spend`) and CSV files in bucket `sources` (`spend`, `tax`). Every table has `provenance` (`original`/`synthetic`).
- **Raw ingest:** `pipelines/jobs/ingest/load.py` appends to `raw/<source>/<table>` with `_load_id`, `_ingested_at`, `_source`, `_load_kind`, `_source_version`, then reconciles source vs raw rows and checksum plus `load_rows` in `governance/baselines.yml` into `ops.load_reconciliation`. `io.read_raw()` returns the latest row per registry `natural_key` from passed loads only, and refuses `derived` datasets (`spend_recon`). Before writing, the schema gate compares the source with `contracts/schemas/<dataset_id>.yml`: missing or retyped columns gate the run (`schema_drift`), extra columns are dropped with a warning. DAG `full_refresh` runs all ingest jobs, then refreshes the catalog.
- **Memory:** core limits total 11.25 GB; measured peak 6.6 GB with a 10M-row Spark job (`MEMORY_ROWS=10000000 sh scripts/check_memory.sh`).

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
tests/            Unit, reconcile and e2e tests
```

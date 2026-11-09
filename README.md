# Marketing Data Fabric

Demo data platform for campaign intelligence.

## Setup

Docker Desktop with memory ≥ 12GB. Every `make` target runs in Docker; no local Python needed.

```bash
cp compose/.env.example compose/.env
```

Editor support (optional): Python 3.11, `pip install --group dev`.

## Startup

`make up` starts the stack, then the one-shot `bootstrap` service brings it to a ready state (about 5–8 minutes on first run). It is done when this shows `Exited (0)`:

```bash
docker compose -f compose/docker-compose.yml ps -a bootstrap
```

Bootstrap steps, in order: create Airflow pool `fabric_writes` → seed sources → create the `lake` bucket → set OpenMetadata admin password and save the bot token → register the quality rule definition → apply migrations → register lake tables from contracts and scan `serving` → sync tags and glossary to OpenMetadata → run DAG `full_refresh` → sync and verify access policies. Rerunning is safe; `make reset` rebuilds from empty volumes to the same result.

Windows (WSL2): give the VM enough memory in `%UserProfile%\.wslconfig`, then run `wsl --shutdown`:

```ini
[wsl2]
memory=14GB
```

## Commands

| Command | Action |
|---|---|
| `make up` | Start full stack |
| `make up-dev` | Start Postgres, SeaweedFS, Streamlit (offline) |
| `make up-benchmark` | Start benchmark stack (pinned MinIO) |
| `make down` | Stop stack |
| `make reset` | Delete volumes and restart |
| `make bootstrap` | Rerun bootstrap (also runs on `make up`): seed, catalog, migrations, tags, glossary, `full_refresh`, policies |
| `make seed` | Reseed sources from `sources/data/*.xlsx` (bumps `source_version`) |
| `make migrate` | Run migrations, sync tags and policies |
| `make break-dq DATASET=<id>` | Dev only: make the next quality check on `<id>` fail a critical rule; `make fix-dq DATASET=<id>` removes it |
| `make test` | Run unit and reconcile tests (in Docker) |
| `make test-jobs` | Run unit tests in `fabric-jobs`, including Spark tests |
| `make test-e2e` | Run e2e tests against the running stack, reusing the latest `full_refresh` |
| `make test-e2e-full` | Same, but reseed and rerun `full_refresh` first |
| `make format` | Format and fix lint (in Docker) |
| `make lint` | Check format and lint (in Docker) |

Any test target takes `ARGS`, e.g. `make test-e2e ARGS="-k drift"`.

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
- **Bootstrap** (`fabric_control/bootstrap.py`): creates Airflow pool `fabric_writes`, sets the OpenMetadata admin password from `OM_ADMIN_PASSWORD` (needs upper, lower, digit, special), writes the `ingestion-bot` JWT to volume `om-secrets` (`/run/om/bot_token`), registers every Delta registry dataset with `fabric_control.register()` (columns from `contracts/schemas/`), and scans `serving` (Postgres) with the OpenMetadata connector.
- **`om_fqn`:** `lake_<layer>.default.lake.<table>` for Delta, `serving.serving.<schema>.<table>` for Postgres. Delta tables are registered, never scanned: OpenMetadata's DeltaLake connector loads whole tables into memory and runs out of memory as append-only raw grows.
- **Lineage:** `fabric_control.emit_lineage()` via REST, one pipeline per `job_id` under service `fabric`. Spark OpenLineage is not used: OpenMetadata cannot map `s3a://` paths to tables without a Hive or Glue catalog.
- **Quality:** `fabric_control.report_data_quality()` pushes each rule as test case `<om_fqn>.<rule_id>`. Lineage and quality failures log a warning and never fail the job.
- **Orchestration:** DAGs build tasks with `job_task(job_id)` from `pipelines/dags/job_task.py`: a `fabric-jobs` container per job (`python -m pipelines.jobs.<job>.job`, Spark `local[*]`, pool `fabric_writes`, `om-secrets` mounted). Task id is `job_id` with `/` replaced by `.`. A job returns an XCom value with `pipelines.io.result.write_result()`. Other services start DAGs with `fabric_control.trigger()`. Check: DAG `platform_smoke`.
- **Runs:** `fabric_control.run()` writes `ops.runs` (status `success`, `failed` or `gated`, rows in/out, failing step from `run.step`, Delta version) and `ops.alerts` on error.
- **Catalog read:** pages call `fabric_control.catalog(filter)`, `term(term_id)`, `search(q)`, `lineage(dataset_id, depth)` and `latest_score(dataset_id)`, never OpenMetadata. Results are keyed by `dataset_id` / `term_id`. Online, lineage and quality come from OpenMetadata and refresh time and version from `ops.runs`; offline, everything comes from `contracts/`, `governance/` and each job's `INPUTS`. `latest_score()` returns `"not yet measured"` when a dataset has no results.
- **Quality gate and stale:** a failing critical rule makes `gate()` raise `GateFailed` before the write, so the previous version stays. The run is recorded as `gated` in `ops.runs` with the failing rules, and its downstream jobs in the same DAG run do not run. `fabric_control.status(dataset_id)` reports a dataset as stale (`since`, `cause`, `datasets`) while it or any upstream dataset's latest run is gated; `shell.metric` then shows "Using previous version" and the page shows one banner naming the failed datasets. Both clear after the next successful write.
- **Access policy:** each role has its own Postgres login (`<ROLE>_DB_PASSWORD` in `compose/.env`), plus `app_writer` and `ops_writer`. `fabric_control.sync_policies()` builds one view `<schema>_v.<table>` per table in `mart_*`, `app` and `ops`, and grants roles the views only, never the tables. Columns are tagged under `columns:` in `governance/tags/<slice>.yml`; a tag's `actions` set `allow`, `mask:partial` or `deny` per role (no action means `deny`), and `governance/access_matrix.yml` lists who reads each dataset. An untagged column fails the sync. A denied column is NULL with a `<col>__denied` flag; a masked column is text. `verify_policies()` checks `ops.policy_effective` against real privileges and view output. Logins are created by `compose/pg-init/roles.sh` on a new volume; on an existing one run `docker compose -f compose/docker-compose.yml exec postgresql bash /pg-init/roles.sh`.
- **Sources:** `sources/seed.py` loads the sample workbooks into 7 sources: Postgres `sources` DB (`sales`, `crm`, `erp`), mock API `GET /<source>/<table>` (`campaign`, `promotion`, `spend.campaign_spend`) and CSV files in bucket `sources` (`spend`, `tax`). Every table has `provenance` (`original`/`synthetic`).
- **Raw ingest:** `pipelines/jobs/ingest/load.py` appends to `raw/<source>/<table>` with `_load_id`, `_ingested_at`, `_source`, `_load_kind`, `_source_version`, then reconciles source vs raw rows and checksum plus `load_rows` in `governance/baselines.yml` into `ops.load_reconciliation`. `io.read_raw()` returns the latest row per registry `natural_key` from passed loads only, and refuses `derived` datasets (`spend_recon`). Before writing, the schema gate compares the source with `contracts/schemas/<dataset_id>.yml`: missing or retyped columns gate the run (`schema_drift`), extra columns are dropped with a warning. DAG `full_refresh` runs every job that writes a registry dataset, ordered by each job's `INPUTS` (ingest → unified → marts), then registers lake tables, rescans `serving`, and syncs and verifies access policies; new jobs need no DAG edit (see **Full refresh**).
- **Spend edits:** `PUT /spend/campaign_spend/{campaign_id}/{date}` on the mock API with header `X-Fabric-Role`. Only roles listed under `edit:` in `governance/access_matrix.yml` may call it (403 otherwise). The allocation must be ≥ 0, keep that day's campaign allocations within its online spend, and fall inside the campaign period (422 with `field` and `reason`). A saved change bumps the `spend` `source_version`, records the event in `ops.source_events` and triggers `partial_refresh`; nothing else triggers it.
- **Impact analysis:** `fabric_control.affected_by(event)` walks lineage (each job's `INPUTS`, the same graph emitted to OpenMetadata) from the event's raw dataset and returns `[{dataset_id, job_id, scope}]` in topological order: the source, then `unified`, `mart_shared` and slice marts. Scope is projected onto each dataset's grain through `scope_map` in its manifest (`mart*.yml`, or `manifest*.yml` for `unified`); keys missing from `scope_map`, or datasets without `scope` in `modes`, get `{"mode": "full"}`. `refresh_plan(affected)` merges that into one step per job.
- **Scoped writes:** a job run with `--scope '{"mode":"scope","keys":{...}}'` (stored verbatim in `ops.runs.scope`) recomputes the grain rows matching the scope and replaces only those: `io.upsert_pg(table, df, scope, run_id, source_version)` runs `DELETE WHERE scope` + `INSERT` in one transaction and returns `(before, after)` read `FOR UPDATE`; `io.write_delta(..., replace_where=scope)` does the same in Delta, and the unified job stores the Delta version before and after in `ops.runs`. Scope keys not in a table's grain are dropped (`io.restrict`), so other rows keep their values and `_refreshed_at`. `run.record_change()` writes changed `metrics` values from the manifest to `ops.metric_change_log` with the run's `event_id` and the glossary term id, skipping columns whose tag is not `allow` for every reader of the log (e.g. SKU cost). Check: `tests/e2e/test_scoped_refresh.py`.
- **Full refresh:** DAG `full_refresh` runs one task, `platform/full_refresh`, in one container (pool `fabric_writes`) with the same runner as partial refresh: every job in `INPUTS` order as `{"mode": "full"}`, one shared SparkSession, cache cleared between jobs, one `ops.runs` row per job. A job runs only after its direct upstream jobs succeeded in this DAG run, so a failed or gated job skips all its descendants, while unrelated jobs still run; the task, and with it the DAG run, fails if any job did not succeed, and `platform/catalog` and `platform/policies` run regardless. Per-job progress is in `ops.runs` (Pipeline Status) and the task log; the Airflow grid shows one task. In one process, `io.source_versions()` reads each raw table's highest passed `_source_version` once and reuses it for later marts; `io.ops.write_reconciliation()` drops that dataset's entry when one of its loads is checked. The task holds the single `fabric_writes` slot for the whole run, so a spend edit made during a full refresh starts its partial refresh only after the full refresh ends. `FABRIC_FULL_REFRESH_PER_JOB=1` in `compose/.env` restores one task and one container per job (the partial refresh then waits for one job at most); apply it with `docker compose -f compose/docker-compose.yml --profile core up -d openmetadata-ingestion`, which recreates the Airflow container, and no code change. Check: `tests/e2e/test_full_refresh.py`.
- **Partial refresh:** DAG `partial_refresh` (conf = the change event) runs one task, `platform/partial_refresh`, in one container (pool `fabric_writes`): it builds `refresh_plan(affected_by(event))` and runs each job in plan order in the same process, sharing one SparkSession and clearing its cache between jobs. Each job still records its own row in `ops.runs`. A job whose upstream job in the same DAG run did not succeed is skipped, so a gated dataset stops its descendants and `status()` reports them stale; the task fails if any job did not succeed. Latency `max(ended_at) − emitted_at` is shown on Pipeline Status; measured 46–54 s on the sample data (target < 2 min), against 109–196 s with one container per job. Airflow runs with `AIRFLOW__CORE__PARALLELISM=4`: at the default 32, idle LocalExecutor workers fill the 2 GB container and the OOM killer stops the API server. Check: `tests/e2e/test_partial_refresh.py`.
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

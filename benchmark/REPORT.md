# Architecture benchmark report

Measured evidence for the architecture choices (Epic 9, NFR-5). Each section states what was run, what the numbers
are, and what they do not show. Raw numbers live in `benchmark/results/`.

## Processing: Spark vs Flink (Story 9.1)

**Choice: keep Spark.** At the demo's size and up to ×100 both engines finish the same job in seconds with identical
output, so speed does not decide. Spark wins on integration: it runs the demo's own transforms (no second copy of the
business logic), it is already in the `fabric-jobs` image, and Delta Lake, OpenLineage and GX all have Spark
integrations the platform uses. Flink would add a second image and a SQL copy of every rule to keep in sync.

### What was run

- **Job:** build `unified/orders` from sales lines, then the RFM mart (recency, frequency, monetary, the three quintile
  scores, segment, sorted categories, CRM profile) as of `AS_OF_DATE` 2019-12-31.
- **Spark 3.5.9:** `benchmark/processing/spark_job.py` calls the demo's `build_orders`, `canonical_column` and
  `build_rfm`.
- **Flink 2.2.1 (PyFlink, batch SQL):** `benchmark/processing/flink_job.py`. The segment `CASE` and the category map
  are generated from `governance/mappings/*.yml`, not hand-copied.
- **Data:** the sample workbooks replicated ×1, ×10 and ×100 (`benchmark/processing/data.py`). Copy *k* shifts both
  `customer_id` and `transaction_id` by *k* × 10,000,000, so every copy adds new customers and orders. Both engines
  read the same CSV files from a local volume; object storage is compared separately (Story 9.2).
- **Resources:** a fresh container per run, `--cpus=2 --memory=4g`, parallelism 2 for both engines. Spark driver
  memory 2g; Flink local minicluster with default memory settings.
- **Measures:** wall time of the whole container (includes JVM start), job time (inside the engine, after session
  start), and peak memory of the container from cgroup `memory.peak` (driver, JVM and workers together). Median of 3
  runs. Machine: Apple silicon (arm64) laptop, Docker via OrbStack; both images are native arm64.

### Results

| Scale | Sales lines | Engine | Wall time (s) | Job time (s) | Peak memory (MiB) | Outputs equal |
|---|---:|---|---:|---:|---:|---|
| ×1 | 52,924 | Spark | 5.63 | 3.89 | 788 | yes |
| ×1 | 52,924 | Flink | 5.59 | 3.63 | 864 | yes |
| ×10 | 529,240 | Spark | 9.17 | 7.39 | 981 | yes |
| ×10 | 529,240 | Flink | 8.74 | 6.47 | 1,348 | yes |
| ×100 | 5,292,400 | Spark | 22.70 | 19.28 | 2,924 | yes |
| ×100 | 5,292,400 | Flink | 25.20 | 22.41 | 2,386 | yes |

- **Correctness (checked):** at every scale Spark and Flink produce the same rows in both outputs (`exceptAll` both
  ways, duplicates counted): 26,631 / 266,310 / 2,663,100 orders and 1,468 / 14,680 / 146,800 RFM customers. The ×1
  order count matches the demo's 26,631 orders; the Spark side runs the demo's own transforms, so it is the demo
  result on the same input.
- **Speed:** wall times differ by at most 11% and job times by at most 16%; Flink is faster at ×1 and ×10, Spark at
  ×100. Single runs of the same engine vary by up to 23% (`processing_runs.csv`), so neither engine is clearly faster.
- **Memory:** Flink peaks higher at ×10 (1,348 vs 981 MiB) and lower at ×100 (2,386 vs 2,924 MiB). Spark's peak
  follows its 2g driver setting; Flink's minicluster was left at defaults, so memory compares configurations as much as
  engines.

### Integration effort

| | Spark | Flink |
|---|---|---|
| New code for the benchmark | 38 lines (`spark_job.py`) | 85 lines (`flink_job.py`, SQL included) |
| Business logic | 175 lines reused from the demo transforms | rewritten as SQL in those 85 lines |
| Image | existing `fabric-jobs` image | new `flink-bench` image, 2.6 GB; `apache-flink` has no arm64 wheel, so it is compiled with `build-essential` |
| Platform fit | Delta Lake, OpenLineage and GX Spark integrations already in use | none of these wired; would need connectors for Delta and lineage |

Pitfalls found while porting, each of which would silently change results: `NTILE` returns `BIGINT` in Flink (cast to
`INT`); the filesystem sink appends unless the insert is `INSERT OVERWRITE`; quintile ties need the same total order
(`metric, customer_id`) in both engines; money stays `DECIMAL`, never `DOUBLE`.

### Limits

- One laptop, 2 CPUs, data up to 5.3 million lines (about 324 MB of CSV). The comparison says nothing about clusters.
- Flink runs as a local minicluster in batch mode; streaming, its main strength, is not exercised by this workload.
- Spark's job time excludes session start; Flink's excludes `TableEnvironment` creation. Wall time includes both.

### Reproduce

```bash
docker build -t marketing-fabric/flink-bench:2.2.1 benchmark/flink        # or: docker compose --profile benchmark build flink-bench
docker run --rm -v "$PWD:/srv:ro" -v "$PWD/benchmark/data:/bench" -w /srv -e PYTHONPATH=/srv \
  marketing-fabric/fabric-jobs:latest python -m benchmark.processing.data /bench 1 10 100
python3 benchmark/processing/run.py 1 10 100   # writes benchmark/results/processing*.csv
```

## Layer alternatives (Story 9.2)

Every run below uses the harness in `benchmark/measure.py`: a fresh container per run, `--cpus=2 --memory=4g` for the
job, peak memory from cgroup `memory.peak`. Same laptop as Story 9.1.

| Layer | In use | Alternative measured | Choice |
|---|---|---|---|
| Storage | SeaweedFS 4.47 | MinIO (pinned last community build), local FS | Keep SeaweedFS |
| Catalog | OpenMetadata 2.0.2 | Unity Catalog OSS 0.6.0 | Keep OpenMetadata |
| Quality | GX Core 1.23.2 | Soda Core 3.5.6 (`soda-core-spark-df`) | Keep GX |
| Serving | Streamlit 1.64.0 | React (estimate, no prototype) | Keep Streamlit |

### Storage: SeaweedFS vs MinIO vs local FS

Workload (`benchmark/storage/storage_job.py`): the ×10 sales lines (529,240 rows) through Delta Lake as the platform
uses it: full write, scan with aggregate, `replaceWhere` of one month, 10 small appends (raw ingest pattern), time
travel to version 0. Each run starts a fresh storage server with the core stack's 1g limit. Median of 3 runs.

| Backend | Server start (s) | Server peak (MiB) | Write | Scan | replaceWhere | 10 appends | Time travel | Total (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SeaweedFS | 3.54 | 190 | 5.28 | 3.87 | 2.37 | 3.67 | 0.77 | 17.11 |
| MinIO | 0.56 | 179 | 3.12 | 3.36 | 3.10 | 3.51 | 1.11 | 14.98 |
| Local FS | — | — | 3.86 | 3.66 | 2.29 | 3.38 | 0.89 | 15.81 |

All three end with the same 539,240 rows. MinIO finishes the workload about 12% faster than SeaweedFS and starts in
under a second; memory is the same. **Keep SeaweedFS anyway:** the architecture records the MinIO image as the *last
community build* (no further community releases or fixes), and storage is reached only through the S3 API, so
switching later is a configuration change (`S3_ENDPOINT`), not a code change. Local FS is not an option for the shared
lake; it is listed as the floor.

### Catalog: OpenMetadata vs Unity Catalog OSS

Workload (`benchmark/catalog/catalog_job.py`): register the platform's 26 lake tables with columns from `contracts/`,
record job lineage (28 edges from the job graph), then run 10 queries. OpenMetadata uses the platform's own
`register_all()` and `emit_lineage()`; Unity Catalog uses its REST API. One run each; OpenMetadata startup is a restart
with migrations already applied.

| | OpenMetadata 2.0.2 | Unity Catalog OSS 0.6.0 |
|---|---:|---:|
| Containers | server + Elasticsearch (+ shared Postgres) | one server, embedded H2 |
| Start to healthy (s) | 57.0 | 3.6 |
| Peak memory (MiB) | 2,746 | 541 |
| Register 26 tables (s) | 1.98 | 0.34 |
| Lineage, 28 edges (s) | 4.24 | not supported |
| 10 queries (s) | 0.98 (full-text search) | 0.20 (list tables) |
| Query "orders" | 6 hits | 1 (name match only) |
| Glossary, classification tags, DQ test cases | yes | no |

Unity Catalog is about 5× lighter in memory and starts 16× faster, but it has no lineage, glossary, tags or quality
results, which BR13 (catalog and glossary), BR14 (quality and tags) and BR16 (lineage-driven refresh) need. Choosing it
would mean building those in `fabric_control`. **Keep OpenMetadata**; its cost is memory (2.7 GB of the 12 GB budget).
Its image is 1.2 GB and Elasticsearch's 1.6 GB; Unity Catalog's image is 5.8 GB on disk despite the small footprint.

### Quality: GX vs Soda Core

Workload (`benchmark/quality/quality_job.py`): the rules in `unified/orders`' `data_quality/orders.yml` on the same
cached Spark frame of unified orders, clean and with an injected duplicate `order_key` and NULL `gross_value`. GX runs
through the platform's `fabric_control.data_quality.validate()`; Soda runs SodaCL generated from the same file by
`benchmark/quality/sodacl.py`. Time covers validation only. Median of 3 runs.

| Scale | Orders | Clean: GX / Soda (s) | Broken: GX / Soda (s) | Same verdict |
|---|---:|---:|---:|---|
| ×1 | 26,631 | 10.65 / 3.96 | 10.98 / 20.13 | yes |
| ×10 | 266,310 | 16.92 / 5.22 | 10.97 / 18.10 | yes |
| ×100 | 2,663,100 | 16.05 / 6.41 | 12.70 / 34.61 | yes |

Both tools fail exactly `order_key_unique` and `gross_value_not_null` on broken data and pass clean data. Soda is
2.5–3.2× faster when data is clean and 1.6–2.7× slower when rules fail, which suggests it collects failing-row samples
(not measured separately). Peak memory is dominated by Spark and is similar (1.0–3.1 GiB).

The translator covers all 99 rules in the repository's `data_quality/*.yml` files (5 expectation types); only the 3
`orders` rules were executed against both tools, so equal verdicts for the other 96 are not verified. **Keep GX:** it
is already wired into `check()`, scoring, `ops.dq_results` and the OpenMetadata test-case push (AD-7), and its speed
difference is seconds per dataset. Soda remains a drop-in candidate if validation time on clean data matters.

### Serving: Streamlit vs React

Measured for Streamlit (`benchmark/serving/serving_job.py`): Budget & Spend rendered 20 times through
`streamlit.testing` with demo-sized data (5 campaigns × 27 spend days, 365 reconciliation days), and the time for
`streamlit run app/main.py` to answer `/_stcore/health`.

| Measure | Value |
|---|---:|
| Render p50 / p95 | 91 ms / 568 ms |
| First (cold) render | 590 ms |
| Server start | 0.54 s |
| Peak memory (renders and server) | 176 MiB |

All are under the 3 s page target (NFR-4); this is server-side render time and excludes network and browser.

**React: documented estimate, not measured.** The app is about 3,100 lines of Python across the shell and 16 pages.
A React front end would need the same pages and shell components rewritten in TypeScript, plus an HTTP API for every
read: today the pages query Postgres views directly with the viewer's own role login (AD-8), while `api/` only exposes
`sources` and `spend`. Keeping column policy in Postgres would require that API to open connections per role. The
estimate is several weeks of work for a 4-person team against a 4-week project, for no requirement Streamlit misses.
**Keep Streamlit.**

### Reproduce

```bash
docker compose -f compose/docker-compose.yml --profile benchmark build minio
docker build -t marketing-fabric/quality-bench:latest benchmark/quality
python3 benchmark/storage/run.py                 # results/storage*.csv
python3 benchmark/quality/run.py 1 10 100        # results/quality*.csv
python3 benchmark/catalog/run.py                 # results/catalog.csv (needs compose/.env)
python3 -c "import sys; sys.path.insert(0, '.'); from pathlib import Path; from benchmark.measure import run; \
  print(run('marketing-fabric/dev:latest', ['python', '-m', 'benchmark.serving.serving_job'], Path('benchmark/data').resolve()))"
```

## Data Fabric vs a traditional warehouse (Story 9.3, NFR-10)

**Result: on the demo's data the warehouse is faster and far smaller to build; the fabric is what makes the numbers
traceable, protected and refreshable by scope.** Choose the fabric for BR13–BR16 and the governance requirements,
not for speed.

### What was built

`warehouse_baseline` (Postgres 16.4, `benchmark` profile) is filled by `benchmark/warehouse/etl.py`: read the source
workbooks, drop and reload five staging tables, rebuild the BR01 and BR10 tables with the SQL in
`benchmark/warehouse/marts.sql`. There is no metadata, lineage, quality gate or access policy. BR16 is the same edit
the fabric's e2e test makes (`CMP19_05`, 2019-11-12, allocated spend 1,356.33 → 1,156.33): change the source value,
run the batch again. Each scenario ran 3 times in a fresh `--cpus=2 --memory=4g` container
(`benchmark/results/warehouse.csv`, rerun 2026-11-09 to add peak memory).

### Results

| | Traditional warehouse | Data Fabric |
|---|---|---|
| Data-layer code for BR01, BR10, BR16 | 93 lines (ETL + SQL) | about 1,180 lines: jobs 614, BR16 edit API / impact analysis / scoped writes / change log / DAG 401, contracts 165; plus the shared platform (`fabric_control`, `pipelines/io`) |
| Full batch | 1.7–1.8 s (load 1.7, SQL < 0.1) | full refresh target < 10 min (NFR-4); not measured on this machine |
| Reaction to the BR16 spend edit | 1.7–2.0 s, but only when someone reruns the batch; every table is rebuilt | partial refresh of the affected campaign's datasets only, < 2 min asserted by `tests/e2e/test_br16.py`; not measured on this machine |
| Correctness (§6 marks and BR16 deltas) | 7/7 checks pass before and after the edit | same marks enforced by DQ gates and reconcile tests |
| Can a number be traced to its source? | no: no lineage, glossary or definitions; only by reading SQL | yes: lineage in OpenMetadata, glossary terms and the Definition dialog on every metric |
| What changed after an edit? | not recorded; old values are overwritten | `ops.metric_change_log` with old → new per metric and event; Change History page |
| Unrelated metrics keep their refresh time | no: every table is recreated | yes: key-scoped writes leave other rows and `_refreshed_at` untouched (BR16 AC) |
| Bad data blocked before it reaches a page | no | critical DQ rules gate the write; pages show "Using previous version" |
| Column-level access (FR-20) | no: one login sees every column | policy views per role: UG03 cannot read SKU cost |
| Peak memory | ETL job 99–169 MiB; Postgres server at most 171 MiB over the six runs (cgroup `memory.peak`) | not measured; the core profile's `mem_limit` values sum to 11.5 GB with one `fabric-jobs` container |

The 7 checks: 1,290 attributed orders; online spend 695,646.47; allocated 98,569.53 → 98,369.53; unallocated
597,076.94 → 597,276.94; no day where allocated + unallocated ≠ online spend; the edited day's unallocated
2,034.49 → 2,234.49; CMP19_05 campaign cost 24,593.53 → 24,393.53. BR01 is checked on its total only; per-campaign
values were not compared with the fabric's mart.

### Limits

- The fabric's full and partial refresh times were not measured here: the full stack needs 12 GB and this machine
  gives Docker about 7.8 GB. The table cites the targets and the e2e assertion instead.
- 52,924 sales lines fit in memory several times over; the warehouse's full reload would grow with every source,
  while the fabric's scoped refresh grows with the size of the change.
- The warehouse has no UI; page code is excluded from both columns.

### Reproduce

```bash
python3 benchmark/warehouse/run.py   # starts postgres:16.4-alpine as bench-warehouse, writes results/warehouse.csv
```

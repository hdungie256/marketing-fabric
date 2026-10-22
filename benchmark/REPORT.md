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

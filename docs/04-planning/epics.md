---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - ../01-requirements/prd.md
  - ../03-architecture/ARCHITECTURE-SPINE.md
  - ../04-ux-design/DESIGN.md
  - ../04-ux-design/EXPERIENCE.md
---

# Marketing Data Fabric Demo - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Marketing Data Fabric Demo, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

**Definition of Done (applies to every story that adds a job, dataset or page):** the dataset is registered in `contracts/datasets.yml` (AD-18); serving tables are created by a numbered migration with PK = grain (AD-17) and every column is tagged in `governance/tags.yml` (AD-8 fail-closed); unified/mart jobs ship `dq/<dataset>.yml` and call `check()`/`gate()` before writing (AD-7); marts ship `mart.yml` (AD-6); metrics are declared in exactly one `governance/glossary/<slice>.yml` and rendered only via `shell.metric` (AD-16); code follows the 3-layer rule (AD-14); unit tests for transforms/services and, for BR stories, reconcile (written by a non-author) + e2e + `AppTest` smoke tests pass in `make test` (AD-21); pages render in < 3 s (NFR-4) and follow EXPERIENCE state patterns (loading, empty, error, stale, masked, denied).

## Requirements Inventory

### Functional Requirements

**F1 — Simulated Data Sources & Multi-Source Integration**

- FR-1: Build 7 simulated source systems (S1–S7, 8 source tables) from the sample Excel dataset with the correct interface type: Sales, CRM, Product/ERP as database; Campaign, Promotion, Advertising Cost as API; Finance Cost (part of S5), Tax as file.
- FR-2: Batch-load all three source types into the raw zone; the raw copy is never overwritten; each load is timestamped and versioned.
- FR-3: After each load, reconcile row counts/checksums between source and raw against the reconciliation marks (52,924 sales rows · 26,631 orders · 1,468 customers · 1,290 order–campaign links · online cost discrepancy 0) and display match/mismatch.
- FR-4: Distinguish original business tables from derived tables (e.g. cost reconciliation) to avoid loops and double counting.

**F2 — Unified Data & Quality**

- FR-5: Create a unified order key per R1 (`CustomerID` + `Transaction_ID`), keeping the original source code alongside.
- FR-6: Standardize date formats and category names per R13 using a mapping table lookup-able in the catalog.
- FR-7: Apply quality rules (completeness, uniqueness, validity, consistency) per table, each Critical or Warning; quality score = % rules passed; Green (100% critical pass and ≥ 90% all), Amber (100% critical pass, < 90% all), Red (any critical fails).
- FR-8: Generate an exception list per AC02: transaction codes shared across customers (1,319), sales lines not reconcilable with the coupon plan (400, 126 `Used`; unchanged by R13 normalization); R17 storage traits are not exceptions.
- FR-9: UG05 views, filters, and marks exception status (new / seen / accepted).

**F3 — Marketing Metric Catalog & Glossary**

- FR-10: Catalog lists every dataset (raw → unified → serving) with description, owner, source, last refresh, quality score, provenance label (original / synthetic).
- FR-11: Glossary defines every metric: English display name, definition, formula, source columns, related rules, interpretation limitations, owner, last refresh, quality score inherited via lineage. Canonical names: Attributed Gross Value, Attributed Orders, Average Order Value, Attributed Value / Spend Ratio (not "ROAS"), Cost per Attributed Order, Estimated Contribution, First Observed Buyers, RFM Segment.
- FR-12: From any dashboard metric, open its glossary definition in one action.
- FR-13: Keyword search across catalog and glossary.
- FR-14: Data columns carry classification labels (e.g. customer identifier, financial) used as inputs to access control.

**F4 — Lineage & Automatic Refresh**

- FR-15: For every serving metric/table, display a lineage graph source → processing steps → metric with timestamps and data versions.
- FR-16: When a cost item or campaign info changes at the source, identify affected datasets/metrics via lineage and refresh only that part; unrelated metrics keep values and refresh timestamps.
- FR-16a: UG04 can edit a campaign cost item by day in the simulated cost source; the change is versioned and triggers FR-16.
- FR-17: When a dataset's quality check fails at critical level, the downstream serving dataset is not updated and the dashboard warns "data is using the previous version".
- FR-18: Users can view before/after values of metrics affected by a source change.

**F5 — Access Control & Customer Data Protection**

- FR-19: Each group UG01–UG06 has a demo account; log in once, then switch roles instantly via a role selector.
- FR-20: View permissions are decided by policy at the platform layer from role and column labels, not just hidden in UI (UG04 sees SKU cost of goods; UG03 only aggregated contribution; UG01 no cost of goods; customer IDs masked for groups without need).
- FR-21: Customer contact export is disabled when consent data is missing (R12), with an explanatory notification.
- FR-22: UG05 can view the effective "role × dataset/column" matrix.

**F6 — Operational Monitoring**

- FR-23: Operations page shows status of each source and processing step: last run, duration, row count, success/failure.
- FR-24: UG06 triggers a reload of a source or the entire pipeline from the UI.
- FR-25: Load/processing errors generate in-app alerts with cause and failing step.
- FR-26: Measure and display end-to-end refresh time and analytics page response time.

**F7 — Campaign & Product Analysis**

- FR-27 (BR01): Campaign overview dashboard: orders, buying customers, attributed gross value, average order value; filter by period and campaign.
- FR-28 (BR02): Compare campaigns, channels, periods with the same metric definitions; 5 simulated campaigns.
- FR-29 (BR03): Rank best-selling SKUs/categories and trends over time; filterable by campaign.
- FR-30 (BR06): Separate first observed buyers (R9) and returning customers by campaign.
- FR-31 (BR12): Goal-achievement table per campaign against its own targets (R14): achievement = actual / target; Continue (≥ 100%), Adjust (70% – < 100%), Stop (< 70%); thresholds displayed; note that targets are retrospective synthetic.

**F8 — Customer Analysis**

- FR-32 (BR05): RFM segmentation as of 2019-12-31, frequency by technical order, quintile scoring and ordered segment rules per R18; distribution and customer list by segment.
- FR-33 (BR08): Build target customer groups by segment, purchased category, purchase history; save for planning; no contact export.
- FR-33a (BR09): List customers with (F = 5 or M = 5) and R = 1 as of the as-of date (R18); filterable by purchased category.

**F9 — Campaign Cost & Finance**

- FR-34 (BR10): Track budget, allocated cost, unallocated cost by day, Attributed Value / Spend Ratio, Cost per Attributed Order; no double counting (R8).
- FR-35 (BR11): Estimated contribution by campaign = attributed gross value − reference cost of goods − campaign cost; list items not yet available.

**Business rules bound to all FRs (PRD §6):** R1 order key · R2 gross value = SUM(Quantity × Avg_Price), not net revenue · R3 shipping once per order, separate · R4 GST not added · R5 as-of 2019-12-31 · R6 ≤ 1 campaign per order, attributed ≠ incremental · R7 not "ROAS" · R8 allocated + unallocated shown, budget ≠ cost · R9 first within observed history · R10 currency unit not verified · R11 contribution is an estimate · R12 no consent → no contact export · R13 only true synonyms normalized; Nest / Nest-USA / Nest-Canada separate · R14 targets retrospective synthetic · R15 CRM is current snapshot · R16 synthetic data labeled · R17 row-level storage conventions are not errors · R18 RFM quintile scoring 1–5 and ordered segment rules.

**Acceptance tests (PRD §8):** T-BR01, T-BR02, T-BR03, T-BR05, T-BR06, T-BR08, T-BR09, T-BR10, T-BR11, T-BR12, T-BR13, T-BR14, T-BR15, T-BR16.

### NonFunctional Requirements

- NFR-1: Runs locally — entire system built with a single `docker compose` command on a 16GB RAM machine (Docker/WSL2), no cloud.
- NFR-2: Resource budget — total RAM of concurrently running services ≤ ~12GB.
- NFR-3: Data correctness — every aggregate reconciles with detailed data per PRD §6; automated reconciliation test suite.
- NFR-4: Performance — measure and report; analytics page < 3 s; full refresh < 10 min; partial refresh after source change < 2 min.
- NFR-5: Benchmark per architecture layer (storage, processing, catalog/metadata, quality, serving) with ≥ 1 measured alternative and rationale; processing: Spark vs Flink on the same ETL job (unified orders + RFM) at ×1, ×10, ×100; alternative runs only during benchmarking.
- NFR-6: Reproducible — re-running the load pipeline gives the same result; sources re-initializable from the sample Excel.
- NFR-7: End-to-end testing — automated suite from source → unified → displayed metric for each BR.
- NFR-8: Ease of use — visual, clear UI; first-time user finds their role's metrics without guidance; UI language English.
- NFR-9: Demo-level security — access enforced at platform layer; demo credentials not hard-coded in public source.
- NFR-10: Full alternative solution — compare Data Fabric vs traditional warehouse (ETL → one DB → dashboard, no governance) on at least BR01, BR10, BR16: build effort, traceability, response time to source change, data correctness.

**Success metrics:** SM1 100% committed BRs pass · SM2 e2e suite all green · SM3 100% reconciliation · SM4 7/7 fabric capabilities in acceptance scenarios · SM5 builds on 16GB with documented procedure, no manual fixes.

### Additional Requirements

**Starter / greenfield:** No starter template. Greenfield repo `marketing-fabric/` with the Structural Seed directory tree and owners (P1–P4); Epic 1 Story 1 must scaffold the repo, compose profiles, `.env.example`, and the `fabric_control` stub.

**Infrastructure & deployment**
- `docker compose` profiles: `core` (full demo, default), `dev` (PG, SeaweedFS, Streamlit; jobs manual; `FABRIC_CONTROL_MODE=offline`; fixtures from `contracts/fixtures/<dataset_id>.parquet`), `benchmark` (Flink, Soda, pinned MinIO, traditional warehouse) (AD-15).
- `mem_limit` per `core` service totaling ≤ 12GB: OM server 2GB, Elasticsearch 1.5GB (heap 1GB), PostgreSQL 1GB, OM ingestion/Airflow 2GB, SeaweedFS 0.5GB, mock-api 0.25GB, Streamlit 0.5GB, fabric-jobs 3GB (1 writing container at a time, driver.memory=2g); `.wslconfig` memory=14GB (AD-15).
- One-shot idempotent `bootstrap` service (fabric-jobs image, `depends_on: service_healthy`): PG init → seed sources from xlsx → fetch OM bot token to secret volume → register OM services → migrations → `sync_tags` → `sync_glossary` → `full_refresh` → `sync_policies` → `verify_policies`; `docker compose up` is done when bootstrap exits 0; `make reset` deletes volumes and reruns (AD-20).
- Named volumes for PG, SeaweedFS, ES (AD-20).
- Stack pins: OM 2.0.2 (server/ingestion/postgresql = PG 15), Airflow 3.3.1 in OM ingestion image (REST `/api/v2` + JWT, providers-docker 4.5.9), Elasticsearch 9.3.0, Spark/PySpark 3.5.9 (Scala 2.12), Delta 3.3.3, hadoop-aws 3.3.4 / aws-java-sdk-bundle 1.12.262, PG JDBC 42.7.x, OpenLineage 1.53.0, GX Core 1.23.2 (numpy<2), SeaweedFS 4.47, Python 3.11, Java 17, Streamlit 1.64.0, FastAPI 0.141.1, psycopg 3.3.6.

**Data plane & storage**
- One-directional medallion flow: source → `raw` → `unified` → `mart_*` → `*_v` views → app; no layer skipping; Streamlit never reads SeaweedFS, source DBs, or underlying mart tables (AD-1).
- Storage only via S3 API (`s3a://` path-style, boto3); SeaweedFS ↔ MinIO is config-only (AD-9).
- `raw` and `unified` are Delta tables; `raw` append-only with `_load_id`, `_ingested_at`, `_source`, `_load_kind`, `_source_version`; `source_version` monotonically increasing per source (API on every PUT, DB/files on every seed) (AD-9).
- Load reconciliation vs `governance/baselines.yml` into `ops.load_reconciliation`; failed loads are never used; `io.read_raw` reads latest version per natural key from passed loads only (AD-9).
- Mart `_source_version` jsonb `{dataset_id: source_version}`; full rerun with same versions must be deterministic for non-`_` columns (AD-9, NFR-6).
- Category mapping in `governance/mappings/*.yml`, materialized as `unified/ref_<name>` with lineage (AD-9).
- PostgreSQL: one server (OM image), 4 DBs (`openmetadata_db`, `airflow_db`, `sources`, `serving`); `serving` schemas `mart_campaign`, `mart_customer`, `mart_finance`, `mart_shared`, `app`, `ops` + generated `*_v` schemas; `warehouse_baseline` only in benchmark (AD-10).
- Serving DDL only via numbered migrations `migrations/<schema>/NNN_*.sql` (PK = grain); jobs write only via `pipelines/io` (`write_pg_full` = TRUNCATE+INSERT in one tx; `upsert_pg` scoped); no DDL / JDBC overwrite in jobs; `sync_policies()` after every migration run and end of `full_refresh` (AD-17).
- One writer per dataset declared in `contracts/datasets.yml`; Airflow pool `fabric_writes` slots=1, `max_active_runs=1`; `Spend_Recon` at source never read as fact, recomputed in `mart_shared.spend_reconciliation` (AD-4, FR-4).
- Slices never read each other's marts; shared metrics computed once in `mart_shared` (`campaign_attributed_daily`, `campaign_spend_allocated`, `spend_reconciliation`, `exceptions`) and `unified/product_cost`; `contracts/shared_metrics.yml`; `unified` + `mart_shared` schemas published in `contracts/` before code; changes via PR approved by owner + consumers (AD-11).

**Control plane & metadata**
- OpenMetadata 2.0.2 is the metadata system of record (catalog, glossary, tags, lineage, DQ); OM UI admin-only; users see metadata in Streamlit via `fabric_control` read functions (AD-2).
- Metadata writes: Spark OpenLineage → `POST /api/v1/openlineage/lineage`; non-Spark lineage and Delta registration fallback via `fabric_control.emit_lineage` / `register`; glossary/tags/mappings via `fabric_control.sync_*` from `governance/` (AD-2).
- `Provenance.Synthetic` set at raw from source `Provenance` column and propagated through lineage by `sync_glossary()` (AD-2, R16).
- `fabric_control` is the sole API to OM/Airflow/PG admin; stub with exact signatures committed in week 1: `run`, `Run.record_change`, `check`, `score`, `report_dq`, `gate`, `affected_by`, `status`, `sync_policies`, `verify_policies`, `can_export`, `sync_glossary`, `sync_tags`, `emit_lineage`, `register`, `catalog`, `search`, `term`, `lineage`, `latest_score`, `effective_matrix`, `trigger`, `record_timing`; offline mode for dev (AD-3).
- Identity registry `contracts/datasets.yml` (`dataset_id`, `om_fqn`, `openlineage{namespace,name}`, `job_id`, `owner`, `tags`); `dataset_id` shapes `raw/<source>/<table>` · `unified/<entity>` · `mart_<subject>.<table>`; `job_id` = job dir path = DAG task id; `run_id` = `<dag_run_id>:<job_id>` in `_run_id`; CI checks job outputs exist in registry (AD-18).
- Glossary as code: one OM glossary `marketing_metrics`; term ID = snake_case of display name with `/` → `_per_`; fields display_name, owner_slice, dataset_id, column, rules, limitations, notes (`currency_unverified | retrospective_target | estimate_not_profit | attributed_not_incremental | first_in_observed_history`); declared once in `governance/glossary/<slice>.yml`; `sync_glossary()` fails on duplicate IDs/display names (AD-16).

**Orchestration & refresh**
- Airflow 3.3.1 in OM ingestion image is the only orchestrator; DAGs in `pipelines/dags` import only Airflow SDK; 3 DAGs: `full_refresh`, `partial_refresh`, `reload_source`; tasks run `fabric-jobs` image via DockerOperator (`spark-submit --master local[*]`, auto-remove); docker.sock mounted with `group_add`; all jars baked into image, no `--packages`, no `openmetadata-ingestion` in fabric-jobs (AD-12).
- `partial_refresh` first task runs `affected_by(event)` in fabric-jobs, returns via XCom, dynamic task mapping generates ordered job tasks (AD-12).
- Business changes only via mock API `PUT` (UG04 only per `access_matrix.yml`); source invariants (0 ≤ allocation ≤ day's online spend, date within campaign period) → 4xx with reason; success increments `source_version` and calls `trigger("partial_refresh", event)`; event `{event_id, emitted_at, source, keys, source_version}`; no other path triggers partial refresh (AD-5).
- Key-scoped refresh contract: each mart has `mart.yml` (`table`, `grain`, `modes`, `scope_map`, `metrics`); scope `{"mode":"full"}` or `{"mode":"scope","keys":{...}}` passed via `--scope` and logged in `ops.runs.scope`; `affected_by` reads only OM lineage + manifests, topological order with scope projected per grain; scoped write recomputes all matching grain rows and replaces in one tx (`upsert_pg` DELETE+INSERT; Delta `replace_where`); `upsert_pg` returns (before, after) `FOR UPDATE`; `run.record_change` → `ops.metric_change_log(run_id, event_id, dataset_id, grain_key, term_id, old_value, new_value)` (AD-6).
- Freshness per displayed value = `max(_refreshed_at)` of producing rows; `_refreshed_at` changes only on rewrite; stale = last run `gated` or stale ancestor, answered only by `status()` (cached per DAG run); DAG skips descendants of blocked dataset (AD-19).

**Data quality**
- Every job writing `unified`/`mart` runs `check()` (GX Core, rules in `dq/<dataset>.yml` with `rule_id`, `expectation`, `severity`) before write; in scope mode, table-level rules run on post-merge image; `score()` per FR-7; `report_dq()` writes `ops.dq_results` (UI source) and pushes to OM test cases (FQN `<om_fqn>.<rule_id>`) without blocking on OM failure; critical `gate()` failure stops write; GX `OpenMetadataValidationAction` not used (AD-7).
- Exceptions: each detecting job writes `unified/exceptions_<class>` per `contracts/exceptions.yml`; `exception_id = sha1(class|natural_key)` stable; `mart_shared.exceptions` merges; `app.exception_status` keyed by `exception_id`; vanished ID → "resolved at source" (AD-7).

**Security & policy**
- Per-group PG logins (creds in `.env`); role switcher swaps connections (no `SET ROLE`); underlying `mart_*`/`app`/`ops` tables never granted; `sync_policies()` generates one `<schema>_v.<table>` view per exposed table (same column names); repositories query only `*_v` with explicit column lists (AD-8).
- `tags.yml` actions per tag × role: `allow`, `mask:<fn>` (closed list; guest id `mask:partial` → `C****42`), `deny` (NULL + `<col>__denied` flag); no privilege → PG `permission denied`; fail-closed if any serving column is untagged; generated objects prefixed `policy_` with comment `generated-by sync_policies` (AD-8).
- `verify_policies()` cross-checks `ops.policy_effective` against `has_column_privilege` and actual view output; FR-22 matrix reads `ops.policy_effective`; `app.segments`, `ops.metric_change_log` tagged too; `can_export()` returns False without consent metadata; no contact-export view ever granted (AD-8).
- Config/secrets only via env / `.env`; commit `.env.example`; no hard-coding (NFR-9).

**Operations & monitoring**
- Every job runs in `with fabric_control.run(job_id, scope) as run:` writing `ops.runs` (run_id, job_id, event_id, scope, start/end, rows in/out, status success|failed|gated, failing step, Delta version); errors → `ops.alerts` then re-raise; partial-refresh latency = `max(ended_at) − emitted_at` per event; page timing via `record_timing()` → `ops.page_timings` (`ops_writer` inside the library); ops page reads only `ops_v`; reload via `trigger()` (AD-13).
- Fault toggles for BR15 in `sources/` via `make break-source SRC=<source>` (no in-app break button).

**Code structure**
- 3 layers in every unit: presentation (`app/pages`, `mock_api/routers`, `jobs/*/job.py`) → business (`app/services`, `mock_api/services`, `transforms.py`, `fabric_control/decisions`) → data access (`app/repositories`, `mock_api/repositories`, `pipelines/io`, `fabric_control/clients`); transforms are pure DataFrame → DataFrame; only `job.py` assembles io + fabric_control (AD-14).
- Conventions: English snake_case; `order_key = customer_id || '|' || transaction_id`; `AS_OF_DATE = 2019-12-31` in `contracts/constants.yml`; `unified/orders` holds `gross_value` and `shipping_fee`; `unified/customers` holds `first_observed_order_date`; mart metadata columns `_refreshed_at`, `_run_id`, `_source_version`; DATE ISO-8601; money NUMERIC(18,2) without currency label.

**Testing (AD-21)**
- Conflict-free ownership: shared registries split into per-owner fragments (`contracts/datasets/<slice>.yml`, `governance/glossary/<slice>.yml`, `governance/tags/<slice>.yml`, `app/pages/<slice>/registry.py`); migration numbers reserved per owner in multi-owner schemas (P1 001–099, P2 100–199, P3 200–299, P4 300–399); co-owner parts delivered as separate PRs against published contracts/stubs.
- Unit tests (`tests/unit`) for transforms and services against fixtures, by code owner.
- Reconcile tests (`tests/reconcile/test_br<nn>.py`): independent SQL on `unified` vs `*_v` values, no mart code import, written by someone other than the mart author, hard-assert 52,924 · 26,631 · 1,468 · 1,290 · 0 · 1,319 · 400/126, ignore `_` columns.
- E2e tests (`tests/e2e/test_br<nn>.py`, or `test_br<nn>_<area>.py` when a BR spans multiple owners) by the owning slice against the `core` stack after bootstrap, via `app/services`, plus one Streamlit `AppTest` smoke test per page; e2e fails if any `term_id` is unknown.
- Single `make test` (P1), green before merge to `main`.

**Week-1 blocking spikes**
- S1: OM 2.0.2 indexes Delta on SeaweedFS via Delta connector (storage mode) in stock ingestion image; fallback `register()` via REST.
- S2: OpenLineage 1.53.0 Spark events (Delta on s3a, JDBC to PG) map to OM entities by registry `om_fqn`; fallback `emit_lineage()`.
- S3: Spark s3a + Delta 3.3.3 on SeaweedFS (static keys, path-style, http): write, overwrite, replaceWhere, time travel, VACUUM; fallback pinned MinIO.
- S4: `core` RAM ≤ 12GB during a job; partial_refresh end-to-end < 2 min; fallback chain scoped jobs in one container/SparkSession.
- S5: DAG from `pipelines/dags` runs DockerOperator (docker.sock, `group_add`, `mount_tmp_dir=False`) and reads XCom; mock API triggers DAG via `/api/v2` JWT.
- S6: bootstrap fetches OM bot token automatically; `report_dq()` creates a test case and pushes results on a registered Delta table.

**Team & ownership (rebalanced 2026-09-29 for conflict-free parallel work):** 4 members. P1 owns the platform (`compose`, `contracts`, `fabric_control`, `mock_api`, governance mappings, DAGs, IO, ingest, `mart_shared.exceptions`). P2 owns campaign unified jobs and marts, `mart_shared.campaign_attributed_daily`, `app/shell`, campaign/change-history pages, and demo readiness. P3 owns source seeds, unified sales/customer/product jobs, customer/catalog marts and pages, plus the DQ & Exceptions page. P4 owns `unified/campaign_spend`, finance and shared spend marts, governance standards/tags/access/baselines, policy/access and ops pages, and benchmark work. Story leads coordinate cross-owner work through published contracts and separate PRs; they do not take over another owner's directory. Project duration ~1 month.

### UX Design Requirements

**Theme & tokens**
- UX-DR1: `.streamlit/config.toml` theme: base light; primaryColor `#2F5BEA`; backgroundColor `#F6F7F9`; secondaryBackgroundColor `#EEF0F3`; textColor `#1A1F29`; borderColor/dataframeBorderColor `#E4E7EC`; green/orange/red/blue/grayColor = success `#146C2E` / warning `#92400E` / danger `#99180C` / accent / muted `#5B6472`; chartCategoricalColors series-1..5 (`#2a78d6`, `#d95926`, `#1baf7a`, `#4a3aa7`, `#eda100`); chartSequentialColors (`#E8EEFE`, `#7D9AF2`, `#1F3FAE`); system sans + mono fonts; baseFontSize 16; baseRadius/buttonRadius 8px; sidebar bg `#FBFBFC`. Light mode only.
- UX-DR2: Single shell CSS layer in `app/shell` only (no per-page CSS or `unsafe_allow_html` styling in pages): card surface, 12px card radius, single soft shadow, 40px/700 KPI numerals, badge pills, warning-border for stale, accent-tint/accent-strong nav state, info-icon bg, sidebar width 244px, lineage node styling.
- UX-DR3: Typography floor: body ≥ 15px (16px), nothing < 14px; page-title 28/700, section-title 19/700, label 15/600, table-header 14/600 (uppercase allowed), badge 14/700, masked value mono 16/600; tabular right-aligned numbers; metric labels use glossary `display_name` verbatim, never uppercase-transformed.
- UX-DR4: Fixed campaign color by slot CMP-01..05 → series-1..5 on every page, never re-ordered by rank; status colors never used as chart series; `series-neutral #848B97` only for unallocated/non-entity.

**Shell & navigation**
- UX-DR5: Login once (inline "Invalid demo credentials" on failure, no role hint); sidebar: app name + "CO5173 · Academic demo" → role-switcher ("Role (demo mode)", caption "Signed in as UGxx · nav filtered to this role") → alert-indicator → nav groups.
- UX-DR6: Role-filtered navigation via `st.navigation` for 16 pages in 5 groups (Campaigns, Customers, Finance, Data trust, Operations) per the EXPERIENCE role × page matrix; hidden pages not in nav and unreachable by URL; no shown-locked items.
- UX-DR7: Role homes: UG01 Campaign Overview, UG02 RFM Segments, UG03 Targets, UG04 Budget & Spend, UG05 Data Quality & Exceptions, UG06 Pipeline Status; land on home after login; on role switch stay on page if permitted else redirect to home with toast "Switched to <Role> (UGxx)"; switch swaps PG connection.
- UX-DR8: Page anatomy: title + right-aligned "Viewing as: <Role> (UGxx)" → optional banner → filter-bar → KPI row (≤ 4 cards, one line at 1366×768) → content grid (chart ~1.3fr + table ~1fr or full-width) → footnote strip; `layout="wide"`.
- UX-DR9: Alert-indicator (bell + count, danger tint) visible only to UG05 (DQ failures) and UG06 (pipeline failures), hidden at 0; click → Pipeline Status filtered to failed runs (UG06) or DQ & Exceptions filtered to failures (UG05).
- UX-DR10: Shell captures page render time and calls `record_timing()` for every page; each page < 3 s.

**Components**
- UX-DR11: `shell.metric(term_id, value, freshness)` metric-card — the only rendering path for metrics: label + ⓘ button, KPI value, badge row (fresh / refreshing / stale / synthetic); stale variant = warning border + warning value color; refreshing variant keeps previous value; notes from term; `currency_unverified` collected once into the footnote strip; unknown term_id fails e2e.
- UX-DR12: Badges with icon + text: fresh "Refreshed HH:MM" (check_circle), refreshing "Refreshing…" (sync), stale "Using previous version" (warning), synthetic "Synthetic" (science), masked mono value `C****42` + lock, denied italic muted "not permitted for role" + lock (never red).
- UX-DR13: Status-chip variants: success (run success · DQ Green · Continue), warning (DQ Amber · Adjust · gated), danger (failed · DQ Red · Stop), info (running), neutral (queued · exception new/seen/accepted · resolved at source).
- UX-DR14: Definition dialog (`st.dialog` large) opened from ⓘ on metric cards, metric column headers, change-history rows and catalog term results: title in accent; tabs Definition (display name, definition, formula, source columns as inline code, rules, limitations, owner, synthetic, cautions e.g. "Not ROAS" as danger chip) · Lineage (lineage-graph) · Quality (score + status chip, last refresh); one modal level; Esc returns with filters intact.
- UX-DR15: Lineage-graph component: left-to-right DAG source → raw → unified → mart → metric; rounded nodes with dataset id + refreshed time + version; stale nodes warning border + ⚠; click node → side detail (id, refreshed, version, quality); read via `fabric_control`.
- UX-DR16: Table: `st.dataframe` themed; numeric right-aligned tabular; campaign cells name + muted `CMP-0x`; selected row accent-tint; sortable; metric headers with ⓘ; masked/denied cells rendered via badges (`__denied` flag and PG permission error both → "not permitted for role").
- UX-DR17: Chart: titled, labeled axes, legend, hover tooltip, direct labels (≤ 4 series), "Table view" toggle on every chart; thin marks, border-colored grid; no dual axis; aqua/yellow series always direct-labeled or table-backed.
- UX-DR18: Spend-stack-bar: daily stacked bar Allocated (accent) + Unallocated (series-neutral) with 2px surface gap, legend + direct labels, table-view toggle.
- UX-DR19: Filter-bar: Period + Campaign (+ page-specific); applies on change (no Apply); filters persist per page in session including across role switch.
- UX-DR20: Banners: banner-stale (one per page, lists all stale datasets, "Using previous version — quality check failed on `<dataset>`", disappears when gated dataset is written) and banner-error (cause, never swallowed); 4px left rule + icon.
- UX-DR21: Footnote-strip at page bottom holding the single "currency unverified" note (R10) and page interpretation notes.
- UX-DR22: Buttons: primary/secondary with verb labels ("Save change", "Reload source", "Save audience", "Mark accepted"); disabled = sunken fill + lock + reason text visible beneath (never tooltip-only).
- UX-DR23: Form-field: label above; accent focus ring; error = danger border + message beneath in caption size; values kept on error.
- UX-DR24: Skeleton loading shaped like final card/table/chart; no centered spinners anywhere.
- UX-DR25: Toast (`st.toast`) with status icon for save, role switch, reload; never the only place an error is shown.

**Page composites**
- UX-DR26: Spend edit form (Budget & Spend, UG04 only): `st.form` campaign/date/allocated value; Save → mock API; "Saving…" while submitting; 4xx reason inline under field; success toast "Change saved · partial refresh started"; not rendered for UG03 (read-only table).
- UX-DR27: Progress-strip below spend form after save: "Refreshing N datasets · m:ss", per-dataset steps queued → running → done with elapsed timer; affected metric cards on Budget & Spend / Contribution / Targets show refreshing badge then flip to fresh independently; on completion "N metrics changed — see Change History".
- UX-DR28: Audience builder: criteria RFM segment + purchased category + purchase history; live match count; "Save audience"; "Export contacts" always disabled with "Contact export disabled — no marketing consent data (R12)"; customer IDs masked per role; zero-match state "No customers match these criteria." + widen hint.
- UX-DR29: Win-back list: high F/M, low R at 2019-12-31; category filter; "Build audience from this list" prefills Audience Builder; zero-match "No lapsed high-value customers for this filter."
- UX-DR30: Exceptions triage: filter by class and status; status chips new/seen/accepted; row multi-select + "Mark seen" / "Mark accepted"; keyed by `exception_id`; vanished IDs show "resolved at source" (still visible under status filter); R17 traits never listed.
- UX-DR31: DQ scoreboard: per dataset score %, Green/Amber/Red chip failing rules with Critical/Warning severity.
- UX-DR32: Access matrix: read-only role × dataset/column grid from `ops.policy_effective`; cells status-chip allow (success) / mask (warning) / deny (neutral) with icon + word.
- UX-DR33: Pipeline status: per source and step last run, duration, rows in/out, status chip queued → running → success/failed/gated, failing step + cause; auto-refresh every 5 s via `st.fragment(run_every=5)` only while a run is active; `?event_id=` deep link with elapsed timer vs "2 min target" and "Over 2 min target" warning chip; "Reload source" / "Reload all" with one confirm; shows end-to-end, partial refresh and page response times.
- UX-DR34: Change history: per event metric, campaign, old → new, delta; row ⓘ opens definition dialog; summary "N metrics changed · M unchanged kept refresh time HH:MM"; `?event_id=` filter; empty "No source changes recorded yet."
- UX-DR35: Catalog search: keyword across datasets and terms; results show provenance, owner, last refresh, quality; selecting a term opens definition dialog; zero-match "No datasets or terms match '<q>'."

**Voice, format, accessibility**
- UX-DR36: Voice: short neutral English; canonical metric names (Attributed Gross Value, Attributed Orders, Attributed Buyers, Average Order Value, Attributed Value / Spend Ratio, Cost per Attributed Order, Campaign Budget, Allocated Spend, Unallocated Spend, Estimated Contribution, First Observed Buyers, RFM Segment); banned terms "Revenue", "Sales", "ROAS", "Access denied!", "Success! 🎉", "OK/Submit/Go"; every block/disable message states its reason.
- UX-DR37: Number/date formats: counts/money thousands separator, no currency symbol; ratios 2 decimals + × (3.42×); percents 1 decimal; ISO dates; freshness 24h HH:MM.
- UX-DR38: Empty state pattern: explanatory sentence + clear-filter hint (e.g. "No attributed orders for CMP-03 in this period. Clear the Campaign filter to see all.").
- UX-DR39: Accessibility floor: WCAG AA text contrast; status never color-only (icon + text); full keyboard operability, Tab order = reading order, visible accent focus ring, Esc closes dialog; disabled controls state reason in visible text; no hover-only information.
- UX-DR40: Platform: desktop web, 1366×768 projector baseline, larger desktop same layout; mobile out of scope; browser zoom 100%.
- UX-DR41: Deep links via query params `?event_id=` on Pipeline Status and Change History; no auto-refresh anywhere except Pipeline Status during an active run.
- UX-DR42: Demo script support (~15 min, 8 steps) and pre-demo state: full refresh done, all badges fresh, alert count 0, fault toggle off.

### FR Coverage Map

| FR | Epic | Summary |
|---|---|---|
| FR-1 | Epic 1 | 7 simulated sources (DB/API/file) seeded from xlsx |
| FR-2 | Epic 1 | Append-only, versioned batch loads into raw |
| FR-3 | Epic 1 | Load reconciliation vs baselines, match/mismatch shown |
| FR-4 | Epic 1 | Derived `Spend_Recon` never read as fact; `mart_shared.spend_reconciliation` |
| FR-5 | Epic 1 | Unified order key R1 |
| FR-6 | Epic 1 | Date + category standardization via mapping (R13) |
| FR-7 | Epic 3 | DQ rules, score, Green/Amber/Red |
| FR-8 | Epic 3 | Exception list (1,319 shared transaction codes, coupon mismatches) |
| FR-9 | Epic 3 | Exception triage status by UG05 |
| FR-10 | Epic 2 | Dataset catalog with provenance, owner, refresh, quality |
| FR-11 | Epic 2 | Glossary terms with full fields |
| FR-12 | Epic 2 | One-action definition dialog from any metric |
| FR-13 | Epic 2 | Keyword search across catalog + glossary |
| FR-14 | Epic 3 | Column classification tags drive policy |
| FR-15 | Epic 2 | Lineage graph with timestamps and versions |
| FR-16 | Epic 8 | Lineage-driven, key-scoped partial refresh |
| FR-16a | Epic 8 | UG04 edits daily campaign spend via mock API |
| FR-17 | Epic 3 | Critical DQ failure gates write; stale banner/badges |
| FR-18 | Epic 8 | Change History before/after values |
| FR-19 | Epic 1 | Demo login + instant role switcher |
| FR-20 | Epic 3 | Tag-based allow/mask/deny enforced in Postgres (foundation views in Epic 1) |
| FR-21 | Epic 5 | Contact export disabled via `can_export()` (R12) |
| FR-22 | Epic 3 | Effective access matrix |
| FR-23 | Epic 7 | Pipeline status per source/step |
| FR-24 | Epic 7 | Reload source / all from UI |
| FR-25 | Epic 7 | In-app alerts with cause + failing step |
| FR-26 | Epic 7 | Refresh times + page response times |
| FR-27 | Epic 1 | Campaign Overview dashboard (BR01) |
| FR-28 | Epic 4 | Campaign/channel/period comparison (BR02) |
| FR-29 | Epic 4 | SKU/category ranking + trends (BR03) |
| FR-30 | Epic 4 | First observed vs returning buyers (BR06) |
| FR-31 | Epic 4 | Targets achievement + Continue/Adjust/Stop (BR12) |
| FR-32 | Epic 5 | RFM segmentation at 2019-12-31 (BR05) |
| FR-33 | Epic 5 | Audience Builder, save for planning (BR08) |
| FR-33a | Epic 5 | Win-back list (BR09) |
| FR-34 | Epic 6 | Budget, allocated/unallocated spend, ratios (BR10) |
| FR-35 | Epic 6 | Estimated contribution + missing items (BR11) |

**NFR coverage:** NFR-1, NFR-2, NFR-6 → Epic 1 · NFR-9 → Epic 1 (secrets, per-role logins) + Epic 3 (policy) · NFR-3, NFR-7 → reconcile/e2e stories inside the epic owning each BR (harness in Epic 1) · NFR-4 → Epic 7 (measurement), Epic 8 (partial refresh < 2 min), Epic 9 (report) · NFR-5, NFR-10 → Epic 9 · NFR-8 → UX-DRs across all UI epics.

**UX-DR coverage:** UX-DR1–8, 10, 11–13, 16, 19, 21, 24, 25, 36–40 → Epic 1 · UX-DR14, 15, 35 → Epic 2 · UX-DR11/12 stale variant, 20, 30–32 → Epic 3 · UX-DR17 → Epic 4 · UX-DR22, 28, 29 → Epic 5 · UX-DR18 → Epic 6 · UX-DR9, 33, 41 → Epic 7 · UX-DR23, 26, 27, 34 → Epic 8 · UX-DR42 → Epic 9.

## Epic List

### Epic 1: One-command demo with Campaign Overview end-to-end
Anyone on the team runs one `docker compose up` on a 16GB machine and gets the full stack: 7 simulated sources (DB/API/file) seeded, loaded into an append-only raw zone with reconciliation against the §6 marks, unified into shared entities and shared marts, served through per-role `*_v` views. Every demo role logs in and switches roles; UG01 opens Campaign Overview and sees the four BR01 KPIs rendered through `shell.metric` with freshness and synthetic badges. Includes week-1 spikes S1–S6, contracts, the `fabric_control` stub, the test harness, and the Clean SaaS theme/shell.
**FRs covered:** FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-19, FR-27

### Epic 2: Understand & trace every metric
Every role opens the ⓘ on any metric and gets its definition, lineage and quality in one dialog; browses and searches the Catalog & Glossary; follows any dataset on the Lineage page from source to metric with times and versions. Synthetic provenance propagates through lineage automatically.
**FRs covered:** FR-10, FR-11, FR-12, FR-13, FR-15

### Epic 3: Trustworthy & protected data (quality gate + policy)
UG05 sees per-dataset quality scores (Green/Amber/Red), triages the exception list (1,319 shared transaction codes) and inspects the effective access matrix. A critical quality failure blocks the downstream write and pages show "Using previous version". Column tags drive allow/mask/deny enforced inside Postgres, fail-closed.
**FRs covered:** FR-7, FR-8, FR-9, FR-14, FR-17, FR-20, FR-22

### Epic 4: Campaign performance & stop/keep decisions
UG01 and UG03 compare campaigns, channels and periods with shared definitions, rank SKUs/categories (Nest, Nest-USA, Nest-Canada separate), split first observed vs returning buyers, and UG03 decides Continue/Adjust/Stop per campaign against its own retrospective target.
**FRs covered:** FR-28, FR-29, FR-30, FR-31

### Epic 5: Customer segments & win-back audiences
UG02 views RFM segments as of 2019-12-31, finds lapsed high-value customers, builds and saves target audiences for planning, and sees contact export locked with the R12 consent reason; customer IDs are masked per role.
**FRs covered:** FR-32, FR-33, FR-33a, FR-21

### Epic 6: Campaign spend & financial contribution
UG04 and UG03 track budget vs allocated/unallocated daily spend (difference 0), Attributed Value / Spend Ratio and Cost per Attributed Order, and estimated contribution by campaign; UG04 sees SKU reference cost while UG03 sees only the aggregate.
**FRs covered:** FR-34, FR-35

### Epic 7: Pipeline operations & alerts
UG06 monitors every source and processing step, receives in-app alerts naming the failing step and cause, reloads a source or the whole pipeline from the UI, and sees end-to-end refresh and page response times.
**FRs covered:** FR-23, FR-24, FR-25, FR-26

### Epic 8: Change-driven partial refresh (demo climax)
UG04 corrects one day's spend for a campaign; within < 2 minutes only that campaign's BR10/BR11/BR12 metrics refresh (others keep their refresh time), the UI shows progress and Refreshing badges, and Change History shows old → new values.
**FRs covered:** FR-16, FR-16a, FR-18

### Epic 9: Architecture evidence: benchmarks & warehouse comparison
The team presents measured evidence for every architecture layer (Spark vs Flink at ×1/×10/×100 plus storage, catalog, quality, serving alternatives), a Data Fabric vs traditional warehouse comparison on BR01/BR10/BR16, and the NFR-4 performance report, plus a rehearsed demo readiness checklist.
**FRs covered:** none directly (NFR-4, NFR-5, NFR-10)

## Epic 1: One-command demo with Campaign Overview end-to-end

Anyone on the team runs one `docker compose up` on a 16GB machine and gets the full stack: 7 simulated sources seeded, loaded into an append-only raw zone with reconciliation, unified into shared entities and shared marts, served through per-role `*_v` views. Every demo role logs in and switches roles; UG01 opens Campaign Overview and sees the four BR01 KPIs rendered through `shell.metric`.

### Story 1.1: Repository scaffold, compose profiles and fabric_control stub

As a team member (P1–P4),
I want a greenfield repository with the agreed directory tree, compose profiles, contracts skeleton and a `fabric_control` stub with the final signatures,
So that all four of us can start slice work in parallel on day 1 without waiting for the platform.

**Acceptance Criteria:**

**Given** a fresh clone of `marketing-fabric/`
**When** I list the repository
**Then** it contains the Structural Seed tree (`compose/`, `migrations/`, `contracts/`, `governance/`, `fabric_control/`, `mock_api/`, `sources/`, `pipelines/{dags,io,jobs}`, `app/{shell,pages,services,repositories}`, `tests/{unit,reconcile,e2e}`, `benchmark/`) with a CODEOWNERS-style ownership note per directory
**And** `compose/docker-compose.yml` defines profiles `core`, `dev` and `benchmark` with every `core` service carrying the AD-15 `mem_limit` (total ≤ 12GB) and pinned image versions from the Stack table
**And** `.env.example` lists every credential/endpoint variable with placeholder values and `.env` is git-ignored (NFR-9)

**Given** the `fabric_control` package
**When** I import it
**Then** every function in the AD-3 table exists with its exact signature (`run`, `Run.record_change`, `check`, `score`, `report_dq`, `gate`, `affected_by`, `status`, `sync_policies`, `verify_policies`, `can_export`, `sync_glossary`, `sync_tags`, `emit_lineage`, `register`, `catalog`, `search`, `term`, `lineage`, `latest_score`, `effective_matrix`, `trigger`, `record_timing`)
**And** with `FABRIC_CONTROL_MODE=offline` every OM/Airflow call is a no-op that logs locally, and `score()` is already a pure function implementing FR-7 thresholds with unit tests

**Given** the `contracts/` folder
**When** I open it
**Then** `constants.yml` declares `AS_OF_DATE: 2019-12-31`, the registry exists as per-owner fragments `contracts/datasets/{platform,campaign,customer,finance}.yml` with the AD-18 field schema (a loader merges them and fails on duplicate `dataset_id`), and `shared_metrics.yml` / `exceptions.yml` exist as schemas
**And** empty per-owner fragment files exist for `governance/glossary/<slice>.yml`, `governance/tags/<slice>.yml` and `app/pages/<slice>/registry.py`, and each migration folder of a multi-owner schema has a README stating the reserved number ranges (P1 001–099, P2 100–199, P3 200–299, P4 300–399)
**And** `make test` runs the unit, reconcile and e2e suites (empty suites pass) and a CI check fails if a `job.py` declares an output missing from `datasets.yml`

### Story 1.2: Storage and lineage spikes (S1, S2, S3)

As the platform owner (P1),
I want to prove Spark + Delta on SeaweedFS and the OpenMetadata Delta/OpenLineage integration with a throwaway job,
So that we lock the storage and metadata path (or switch to the documented fallback) before any slice depends on it.

**Acceptance Criteria:**

**Given** the `core` services SeaweedFS, OM server, OM ingestion and PostgreSQL are up
**When** a spike Spark job writes a Delta table to `s3a://` (static keys, path-style, http endpoint)
**Then** write, overwrite, `replaceWhere`, time travel and VACUUM all succeed (S3), otherwise the pinned MinIO fallback is applied as a config-only change
**And** OM 2.0.2 indexes that Delta table via the Delta connector in storage mode from the stock ingestion image (S1), otherwise `fabric_control.register()` via REST is implemented as the fallback
**And** the OpenLineage 1.53.0 event emitted by Spark (Delta on s3a → JDBC to PG) appears in OM on the entity whose FQN equals the registry `om_fqn` (S2), otherwise `emit_lineage()` via REST is the fallback

**Given** the spikes are finished
**When** I read `docs/spikes.md`
**Then** each of S1–S3 records outcome (pass / fallback), exact config used and the evidence (command output or screenshot)

### Story 1.3: Orchestration and resource spikes (S4, S5, S6)

As the platform owner (P1),
I want to prove DockerOperator orchestration, OM bot-token automation and the RAM budget,
So that the one-command demo and the < 2 min partial refresh are feasible on a 16GB laptop.

**Acceptance Criteria:**

**Given** a DAG mounted from `pipelines/dags` that imports only the Airflow SDK
**When** it runs a `fabric-jobs` container via `DockerOperator` (docker.sock mounted, `group_add`, `mount_tmp_dir=False`)
**Then** the container runs `spark-submit --master local[*]`, removes itself, and a value it returns is readable by a downstream task via XCom (S5)
**And** an HTTP call with JWT to Airflow `/api/v2` from the mock-api container triggers that DAG (S5)

**Given** only admin credentials in `.env`
**When** the spike bootstrap script runs
**Then** it fetches an OM bot token via REST and writes it to a secret volume without manual copy (S6)
**And** a `report_dq()` spike creates a test case and pushes a result onto the Delta table registered in Story 1.2 (S6)

**Given** the `core` profile with one Spark job running
**When** RAM is sampled with `docker stats`
**Then** the measured total is recorded in `docs/spikes.md` and is ≤ 12GB (S4), otherwise the S4 fallback (chained scoped jobs in one container / SparkSession) is documented as adopted

### Story 1.4: Simulated source systems seeded from the sample Excel

As a Marketing Data Engineer (UG06),
I want the 7 simulated source systems rebuilt from the sample Excel with their real interface types,
So that the demo integrates genuinely different sources (database, API, file) like a real company.

**Acceptance Criteria:**

**Given** the sample xlsx in `sources/`
**When** I run the seed command
**Then** PostgreSQL database `sources` contains Sales_Lines, Customers and Product_Costs tables; the mock API (FastAPI, 3-layer routers/services/repositories) serves Campaigns/Targets/Attribution, Coupon_Plan and Campaign_Spend over GET; Finance daily spend and Tax rates are CSV files in SeaweedFS (FR-1)
**And** every source table carries a `Provenance` column (`original` or `synthetic` per R16: attribution, targets, product cost, allocated spend are synthetic)
**And** each source has a `source_version` integer that increments on every seed (AD-9)

**Given** the seed has run once
**When** I run it again
**Then** the resulting source data is identical to the first run (NFR-6) and only `source_version` increments
**And** row counts match the reconciliation marks (52,924 sales rows, 1,468 customers, 1,290 attribution links) verified by a unit test

**Given** the source-side `Spend_Recon` derived table
**When** it is seeded
**Then** it is marked `derived: true` in `contracts/datasets.yml` so that no downstream job may read it as a fact (FR-4, AD-4)

### Story 1.5: Versioned raw ingestion with load reconciliation

As a Marketing Data Engineer (UG06),
I want every source loaded into an append-only raw zone and reconciled against the known baselines,
So that I can prove nothing was lost or duplicated before any metric is computed.

**Acceptance Criteria:**

**Given** seeded sources and migration `migrations/ops/001_*.sql` creating `ops.runs`, `ops.alerts` and `ops.load_reconciliation`
**When** each `jobs/ingest/<source>/job.py` runs inside `with fabric_control.run(job_id, scope) as run:`
**Then** it appends a Delta table `raw/<source>/<table>` with `_load_id`, `_ingested_at`, `_source`, `_load_kind`, `_source_version` and never overwrites earlier loads (FR-2, AD-9)
**And** `ops.runs` gets one row per run with start/end, rows in/out, status and Delta version (AD-13); on exception an `ops.alerts` row is written and the error re-raised

**Given** a completed load
**When** reconciliation runs
**Then** source vs raw row counts and checksums are compared and checked against `governance/baselines.yml` (52,924 · 26,631 · 1,468 · 1,290 · 0) and the match/mismatch result is written to `ops.load_reconciliation` (FR-3)
**And** a load that fails reconciliation is flagged unusable and `io.read_raw()` never returns rows from it

**Given** two successive loads of the same source
**When** `io.read_raw()` is called
**Then** it returns only the latest version per natural key from reconciled loads
**And** unit tests cover append-only behaviour, reconciliation mismatch, and latest-per-key selection

### Story 1.6: Unified sales entities with order key and standardized categories

As a Marketing Analyst (UG01),
I want sales, customers and products unified with one order key and consistent dates and category names,
So that every page counts orders and customers the same way.

**Acceptance Criteria:**

**Given** reconciled raw sales, CRM and product loads
**When** the unified jobs run
**Then** `unified/orders` has `order_key = customer_id || '|' || transaction_id` with the original `transaction_id` kept, `gross_value = SUM(quantity × avg_price)` (R2) and `shipping_fee` counted once per order (R3), totalling 26,631 orders (FR-5)
**And** `unified/order_lines`, `unified/customers` (with `first_observed_order_date`, R9), `unified/products` and `unified/product_cost` exist with schemas published in `contracts/` before coding (AD-11)
**And** dates are ISO `DATE`, money `NUMERIC(18,2)`-compatible decimals without currency label (R10)

**Given** `governance/mappings/category.yml`
**When** the mapping job runs
**Then** `unified/ref_category_map` is materialized with lineage, "Notebooks" maps to "Notebooks & Journals", and `Nest`, `Nest-USA`, `Nest-Canada` remain three separate categories (FR-6, R13)

**Given** each unified job
**When** it writes
**Then** it calls `fabric_control.check()` and `gate()` before writing (stub-passing at this stage) and writes only via `pipelines/io`
**And** transforms are pure DataFrame → DataFrame functions with unit tests on fixtures, and P1 publishes `contracts/fixtures/<dataset_id>.parquet` for the `dev` profile

### Story 1.7: Unified campaign, attribution, spend and target entities

As a Marketing Analyst (UG01),
I want campaigns, attribution, coupon plan, spend and targets unified and linked to orders,
So that campaign results and costs can be joined reliably.

**Acceptance Criteria:**

**Given** reconciled raw API and file loads
**When** the unified jobs run
**Then** `unified/campaigns`, `unified/attribution` (≤ 1 campaign per order, R6; 1,290 order–campaign links), `unified/coupon_plan`, `unified/campaign_spend` (API allocation + finance daily online spend file) and `unified/campaign_targets` exist per `contracts/`
**And** `unified/attribution` joins to `unified/orders` on `order_key` with zero orphan links verified by a unit test

**Given** input that Spark lineage cannot see (API-sourced raw)
**When** the job completes
**Then** lineage from the raw API dataset to the unified dataset is emitted through `fabric_control.emit_lineage()` (or OpenLineage where available) using registry names (AD-2, AD-18)
**And** synthetic provenance of attribution, targets and allocated spend is preserved from the raw `Provenance` column

### Story 1.8: Shared marts for campaign results and spend reconciliation

As a Finance Controller (UG04) and Marketing Analyst (UG01),
I want campaign results and allocated spend computed once in shared marts,
So that every page shows the same attributed numbers and costs are never double counted.

**Acceptance Criteria:**

**Given** migrations `migrations/mart_shared/NNN_*.sql` creating tables with PK = grain and a `mart.yml` per mart
**When** the shared mart jobs run
**Then** `mart_shared.campaign_attributed_daily` (`campaign_id × date`: attributed_orders, attributed_gross_value, buyers, first_observed_buyers), `mart_shared.campaign_spend_allocated` (`campaign_id × date`: allocated, unallocated) and `mart_shared.spend_reconciliation` are written via `io.write_pg_full` (TRUNCATE + INSERT in one transaction) with `_refreshed_at`, `_run_id`, `_source_version` (AD-11, AD-17)
**And** total attributed orders across all campaigns = 1,290 and allocated + unallocated = daily online spend with discrepancy 0 (FR-4, R8)
**And** `spend_reconciliation` is recomputed from `unified` and never reads the source `Spend_Recon` table (FR-4)

**Given** a job attempting DDL or JDBC `overwrite`
**When** code review / CI runs
**Then** it is rejected; jobs contain no `DROP`/`CREATE`/`ALTER` (AD-17)

**Given** a full rerun with the same `source_version`s
**When** the mart output is compared to the previous run
**Then** every non-`_` column is identical (AD-9, NFR-6)

### Story 1.9: Per-role database logins and generated `*_v` views

As a demo viewer,
I want each role to connect with its own database login and read only generated views,
So that access rules are enforced by the platform rather than by the UI.

**Acceptance Criteria:**

**Given** `.env` holding one PG login per UG01–UG06 plus `app_writer` and `ops_writer`
**When** `sync_policies()` runs after migrations
**Then** it generates exactly one view `<schema>_v.<table>` per exposed table with the same column names, prefixed `policy_` objects carrying the comment `generated-by sync_policies`, and grants only views (never underlying `mart_*`, `app`, `ops` tables) to UG logins (AD-8)
**And** `governance/tags/*.yml` fragments (merged into the logical `tags.yml`) and `access_matrix.yml` exist; every serving column is tagged, and if any column is untagged `sync_policies()` fails (fail-closed)

**Given** a UG login
**When** it queries an underlying mart table directly
**Then** PostgreSQL returns `permission denied`
**And** `verify_policies()` writes and cross-checks `ops.policy_effective` against `has_column_privilege`

### Story 1.10: One-command full refresh and idempotent bootstrap

As a lecturer running the demo,
I want `docker compose up` to bring the whole system to a ready state with no manual steps,
So that the demo builds on any 16GB machine exactly as documented.

**Acceptance Criteria:**

**Given** the `full_refresh` DAG (Airflow SDK only, tasks = `fabric-jobs` via DockerOperator, pool `fabric_writes` slots=1, `max_active_runs=1`)
**When** it runs
**Then** every job registered in `contracts/datasets.yml` runs in dependency order (ingest → unified → mart_shared → any slice marts registered so far), so jobs added by later stories are picked up without editing the DAG, and each run is recorded in `ops.runs` (AD-4, AD-12)

**Given** a clean machine with only `.env` filled from `.env.example`
**When** I run `docker compose up`
**Then** the one-shot `bootstrap` service runs PG init → seed → OM bot token → register OM services → migrations → `sync_tags` → `sync_glossary` → `full_refresh` → `sync_policies` → `verify_policies` and exits 0 (AD-20, NFR-1)
**And** running bootstrap again is idempotent, and `make reset` deletes the named volumes and rebuilds to the same result (NFR-6)
**And** the README documents the startup procedure including `.wslconfig memory=14GB` (SM5)

### Story 1.11: Themed app shell with login, role switcher and role-based navigation

As any demo user (UG01–UG06),
I want to log in once and switch roles instantly, seeing only the pages my role is allowed,
So that the presenter can tell each role's story without logging in again.

**Acceptance Criteria:**

**Given** `.streamlit/config.toml` with the DESIGN.md theme mapping and the single `app/shell` CSS layer
**When** any page renders
**Then** colors, fonts (system sans, base 16px), radii and campaign series colors match UX-DR1 and UX-DR4, typography follows the UX-DR3 floor (body ≥ 15px, nothing < 14px), light mode only, and all custom CSS lives only in `app/shell` (UX-DR2)
**And** the sidebar shows app name + "CO5173 · Academic demo", the role-switcher ("Role (demo mode)", caption "Signed in as UGxx · nav filtered to this role"), and nav groups (UX-DR5)

**Given** the login screen
**When** I enter invalid credentials
**Then** "Invalid demo credentials" appears inline with no role hint
**When** I log in successfully
**Then** I land on my role's home page (UX-DR7) (FR-19)

**Given** I am logged in
**When** I switch role
**Then** the PG connection is swapped (not `SET ROLE`), nav is rebuilt with `st.navigation` from the pages declared in each slice's `app/pages/<slice>/registry.py` filtered by the EXPERIENCE role × page matrix (slices add pages without editing `app/shell`), hidden pages are unreachable by URL, and if the current page is not permitted I am redirected to the new home with toast "Switched to <Role> (UGxx)" (UX-DR6, UX-DR7)
**And** filter state per page persists across the switch (UX-DR19)

**Given** any page render
**When** it finishes
**Then** the shell measures render time and calls `record_timing(page, ms)` (UX-DR10, FR-26 capture)
**And** loading states use skeletons shaped like the final element, never a centered spinner (UX-DR24); pages follow the anatomy of UX-DR8 at the 1366×768 desktop baseline with `layout="wide"` (UX-DR40)

### Story 1.12: `shell.metric` card, badges and shared table/format helpers

As a Marketing Analyst (UG01),
I want every number shown with its freshness and synthetic status in a consistent card,
So that I can trust and defend each figure at a glance.

**Acceptance Criteria:**

**Given** a `term_id` declared in `governance/glossary/<slice>.yml`
**When** a page calls `shell.metric(term_id, value, freshness)`
**Then** the card renders label = glossary `display_name` verbatim (canonical names and voice per UX-DR36), KPI value (40px/700), and a badge row with `badge-fresh` "Refreshed HH:MM" (from `freshness` = `max(_refreshed_at)` of the producing rows, AD-19) and `badge-synthetic` when the term has a Synthetic ancestor (UX-DR11, UX-DR12)
**And** the `currency_unverified` note is collected once into the page footnote strip, never repeated per card (UX-DR21)
**And** an unknown `term_id` raises an error that makes the e2e test fail (AD-16)

**Given** shared helpers in `app/shell`
**When** pages format values or render tables
**Then** counts/money use thousands separators without currency symbol, ratios `3.42×`, percents one decimal, ISO dates (UX-DR37); tables are themed, numeric right-aligned, campaign cells show name + muted `CMP-0x`, masked values render as mono + lock and `__denied` / `permission denied` render as italic "not permitted for role" (UX-DR16)
**And** `status-chip` variants (UX-DR13), empty state (UX-DR38), `banner-error` (UX-DR20 error part) and toasts (UX-DR25) exist as shell components with icon + text, never color only (UX-DR39)

### Story 1.13: Campaign Overview page (BR01)

As a Marketing Analyst (UG01),
I want a Campaign Overview with Attributed Orders, Attributed Buyers, Attributed Gross Value and Average Order Value filterable by period and campaign,
So that I can report last period's campaign results in minutes instead of manual exports.

**Acceptance Criteria:**

**Given** a `mart_campaign` overview mart (migration + `mart.yml`, aggregating only `mart_shared` (`campaign_attributed_daily`, `campaign_attributed_orders`) and `unified/campaigns`, AD-11) and its generated `*_v` view
**When** UG01 opens Campaign Overview (home) or UG03 opens it from nav
**Then** four metric cards render via `shell.metric` with glossary terms `attributed_orders`, `attributed_buyers`, `attributed_gross_value`, `average_order_value` declared in `governance/glossary/campaign.yml` (FR-27)
**And** the page shows "Viewing as: <Role> (UGxx)", a filter bar (Period, Campaign) that applies on change, a by-campaign table and the footnote strip

**Given** no filter
**When** the page loads
**Then** Attributed Orders for the whole period = 1,290 and the page responds in < 3 s (NFR-4)
**When** I select a campaign with no attributed orders in the chosen period
**Then** the empty state reads "No attributed orders for CMP19_0x in this period. Clear the Campaign filter to see all."

**Given** `tests/reconcile/test_reconcile_br01.py` (renamed: same basename as `tests/e2e/test_br01.py` clashes without `__init__.py`)
**When** `make test-e2e` runs against the `core` stack
**Then** independent SQL on `unified` matches every value in the `*_v` view (ignoring `_` columns) and `tests/e2e/test_br01.py` plus a Streamlit `AppTest` smoke test pass (T-BR01, NFR-3, NFR-7)

## Epic 2: Understand & trace every metric

Every role opens the ⓘ on any metric and gets its definition, lineage and quality in one dialog; browses and searches the Catalog & Glossary; follows any dataset on the Lineage page from source to metric with times and versions. Synthetic provenance propagates through lineage automatically.

### Story 2.1: Glossary and tags as code synced to OpenMetadata

As a Marketing Data Steward (UG05),
I want every marketing metric defined once in the repository and synced to the catalog automatically,
So that there is exactly one definition per metric and nobody edits it by hand in a UI.

**Acceptance Criteria:**

**Given** `governance/glossary/{platform,campaign,customer,finance}.yml` with terms carrying `display_name`, `owner_slice`, `dataset_id`, `column`, `rules`, `limitations`, `notes`, definition and formula
**When** `fabric_control.sync_glossary()` runs (bootstrap step 6)
**Then** OM contains exactly one glossary `marketing_metrics` whose terms have ID = snake_case of the display name with `/` → `_per_` (e.g. `attributed_value_per_spend_ratio`) and are linked to their actual OM columns (FR-11, AD-16)
**And** the canonical terms of FR-11 exist, and `attributed_value_per_spend_ratio` carries the note "not ROAS" with the R7 reason

**Given** a duplicate term ID or duplicate display name across files
**When** `sync_glossary()` runs
**Then** it fails with a message naming both files

**Given** raw datasets whose source `Provenance` is `synthetic`
**When** `sync_glossary()` runs
**Then** every descendant dataset and every term with a Synthetic ancestor in lineage is labelled `Provenance.Synthetic`, computed rather than hand-assigned (AD-2, R16)
**And** `sync_tags()` pushes the classification tags from `governance/tags.yml` to OM columns; re-running both functions is idempotent

### Story 2.2: Catalog and metadata read API in `fabric_control`

As a slice developer,
I want one read API for catalog, terms, search, lineage and quality,
So that every page shows metadata consistently without calling OpenMetadata directly.

**Acceptance Criteria:**

**Given** datasets registered in OM with registry names (connector or `register()` fallback from Story 1.2)
**When** a service calls `catalog(filter)`, `term(term_id)`, `search(q)`, `lineage(dataset_id, depth)` and `latest_score(dataset_id)`
**Then** only `fabric_control/clients` talks to OM and each call returns plain Python objects keyed by `dataset_id` / `term_id` from `contracts/datasets.yml` (AD-3, AD-18)
**And** `catalog()` items include description, owner, source, last refresh, quality score and provenance label (FR-10); `latest_score()` returns "not yet measured" when no DQ result exists

**Given** `FABRIC_CONTROL_MODE=offline`
**When** the same functions are called in the `dev` profile
**Then** they return data from local `governance/` and `contracts/` files so P2–P4 can build pages without OM running
**And** unit tests cover FQN ↔ `dataset_id` translation and offline mode

### Story 2.3: Lineage graph component and Lineage page

As a Marketing Data Engineer (UG06) and any other role,
I want to see a dataset's lineage from source through processing steps to the metric with times and versions,
So that I can say exactly where a number comes from.

**Acceptance Criteria:**

**Given** a dataset or metric selected on the Lineage page (visible to all six roles)
**When** the page renders `lineage(dataset_id, depth)`
**Then** the `lineage-graph` shell component draws a left-to-right DAG source → raw → unified → mart → metric with rounded nodes showing dataset id, refreshed time and version (FR-15, UX-DR15)
**And** for UG01's Attributed Orders the graph traces back through `unified/orders` and `unified/attribution` to the Sales DB and Attribution API sources

**Given** the graph
**When** I click a node
**Then** a side detail shows dataset id, refreshed time, version and quality score
**And** the graph is keyboard-operable and the page renders in < 3 s

### Story 2.4: Definition dialog from any metric (Definition · Lineage · Quality)

As a Marketing Analyst (UG01),
I want to click ⓘ on any metric card or metric column header and see its definition, lineage and quality in one dialog,
So that I can defend every number without leaving the page.

**Acceptance Criteria:**

**Given** a metric card rendered by `shell.metric` or a table metric column header
**When** I click its ⓘ
**Then** an `st.dialog` (large) opens titled with the `display_name` in accent color, with tabs Definition · Lineage · Quality (FR-12, UX-DR14)
**And** Definition shows definition, formula, source columns as inline code, rules R-xx, limitations, owner, synthetic label and cautions (e.g. "Not ROAS" as a danger status-chip)
**And** Lineage reuses the `lineage-graph` component from Story 2.3; Quality shows the dataset score + status chip and last refresh

**Given** the dialog is open
**When** I press Esc or close it
**Then** I return to the page with filters intact, and the dialog never opens another dialog (one modal level)
**And** Campaign Overview's four cards now carry the ⓘ button and a Streamlit `AppTest` asserts the dialog opens for each

### Story 2.5: Catalog & Glossary page with keyword search (BR13)

As a Marketing Data Steward (UG05) and any other role,
I want to browse and search datasets and metric terms,
So that I can look up definitions, formulas, source columns and owners myself.

**Acceptance Criteria:**

**Given** the Catalog & Glossary page (visible to all roles)
**When** I browse
**Then** I see every dataset raw → unified → serving with description, owner, source, last refresh, quality score and provenance (original / synthetic) (FR-10)

**Given** the search box
**When** I search "Attributed Value / Spend Ratio"
**Then** results across datasets and terms appear via `search(q)` (FR-13); selecting the term opens the definition dialog showing definition, formula, source columns, owner, "Not ROAS" and the Synthetic label (T-BR13, UX-DR35)
**When** I search a word with no match
**Then** the page shows "No datasets or terms match '<q>'."

**Given** `tests/e2e/test_br13.py`
**When** `make test` runs
**Then** the scenario passes and the e2e suite fails if any `term_id` used by a page does not exist in the glossary

## Epic 3: Trustworthy & protected data (quality gate + policy)

UG05 sees per-dataset quality scores, triages the exception list and inspects the effective access matrix. A critical quality failure blocks the downstream write and pages show "Using previous version". Column tags drive allow/mask/deny enforced inside Postgres, fail-closed.

### Story 3.1: Quality rules, scoring and reporting on every write

As a Marketing Data Steward (UG05),
I want quality rules run on every unified and mart dataset before it is written,
So that each table has a comparable quality score computed in one place.

**Acceptance Criteria:**

**Given** `dq/<dataset>.yml` files (completeness, uniqueness, validity, consistency) with unique `rule_id`, GX `expectation` and `severity: critical|warning` for all existing unified and `mart_shared` datasets, reviewed by P4
**When** a job calls `check(dataset_id, df, scope)` before writing
**Then** GX Core 1.23.2 evaluates the rules; `score()` returns pct and status Green (100% critical and ≥ 90% all), Amber (100% critical, < 90% all) or Red (any critical fails) (FR-7)
**And** `report_dq()` writes `ops.dq_results` (migration in this story) and pushes test cases (FQN `<om_fqn>.<rule_id>`) and results to OM; a failure pushing to OM logs a warning and does not block the job (AD-7)
**And** `unified/orders` has a critical uniqueness rule on `order_key`

**Given** scope mode is requested
**When** table-level rules (uniqueness, row-count, referential) run
**Then** they evaluate the post-merge image (rows outside scope ∪ newly computed rows)
**And** unit tests cover scoring boundaries (exactly 90%, one critical failure)

### Story 3.2: Critical quality gate and stale propagation

As a Marketing Analyst (UG01),
I want bad data blocked before it reaches my dashboard, with a clear warning that I am seeing the previous version,
So that I never report numbers from a failed load unknowingly.

**Acceptance Criteria:**

**Given** a job whose `check()` has a failing critical rule
**When** `gate()` runs
**Then** it raises `GateFailed`, nothing is written, `ops.runs.status = 'gated'` with the failing rule, and the DAG skips descendant tasks of that dataset (FR-17, AD-19)

**Given** a gated dataset
**When** any page asks `status(dataset_id)` for a displayed value
**Then** the dataset and every descendant in lineage is reported stale with `since` and `cause` (lineage cached per DAG run)
**And** `shell.metric` shows the stale variant (warning border, warning value color, `badge-stale` "Using previous version") and the page shows one `banner-stale` listing the failed datasets, e.g. "Using previous version — quality check failed on `unified/orders`" (UX-DR11, UX-DR12, UX-DR20)
**And** stale lineage nodes get a warning border + ⚠ in the lineage graph

**Given** the gated dataset is later written successfully
**When** pages re-render
**Then** stale badges and the banner disappear
**And** a dev-only toggle (`make break-dq DATASET=<id>`) injects a critical failure for tests and demo rehearsal

### Story 3.3: Stable exception datasets and shared exception list

As a Marketing Data Steward (UG05),
I want data exceptions detected and stored with stable IDs,
So that my review status survives every rerun.

**Acceptance Criteria:**

**Given** `contracts/exceptions.yml` defining the shared exception schema
**When** the unified jobs run
**Then** `unified/exceptions_shared_transaction_id` lists the 1,319 transaction codes that appear across multiple customers and `unified/exceptions_coupon_mismatch` lists the 400 sales lines not reconcilable with the coupon plan (126 of them with `Coupon_Status = Used`; categories Backpacks 89, Fun 160, Google 105, More Bags 46 absent from Coupon_Plan) (FR-8, AC02)
**And** category normalization (R13, only Coupon_Plan "Notebooks" → "Notebooks & Journals") does not change the 400/126 baseline and creates no duplicate plan rows per month × category
**And** each row has `exception_id = sha1(class || '|' || canonical natural_key)`, identical across reruns
**And** R17 storage traits (coupon status per line, shipping fee repeated per line) are never emitted as exceptions

**Given** the exception datasets
**When** `mart_shared.exceptions` runs (P1)
**Then** it merges all classes and is the only exception source for the UI via `mart_shared_v.exceptions`
**And** a reconcile test asserts exactly 1,319 shared-transaction exceptions and 400 coupon-mismatch lines (126 `Used`), and both marks are added to `governance/baselines.yml`

### Story 3.4: Data Quality & Exceptions page (scoreboard + triage)

As a Marketing Data Steward (UG05),
I want a page showing each dataset's quality score and the exception list I can triage,
So that I can manage data quality from one place.

**Acceptance Criteria:**

**Given** UG05 lands on Data Quality & Exceptions (home)
**When** the page loads from `ops_v.dq_results`
**Then** the DQ scoreboard shows per dataset score %, Green/Amber/Red status-chip and failing rules with Critical/Warning severity (FR-7, UX-DR31)

**Given** the exceptions table from `mart_shared_v.exceptions` joined with `app_v.exception_status`
**When** I filter class = shared transaction ID
**Then** 1,319 rows are shown with status-chip new / seen / accepted
**When** I multi-select rows and click "Mark seen" or "Mark accepted"
**Then** statuses are written to `app.exception_status` keyed by `exception_id` via `app_writer` and chips update (FR-9, UX-DR30)

**Given** an `exception_id` that no longer exists after a rerun
**When** the page renders or I try to mark it
**Then** it shows "resolved at source" instead of updating and remains visible under the status filter
**And** `tests/e2e/test_br14_quality.py` covers scores and the 1,319 listing (T-BR14 quality)

### Story 3.5: Column classification tags and masking/deny policy in Postgres

As a Marketing Data Steward (UG05),
I want column labels to decide who sees, masks or is denied each column at the database layer,
So that sensitive customer and cost data is protected regardless of the UI.

**Acceptance Criteria:**

**Given** `governance/tags.yml` classifying every serving column (e.g. `customer_identifier`, `financial.sku_cost`, `financial.aggregate`) with an action per tag × role from {`allow`, `mask:<fn>`, `deny`} (FR-14)
**When** `sync_policies()` regenerates the `*_v` views
**Then** `mask:partial` renders guest identifiers as `C****42` for roles without business need, `deny` returns NULL plus a `<col>__denied` flag column, and mask functions come only from the closed list in `fabric_control` (FR-20, AD-8)
**And** UG04 is allowed SKU cost of goods, UG03 is denied SKU cost but allowed aggregate contribution, UG01 is denied cost of goods, customer IDs are masked for non-CRM roles
**And** `app.segments` and `ops.metric_change_log` columns are tagged and go through the same policy

**Given** policies are applied
**When** `verify_policies()` runs
**Then** `ops.policy_effective(role, dataset_id, column, action)` matches `has_column_privilege` and the views' actual output for every role, else it fails
**And** the UI renders masked values with `badge-masked` and denied values with `badge-denied` "not permitted for role" (no red)

### Story 3.6: Access Matrix page

As a Marketing Data Steward (UG05),
I want to see the role × dataset/column permissions actually in effect,
So that I can prove the policy matches what the platform enforces.

**Acceptance Criteria:**

**Given** UG05 opens Access Matrix
**When** the page loads `effective_matrix()` from `ops_v.policy_effective`
**Then** a read-only grid of role × dataset/column shows cells as status-chips allow (success) / mask (warning) / deny (neutral) with icon + word (FR-22, UX-DR32)
**And** UG03 deny on SKU cost, UG01 deny on cost, and customer ID mask for non-CRM roles are visible

**Given** `tests/e2e/test_br14_access.py`
**When** it runs
**Then** the matrix equals the FR-20 expectations and matches `verify_policies()` output (T-BR14 access)

## Epic 4: Campaign performance & stop/keep decisions

UG01 and UG03 compare campaigns, channels and periods with shared definitions, rank SKUs/categories, split first observed vs returning buyers, and UG03 decides Continue/Adjust/Stop per campaign against its own retrospective target.

### Story 4.1: Campaign Comparison with shared definitions (BR02)

As a Marketing Manager (UG03),
I want to compare the 5 campaigns, their channels and periods side by side using the same metric definitions,
So that I can judge the portfolio without arguing about how numbers were computed.

**Acceptance Criteria:**

**Given** a `mart_campaign.comparison` mart (campaign × channel × period) aggregating only `mart_shared.campaign_attributed_daily` and `unified/campaigns` (AD-11)
**When** UG03 or UG01 opens Campaign Comparison and picks a period
**Then** a table and a chart compare the 5 campaigns and channels; every metric column uses a glossary term and its header ⓘ opens the definition dialog (FR-28)
**And** the chart follows UX-DR17: title, labeled axes, legend, direct labels (≤ 4 series), hover tooltip, "Table view" toggle, no dual axis, each campaign in its fixed `series-n` color

**Given** `tests/reconcile/test_br02.py` and `tests/e2e/test_br02.py`
**When** `make test` runs
**Then** per-campaign totals equal Campaign Overview's values for the same period and every column maps to an existing term (T-BR02)

### Story 4.2: Products & Categories ranking and trends (BR03)

As a Marketing Analyst (UG01),
I want best-selling SKUs and categories and their trend over time, filterable by campaign,
So that I can decide which products to feature.

**Acceptance Criteria:**

**Given** a `mart_campaign.product_sales` mart built from `unified/order_lines`, `unified/ref_category_map` and `unified/attribution`
**When** UG01 opens Products & Categories and filters by campaign
**Then** top SKUs and categories are ranked by gross value and quantity with a monthly trend chart (FR-29)
**And** `Nest`, `Nest-USA` and `Nest-Canada` appear as three separate categories (R13)

**Given** a campaign filter with no attributed sales
**When** the page renders
**Then** the empty state explains why and how to clear the filter
**And** `tests/reconcile/test_br03.py` and `tests/e2e/test_br03.py` pass (T-BR03)

### Story 4.3: New vs Returning buyers by campaign (BR06)

As a Marketing Analyst (UG01) or CRM user (UG02),
I want to see first observed buyers and returning buyers per campaign,
So that I know whether a campaign brought in new customers.

**Acceptance Criteria:**

**Given** a `mart_campaign.new_returning` mart using `first_observed_buyers` and `buyers` from `mart_shared.campaign_attributed_daily`
**When** UG01 or UG02 opens New vs Returning and selects a campaign
**Then** First Observed Buyers and returning buyers are shown via `shell.metric`, with the R9 note "First observed in 2019 history" rendered from the term notes (FR-30)
**And** First Observed Buyers + returning buyers = buyers of that campaign

**Given** `tests/reconcile/test_br06.py` and `tests/e2e/test_br06.py`
**When** they run
**Then** the totals reconcile against an independent query using `unified/customers.first_observed_order_date` (T-BR06)

### Story 4.4: Targets achievement with Continue / Adjust / Stop (BR12)

As a Marketing Manager (UG03),
I want each campaign evaluated against its own target with a clear recommendation,
So that I can decide which campaigns to continue, adjust or stop.

**Acceptance Criteria:**

**Given** a `mart_campaign.target_achievement` mart (grain `campaign_id`) reading `unified/campaign_targets`, `mart_shared.campaign_attributed_daily` and `mart_shared.campaign_spend_allocated`, with `mart.yml` `modes: [full, scope]` and `scope_map: {campaign_id: campaign_id}`
**When** UG03 lands on Targets (home)
**Then** the table shows per campaign its own target metric (attributed gross value / attributed orders / first observed buyers), actual, achievement = actual / target, and campaign cost (FR-31, R14)
**And** the recommendation status-chip is Continue (≥ 100%, success), Adjust (70% – < 100%, warning) or Stop (< 70%, danger), with thresholds displayed next to the result and the note "retrospective synthetic target" plus the Synthetic badge

**Given** a stale source dataset for a campaign
**When** the page renders
**Then** the recommendation still displays with a stale badge and the page banner names the dataset

**Given** `tests/reconcile/test_br12.py` and `tests/e2e/test_br12.py`
**When** they run
**Then** every recommendation matches the FR-31 thresholds (T-BR12)

## Epic 5: Customer segments & win-back audiences

UG02 views RFM segments as of 2019-12-31, finds lapsed high-value customers, builds and saves target audiences for planning, and sees contact export locked with the R12 consent reason; customer IDs are masked per role.

### Story 5.1: RFM segmentation and RFM Segments page (BR05)

As a CRM / Customer Marketing user (UG02),
I want customers segmented by recency, frequency and monetary value as of 2019-12-31,
So that I can pick the right customer group for the next campaign.

**Acceptance Criteria:**

**Given** a `mart_customer.rfm` mart built from `unified/orders` and `unified/customers` with `AS_OF_DATE` from `contracts/constants.yml`
**When** the job runs
**Then** recency is days from the last order to 2019-12-31 (R5), frequency counts technical orders by `order_key` (R1), monetary sums `gross_value` (R2, excluding shipping R3), and each buying customer gets R/F/M scores and an RFM Segment (FR-32)
**And** scoring is quintiles 1–5 per dimension over buying customers (R = 5 most recent, F = 5 most orders, M = 5 highest value; ties broken deterministically by `customer_id` so reruns are identical, NFR-6), documented in glossary terms `rfm_segment`, `recency_score`, `frequency_score`, `monetary_score` (PRD R18)
**And** segments are assigned by an ordered rule table in `governance/mappings/rfm_segments.yml` (first match wins, every customer gets exactly one): Champions (R≥4, F≥4, M≥4) · Can't Lose (R≤2 and (F≥4 or M≥4)) · At Risk (R≤2 and (F=3 or M=3)) · Loyal (R≥3, F≥4) · Potential Loyalist (R≥4, F 2–3) · Recent First Buyers (R≥4, F=1; "first in observed history", R9) · Needs Attention (R=3) · Hibernating (R=2) · Lost (all remaining, i.e. R=1 with F≤2 and M≤2)

**Given** UG02 lands on RFM Segments (home)
**When** the page loads
**Then** the segment distribution is shown with the sequential blue ramp and a table view, and a customer list per segment shows customer IDs per policy
**And** the sum of customers across segments = number of customers who made a purchase

**Given** `tests/reconcile/test_br05.py` and `tests/e2e/test_br05.py`
**When** they run
**Then** segment totals and frequency-by-order reconcile (T-BR05)

### Story 5.2: Win-back list of lapsed high-value customers (BR09)

As a CRM user (UG02),
I want a list of customers who bought often or at high value but have not returned,
So that I can plan a re-engagement campaign.

**Acceptance Criteria:**

**Given** `mart_customer.rfm`
**When** UG02 opens Win-back
**Then** it lists customers with (F = 5 or M = 5) and R = 1 as of 2019-12-31 ("highest group" / "lowest group" = quintile 5 / quintile 1 per Story 5.1), filterable by purchased category, with customer IDs masked per role (FR-33a, UX-DR29)
**When** a filter yields no customers
**Then** "No lapsed high-value customers for this filter." with a widen-filter hint is shown

**Given** `tests/e2e/test_br09.py`
**When** it runs
**Then** every listed customer satisfies (F = 5 or M = 5) and R = 1, and every such customer is listed (T-BR09)

### Story 5.3: Audience Builder with saved audiences (BR08)

As a CRM user (UG02) or Marketing Analyst (UG01),
I want to build a target group by RFM segment, purchased category and purchase history and save it,
So that I can plan who a campaign should reach.

**Acceptance Criteria:**

**Given** migration `migrations/app/NNN_segments.sql` creating tagged `app.segments`
**When** I set criteria (segment, purchased category, purchase history)
**Then** the live count of matching customers updates on change (FR-33, UX-DR28)
**When** I click "Save audience" in its `st.form`
**Then** the audience is written to `app.segments` via `app_writer` and a toast confirms it

**Given** Win-back
**When** I click "Build audience from this list"
**Then** Audience Builder opens prefilled with the Win-back criteria
**When** criteria match zero customers
**Then** "No customers match these criteria." with a widen-segment hint is shown

### Story 5.4: Contact export locked by consent policy (FR-21)

As a CRM user (UG02),
I want the contact export to be locked with a clear reason when consent data is missing,
So that I never send marketing to customers without consent.

**Acceptance Criteria:**

**Given** the customer datasets have no consent metadata
**When** Audience Builder renders
**Then** `can_export(dataset_id, role)` returns `(False, reason)` and "Export contacts" is a disabled button (sunken fill + lock) with "Contact export disabled — no marketing consent data (R12)" shown beneath it, not tooltip-only (FR-21, UX-DR22)
**And** no contact-export view is granted to any role in Postgres

**Given** `tests/e2e/test_br08.py`
**When** it runs
**Then** an audience saves successfully and the export stays locked with the reason, even when the audience has zero matches (T-BR08)

## Epic 6: Campaign spend & financial contribution

UG04 and UG03 track budget vs allocated/unallocated daily spend, Attributed Value / Spend Ratio, Cost per Attributed Order, and estimated contribution by campaign; UG04 sees SKU reference cost while UG03 sees only the aggregate.

### Story 6.1: Budget & Spend page (BR10)

As a Finance / Business Controller (UG04),
I want budget, allocated and unallocated spend by day and the cost-efficiency ratios per campaign,
So that I can reconcile marketing spend with Finance without double counting.

**Acceptance Criteria:**

**Given** a `mart_finance.budget_daily` mart (grain `campaign_id × date`) aggregating `mart_shared.campaign_spend_allocated`, `mart_shared.campaign_attributed_daily` and `unified/campaigns`, with `mart.yml` `modes: [full, scope]` and `scope_map` for `campaign_id` and `date`
**When** UG04 lands on Budget & Spend (home) or UG03 opens it read-only
**Then** Campaign Budget is shown separately from spend, and Allocated Spend, Unallocated Spend, Attributed Value / Spend Ratio (`3.42×` format) and Cost per Attributed Order render via `shell.metric` (FR-34, R7, R8)
**And** the daily `spend-stack-bar` shows Allocated (accent) and Unallocated (`series-neutral`) with 2px gap, legend, direct labels and table-view toggle (UX-DR18)

**Given** `tests/reconcile/test_br10.py` and `tests/e2e/test_br10.py`
**When** they run
**Then** allocated + unallocated = daily online cost with discrepancy 0 and budget is never summed into cost (T-BR10)

### Story 6.2: Contribution page with role-dependent cost detail (BR11)

As a Finance Controller (UG04) and Marketing Manager (UG03),
I want estimated contribution per campaign with SKU cost detail visible only to Finance,
So that Finance can check the estimate while managers see only what they need.

**Acceptance Criteria:**

**Given** `mart_finance.contribution` (grain `campaign_id`, scoped by `campaign_id`) and `mart_finance.contribution_sku` (grain `campaign_id × sku`) reading `unified/product_cost`, `unified/order_lines`, `unified/attribution` and `mart_shared.campaign_spend_allocated`
**When** the jobs run
**Then** Estimated Contribution = attributed gross value − reference cost of goods − campaign cost, labelled an estimate not net profit (R11), and SKUs without reference cost are listed as "items not yet available" (FR-35)

**Given** UG04 opens Contribution
**When** the page loads
**Then** campaign contribution and the SKU cost-of-goods table are visible
**When** the presenter switches to UG03
**Then** campaign aggregate contribution remains visible and the SKU cost column shows "not permitted for role" from the platform `__denied` flag / permission error (Epic 3 policy)

**Given** `tests/e2e/test_br11.py`
**When** it runs as UG04 then UG03
**Then** UG04 sees SKU cost, UG03 sees only the aggregate, and the missing-items list is shown (T-BR11)

## Epic 7: Pipeline operations & alerts

UG06 monitors every source and processing step, receives in-app alerts naming the failing step and cause, reloads a source or the whole pipeline from the UI, and sees end-to-end refresh and page response times.

### Story 7.1: Pipeline Status page

As a Marketing Data Ops engineer (UG06),
I want the status of every source and processing step in one page,
So that I know immediately whether the data is healthy.

**Acceptance Criteria:**

**Given** UG06 lands on Pipeline Status (home)
**When** the page reads `ops_v.runs` and `ops_v.load_reconciliation`
**Then** each source and step shows last run, duration, rows in/out and a status-chip queued / running / success / failed / gated with failing step + cause (FR-23, UX-DR33)
**And** while any run is active the section auto-refreshes every 5 s via `st.fragment(run_every=5)` and stops when none are active; no other page auto-refreshes (UX-DR41)

**Given** a URL with `?event_id=<id>`
**When** the page opens
**Then** it filters to that event's runs with an elapsed timer vs "2 min target" and a warning chip "Over 2 min target" when exceeded

### Story 7.2: Alerts, alert indicator and source fault injection

As a Marketing Data Ops engineer (UG06) and Data Steward (UG05),
I want failures raised as in-app alerts that point to the failing step,
So that I notice and diagnose problems without reading logs.

**Acceptance Criteria:**

**Given** `make break-source SRC=<source>` in `sources/` (no in-app break button)
**When** the next load of that source runs
**Then** it fails, `run()` writes `ops.alerts` with cause and failing step, and Pipeline Status shows a danger status-chip with the cause (FR-25)

**Given** open alerts
**When** UG06 or UG05 views any page
**Then** the sidebar alert-indicator (bell + count) shows the count of pipeline failures (UG06) or quality failures (UG05); it is hidden at 0 and never shown to other roles (UX-DR9)
**When** I click it
**Then** UG06 goes to Pipeline Status filtered to failed runs and UG05 to Data Quality & Exceptions filtered to failures

### Story 7.3: Reload a source or the whole pipeline (BR15)

As a Marketing Data Ops engineer (UG06),
I want to reload a failed source or the whole pipeline from the UI,
So that I can recover without command-line access.

**Acceptance Criteria:**

**Given** the `reload_source` DAG and `full_refresh`
**When** I click "Reload source" or "Reload all" and confirm once
**Then** `fabric_control.trigger()` starts the DAG, a toast confirms, and the run moves queued → running → success on the auto-refreshing page (FR-24)
**And** after a successful reload the reconciliation for that source shows row counts matching the baselines and the alert clears (FR-3)

**Given** the reload itself fails (fault still on)
**When** the run ends
**Then** the alert stays open with the failed step and cause and I can retry

**Given** `tests/e2e/test_br15.py`
**When** it breaks a source, asserts the alert, clears the fault and reloads
**Then** row counts match the reconciliation marks (T-BR15)

### Story 7.4: Refresh and page performance metrics (FR-26)

As a Marketing Data Ops engineer (UG06),
I want end-to-end refresh time, partial refresh time and page response times displayed,
So that I can prove the performance targets.

**Acceptance Criteria:**

**Given** `ops.runs` and `ops.page_timings` (written by `record_timing()` from the shell)
**When** Pipeline Status renders its performance section
**Then** it shows the last full refresh duration vs < 10 min target, partial refresh latency per event (`max(ended_at) − emitted_at`) vs < 2 min target, and p50/p95 page response time per page vs < 3 s target (FR-26, NFR-4)
**And** values over target are shown with a warning chip (icon + text)

## Epic 8: Change-driven partial refresh (demo climax)

UG04 corrects one day's spend for a campaign; within < 2 minutes only that campaign's BR10/BR11/BR12 metrics refresh, the UI shows progress and Refreshing badges, and Change History shows old → new values.

### Story 8.1: Spend edit API with invariants, versioning and change event

As a Finance Controller (UG04),
I want to correct one day's allocated spend for a campaign at the source,
So that the fix is versioned and flows through the platform like a real business change.

**Acceptance Criteria:**

**Given** the mock API `PUT` spend endpoint (routers/services/repositories)
**When** a role other than UG04 per `access_matrix.yml` calls it
**Then** it returns 403 with a reason (AD-5)
**When** UG04 sends an allocation < 0, > that day's online spend, or a date outside the campaign period
**Then** it returns 4xx with a field-level reason and nothing changes

**Given** a valid change
**When** it is saved
**Then** the source row is updated, `source_version` increments, an event `{event_id, emitted_at, source, keys: {campaign_id, date}, source_version}` is recorded, and `fabric_control.trigger("partial_refresh", event)` is called (FR-16a)
**And** no other code path can trigger `partial_refresh` (checked by test)

### Story 8.2: Lineage-driven impact analysis (`affected_by`)

As a Marketing Data Ops engineer (UG06),
I want the platform to work out from lineage exactly which datasets and rows a source change affects,
So that only the necessary part is refreshed.

**Acceptance Criteria:**

**Given** OM lineage and the `mart.yml` manifests
**When** `affected_by(event)` is called with a spend event for `campaign_id = X, date = D`
**Then** it returns `[{dataset_id, job_id, scope}]` in topological order (unified → mart_shared → slice marts), each scope projected onto that dataset's grain via `scope_map` (e.g. `campaign_spend_allocated` scoped to X × D, `target_achievement` and `contribution` scoped to X) (FR-16, AD-6)
**And** keys absent from a `scope_map` do not narrow scope, and datasets not downstream of spend (e.g. RFM, product sales) are excluded

**Given** unit tests with a fixture lineage graph
**When** they run
**Then** ordering, projection and exclusion are verified without OM running (offline mode)

### Story 8.3: Key-scoped writes with before/after capture

As a Finance Controller (UG04),
I want only the affected rows rewritten and their old and new values recorded,
So that unrelated metrics keep their values and refresh times, and changes are auditable.

**Acceptance Criteria:**

**Given** a job invoked with `--scope '{"mode":"scope","keys":{...}}'` (written verbatim to `ops.runs.scope`)
**When** it writes to PG via `io.upsert_pg(table, df, scope)`
**Then** it recomputes all grain rows matching the scope and replaces them with `DELETE WHERE scope` + `INSERT` in one transaction; rows outside scope keep their values and `_refreshed_at` (AD-6, AD-19)
**And** `upsert_pg` returns `(before, after)` read `FOR UPDATE`; `run.record_change()` writes `ops.metric_change_log(run_id, event_id, dataset_id, grain_key, term_id, old_value, new_value)` for the `metrics` columns
**And** Delta writes use `io.write_delta(..., replace_where=scope)` and the unified job records Delta version before/after in `ops.runs`

**Given** the scoped-capable jobs (`unified/campaign_spend`, `mart_shared.campaign_spend_allocated`, `mart_shared.spend_reconciliation`, `mart_finance.budget_daily`, `mart_finance.contribution`, `mart_campaign.target_achievement`)
**When** a scoped run and a full run are compared from the same `source_version`s
**Then** non-`_` columns are identical
**And** DQ table-level rules run on the post-merge image

### Story 8.4: `partial_refresh` DAG meeting the < 2 minute target

As a Finance Controller (UG04),
I want my spend change reflected in the affected metrics within two minutes,
So that I can confirm the correction during the same meeting.

**Acceptance Criteria:**

**Given** an event triggered by Story 8.1
**When** `partial_refresh` runs
**Then** its first task runs `affected_by(event)` in a `fabric-jobs` container, returns the list via XCom, and dynamic task mapping runs the scoped jobs in order in pool `fabric_writes` (AD-12)
**And** a gated dataset stops its descendants and marks them stale (AD-19)
**And** partial-refresh latency `max(ended_at) − emitted_at` is < 2 min on the sample data (NFR-4), measured on Pipeline Status

### Story 8.5: Spend edit form with progress strip and Refreshing badges

As a Finance Controller (UG04),
I want to edit spend on Budget & Spend and watch the affected metrics refresh,
So that I see the platform react to my change.

**Acceptance Criteria:**

**Given** UG04 on Budget & Spend
**When** I open the spend edit `st.form` (campaign, date, allocated value; label above, accent focus ring)
**Then** "Save change" submits to the mock API showing "Saving…"; a 4xx reason appears inline under the offending field in danger color with values kept (UX-DR23, UX-DR26)
**And** UG03 sees no form, only the read-only table

**Given** a successful save
**When** the response returns
**Then** toast "Change saved · partial refresh started" and a progress-strip "Refreshing N datasets · m:ss" with per-dataset steps queued → running → done appear below the form (UX-DR27)
**And** affected metric cards on Budget & Spend, Contribution and Targets show `badge-refreshing` "Refreshing…" with the previous value, then flip independently to "Refreshed HH:MM" — never the stale variant
**And** on completion the strip reads "N metrics changed — see Change History"

### Story 8.6: Change History page (BR16)

As a Finance Controller (UG04), Data Ops (UG06), Marketing Analyst (UG01) or Manager (UG03),
I want to see old and new values of metrics affected by a source change,
So that I can verify exactly what a change did and did not touch.

**Acceptance Criteria:**

**Given** `ops_v.metric_change_log` (policy-tagged)
**When** I open Change History (optionally `?event_id=<id>`)
**Then** per event it lists metric, campaign, old → new and delta; each row ⓘ opens the definition dialog; a summary reads "N metrics changed · M unchanged kept refresh time HH:MM" (FR-18, UX-DR34)
**When** no events exist
**Then** "No source changes recorded yet." is shown

**Given** `tests/e2e/test_br16.py`
**When** UG04 edits one day's spend for one campaign
**Then** within < 2 min only that campaign's BR10/BR11/BR12 metrics change, all other metrics keep their `_refreshed_at`, and before/after values are viewable (T-BR16)

## Epic 9: Architecture evidence: benchmarks & warehouse comparison

The team presents measured evidence for every architecture layer, a Data Fabric vs traditional warehouse comparison on BR01/BR10/BR16, the NFR-4 performance report, and a rehearsed demo readiness checklist.

### Story 9.1: Processing benchmark — Spark vs Flink at ×1, ×10, ×100

As the course team,
I want Spark and Flink compared on the same ETL job with growing data,
So that we justify the processing engine with measured figures.

**Acceptance Criteria:**

**Given** the `benchmark` compose profile with Flink (not running alongside `core`, NFR-2)
**When** the same job (build unified orders + compute RFM) runs on Spark and Flink with data replicated ×1, ×10, ×100 under the `bench/` prefix
**Then** wall time, peak RAM and lines of code / integration effort are recorded per engine and size in `benchmark/results/processing.csv` (NFR-5)
**And** both engines' outputs at ×1 equal the demo's `unified/orders` and RFM results

### Story 9.2: Layer alternatives — storage, catalog, quality, serving

As the course team,
I want at least one measured alternative per remaining layer,
So that every architecture choice has a rationale backed by numbers.

**Acceptance Criteria:**

**Given** the `benchmark` profile
**When** each comparison runs
**Then** storage (SeaweedFS vs pinned MinIO / local FS), catalog/metadata (OpenMetadata vs a lighter candidate selected during the benchmark), quality (GX vs Soda Core on the same `dq/*.yml` rules) and serving (Streamlit vs a React prototype or documented estimate) each record time, resources and integration effort (NFR-5)
**And** `benchmark/REPORT.md` states the chosen option and rationale per layer

### Story 9.3: Traditional warehouse baseline comparison (NFR-10)

As the course team,
I want the same BRs built on a traditional ETL-to-one-database architecture,
So that we can show what the Data Fabric layer adds.

**Acceptance Criteria:**

**Given** `warehouse_baseline` DB in the `benchmark` profile, populated by plain ETL with no metadata/governance layer
**When** BR01, BR10 and BR16 are implemented on it
**Then** the report compares build effort, traceability (can the number be traced to source?), response time to a source spend change and data correctness (reconciliation vs §6 marks) against the fabric (NFR-10)

### Story 9.4: Performance report and demo readiness

As a presenter,
I want a performance report and a one-command readiness check before the demo,
So that the 15-minute demo runs without surprises.

**Acceptance Criteria:**

**Given** the `core` stack after bootstrap
**When** I run `make demo-ready`
**Then** it verifies full refresh done, all badges fresh (no stale datasets), alert count 0, fault toggles off, `make test` green, and prints end-to-end refresh, partial refresh and page response times against NFR-4 targets (UX-DR42, SM2)
**And** `docs/demo-script.md` follows the 8-step EXPERIENCE demo script with role, page and proof per step, and the SM1–SM5 checklist records each BR's test result and the 7 fabric capabilities covered (SM4)

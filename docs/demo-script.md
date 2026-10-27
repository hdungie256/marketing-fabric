# Demo script

The 15-minute demo from `docs/03-ux-design/EXPERIENCE.md` (Demo Script), with the proof to point at in each step, and
the SM1–SM5 checklist (`docs/01-requirements/prd.md` section 3) filled in before the demo. One laptop and projector,
light mode, browser zoom 100%. The role switcher drives the story.

## Before the demo

1. `make up`, then `make bootstrap` (full refresh) on a fresh stack.
2. Open each page once so page times are recorded.
3. `make demo-ready`. It runs `make test`, `make test-e2e` (all 14 BRs and reconcile; T-BR16 records a partial
   refresh) and `make test-e2e-app`, then checks the pre-demo state (UX-DR42): full refresh done, all badges fresh
   (no stale dataset), alert count 0, fault toggles off (no `make break-source` or `make break-dq` left on). Last it
   prints the NFR-4 times: end-to-end refresh, partial refresh and page response (p95 per page). A time never
   measured is a `FAIL`. It must end with no `FAIL` line.
4. Copy the NFR-4 lines into the table under "Performance (NFR-4)" below.

## The 8 steps

| # | Min | Role | Page and action | Proof to point at | BR / capability |
|---|---|---|---|---|---|
| 1 | 0–2 | UG01 | Campaign Overview, select a campaign and period, open the ⓘ dialog: Definition, then Lineage | Attributed Orders for the whole period = 1,290; definition and lineage come from the catalog inside the app | BR01 · catalog/glossary, lineage |
| 2 | 2–4 | UG03 | Targets | Each campaign is judged on its own target metric; Continue / Adjust / Stop matches the ≥100% / 70–<100% / <70% thresholds; "Synthetic" badge and the "goals set after the fact" footnote | BR12 · glossary |
| 3 | 4–6 | UG04 | Budget & Spend, edit one day's spend: first enter an invalid value (4xx shown inline), then a valid one | Inline progress strip; only the affected metrics show "Refreshing…"; allocated + unallocated = daily cost | BR10, FR-16a · multi-source |
| 4 | 6–9 | UG06 | Pipeline Status filtered on the change event, then Change History. **Climax** | Partial refresh finishes under the 2-minute target; only that campaign's metrics change, other metrics keep their refresh time; before/after values in Change History | BR16 · lineage, action-triggering metadata |
| 5 | 9–10 | UG03 | Contribution | Campaign aggregate is visible, SKU cost shows "not permitted for role" (switch to UG04 to show it if time allows) | BR11 · access control |
| 6 | 10–11 | UG02 | Audience Builder, build a group by segment + category, save, try to export contacts | Group saves; export is locked with the missing-consent reason | BR08 · access control |
| 7 | 11–13 | UG05 | Data Quality & Exceptions, then Access Matrix | 1,319 duplicate transaction codes and 400 coupon-mismatch lines (126 `Used`); score and status per table; matrix matches FR-20 | BR14 · data quality, policy |
| 8 | 13–15 | UG06 | Presenter runs `make break-source SRC=spend`, then Reload on Pipeline Status, then `make fix-source SRC=spend` and Reload again | Alert with the failing step and cause; after the fix the reload succeeds and row counts match the reconciliation marks | BR15 · operational monitoring |

After step 8 the stack is back to the pre-demo state except for the spend edit from step 3.

## SM1–SM5 checklist

Fill in from the last `make test-e2e` run (`make test-e2e-app` for BR01's page test) before the demo.

### SM1, SM2, SM3: BR tests

| BR | Test files | Reconcile (SM3) | Result | Run on |
|---|---|---|---|---|
| BR01 | `tests/e2e/test_br01.py`, `tests/e2e/test_br01_app.py` | `tests/reconcile/test_reconcile_br01.py` | pass (4 e2e + app test + reconcile) | 2026-10-27 |
| BR02 | `tests/e2e/test_br02.py` | `tests/reconcile/test_reconcile_br02.py` | pass | 2026-10-27 |
| BR03 | `tests/e2e/test_br03.py` | `tests/reconcile/test_reconcile_br03.py` | pass | 2026-10-27 |
| BR05 | `tests/e2e/test_br05.py` | `tests/reconcile/test_reconcile_br05.py` | pass | 2026-10-27 |
| BR06 | `tests/e2e/test_br06.py` | `tests/reconcile/test_reconcile_br06.py` | pass | 2026-10-27 |
| BR08 | `tests/e2e/test_br08.py` | — | pass | 2026-10-27 |
| BR09 | `tests/e2e/test_br09.py` | — | pass | 2026-10-27 |
| BR10 | `tests/e2e/test_br10.py` | — | pass | 2026-10-27 |
| BR11 | `tests/e2e/test_br11.py` | — | pass | 2026-10-27 |
| BR12 | `tests/e2e/test_br12.py` | — | pass | 2026-10-27 |
| BR13 | `tests/e2e/test_br13.py` | — | pass | 2026-10-27 |
| BR14 | `tests/e2e/test_br14_access.py` | `tests/reconcile/test_br14_exceptions.py` | pass | 2026-10-27 |
| BR15 | `tests/e2e/test_br15.py` | — | pass | 2026-10-27 |
| BR16 | `tests/e2e/test_br16.py` | — | pass (partial refresh 1:43 after `SPARK_SHUFFLE_PARTITIONS`; 2:13 before) | 2026-10-27 |

- SM1, 14/14 BRs pass: ☑ 14/14 (BR16 re-run alone after the Spark fix)
- SM2, `make test` and `make test-e2e` all green: ☐ `make test` 714 passed; `make test-e2e` 69 passed, 2 failed
  (`test_br16.py`, `test_partial_refresh.py`, both on the 2-minute target); both pass when re-run after the Spark
  fix; `make test-e2e-app` 1 passed. A full `make test-e2e` run after the fix is still to do.
- SM3, every reconcile test passes: ☑ 8/8

### SM4: the 7 fabric capabilities

| Capability | Demo step | BR acceptance scenario | Covered |
|---|---|---|---|
| Lineage | 1, 4 | BR01, BR16 | ☑ |
| Catalog / glossary | 1, 2 | BR02, BR06, BR12, BR13 | ☑ |
| Data quality | 7 | BR03, BR05, BR14 | ☑ |
| Access control and policy | 5, 6, 7 | BR08, BR11, BR14 | ☑ |
| Multi-source | 3 | BR09, BR10 | ☑ |
| Action-triggering metadata | 4 | BR16 | ☑ |
| Operational monitoring | 8 | BR15 | ☑ |

### SM5: builds on 16GB

- `make reset` then `make bootstrap` on a 16GB machine with no manual fix: ☐ not run on 2026-10-27 (`scripts/check_memory.sh`
  for peak memory). `make up` brought the stack up on WSL2 with 15 GiB, the full refresh then passed.

## Performance (NFR-4)

Copied from `make demo-ready`.

| Measure | Target | Measured | Pass |
|---|---|---|---|
| End-to-end (full) refresh | < 10 min | 15:53 (16:46–17:31 before the Spark fix) | **fail** |
| Partial refresh after a source change (max over change events) | < 2 min | 1:42–1:45, 3 events (2:03–2:24 before) | pass |
| Analytics page response (p95, slowest page) | < 3 s | 1.9 s (campaign_overview, 16 samples) | pass |

Measured on 2026-10-27, WSL2 laptop, 15 GiB RAM. The Spark fix is `spark.sql.shuffle.partitions` 4 instead of the
default 200 (`pipelines/io/spark.py`); it halved the quality-rule time. What is left is mostly I/O: re-reading raw
tables in `source_versions` (~18 s per partial refresh), Delta writes to S3 (~15 s) and ~166 OpenMetadata calls
(~10 s). The full refresh repeats these for 30 jobs. Partial refresh per step for the slowest event before the fix: `ingest/spend` 33 s,
`unified/campaign_spend` 46 s, `marts/shared/campaign_spend` 12 s, `marts/campaign/target_achievement` 16 s,
`marts/finance/budget_daily` 12 s, `marts/finance/contribution` 24 s; the steps run one after another. Pages not
opened yet have no timing.

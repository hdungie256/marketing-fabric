---
title: "PRD — Marketing Data Fabric Demo"
status: final
created: 2026-09-27
updated: 2026-09-28
changeLog:
  - '2026-09-28: sprint change proposal — added R18 RFM scoring, coupon-mismatch baseline 400/126, exception status new/seen/accepted'
---

# PRD — Marketing Data Fabric Demo

> Data Engineering course project (CO5173, HCMUT, Semester 1, 2026–2027) — group of 4 members.
> This document is written from an **academic product** perspective: illustrating the Data Fabric architecture on a concrete marketing problem, running entirely on a local machine.

## 1. Context & Problem

**Context.** An online retail store (2019 Google Merchandise Store data) has four departments — Sales, CRM, Marketing, Finance — each keeping its own data in a separate system (database, API, file). No department can see the full picture.

**Problem.** A management question that seems simple — *"What results did the last campaign bring, with which customer group, and at what cost?"* — currently has to be answered manually: exporting files from each place, manually joining customer/order/campaign keys, manually handling inconsistent data (transaction codes duplicated across customers, shipping fees repeated on every line, inconsistent category names, mixed date formats). The result is slow, hard to verify, and each department calculates it differently.

**Why Data Fabric.** Instead of merely gathering data into one warehouse, Data Fabric places a **metadata/catalog/governance layer** (lineage, quality, policy, security, glossary) over the entire flow of *Source → Integration → Unified Data → Processing → Serving*. This lets users see not just the numbers, but **where the numbers come from, whether they can be trusted, and whether they are allowed to view them**.

## 2. Product Vision

Build a **scaled-down, locally-run Data Fabric platform** that connects Sales – CRM – Marketing – Finance data into a shared source of truth, and serves marketing user groups through a **visual, easy-to-use** analytics application.

The product must make clear — not vague — **every capability of the Data Fabric architecture**: demo viewers directly see how data is integrated, cleansed, given meaning, traced, and access-controlled, not just the final dashboard.

**PRD readers need to understand:** what the problem is (section 1), the goals and metrics (section 3), what the product does for whom (sections 4–7), and what counts as "done" (acceptance scenarios, section 8).

## 3. Goals & Success Metrics

**Main goal.** A demo that runs end-to-end on a local machine, in which every committed Business Requirement (BR) is accepted and clearly illustrates a Data Fabric capability.

| # | Metric | "Pass" threshold |
|---|---|---|
| SM1 | Share of committed BRs (14 BRs, section 5) passing acceptance scenarios (section 8) | 100% |
| SM2 | End-to-end test suite (source → unified data → application, NFR-7) | All green |
| SM3 | Data correctness: every aggregate figure reconciles with detailed data per the rules in section 6 (NFR-3) | 100% match |
| SM4 | The 7 selected fabric capabilities (lineage, catalog/glossary, data quality, access control, multi-source, action-triggering metadata, operational monitoring) each appear in at least one acceptance scenario (section 8) | 7/7 |
| SM5 | The entire system builds on a 16GB RAM machine using a documented startup procedure (NFR-1) | Runs, no manual fixes needed |

**Counter-metric (avoid over-engineering).** This is a demo with small data (~53 thousand sales rows), not a production system. Do not add tools/components unless they directly serve a BR or a fabric capability that needs illustrating; prioritize a system that **runs stably on a 16GB machine** over having a full-fledged tech stack (NFR-2).

## 4. User Groups

The first four groups come from the request for proposal (RFP); the latter two groups were added to **bring the Data Fabric's data governance layer into service for the Marketing department** — they help Marketing *trust* the numbers. Each group is the primary owner of at least 2 BRs.

| Code | Group | Decisions / work to support | Primary BR owner |
|---|---|---|---|
| UG01 | Marketing Analyst (main key user) | Analyze campaigns, channels, products to adjust marketing activities | BR01, BR03, BR06 |
| UG02 | CRM / Customer Marketing | Segment, select target customer groups, retain and re-engage customers | BR05, BR08, BR09 |
| UG03 | Marketing Manager (decision maker) | Compare campaign portfolio results, decide continue / adjust / stop | BR02, BR12 |
| UG04 | Finance / Business Controller | Reconcile budget, cost, and financial contribution of campaigns | BR10, BR11 |
| UG05 | Marketing Data Steward *(added)* | Manage marketing metric definitions, data quality, exceptions, customer data access rights | BR13, BR14 |
| UG06 | Marketing Data Ops / Data Engineer *(added)* | Operate the marketing data pipeline: source status, refresh, alerts, tracing | BR15, BR16 |

*Later phase (stretch):* UG07 — Marketing Data Scientist, uses governed data via API to build models (e.g., predicting customer churn).

## 5. Business Requirements Overview

14 committed BRs (exceeding the course's minimum of 2n = 8, n = 4 members). The **10 BRs that leverage marketing data** alone (the BRs selected among BR01–BR12) already meet the minimum of 8, even when the 4 fabric foundation BRs (BR13–BR16) are not counted for grading. Each marketing BR also demonstrates at least one Data Fabric capability.

**Business objectives** that the BRs serve:
- **O1** — Accurately measure campaign results to adjust marketing activities in a timely manner.
- **O2** — Understand and retain customers; select the right customer group for the next campaign.
- **O3** — Spend the marketing budget effectively, reconcilable with Finance.
- **O4** — Every department uses a shared set of trustworthy, traceable, correctly access-controlled figures.

| BR | Content | User group | Objective | Why Data Engineering is needed (source → processing) | BR source |
|---|---|---|---|---|---|
| BR01 | Campaign overview: number of orders, number of buying customers, attributed gross value, average order value by period | UG01 | O1 | Join Sales (DB) + Attribution/Campaign (API) via unified order key; deduplicate transaction codes | RFP P1 |
| BR02 | Compare results across campaigns, channels, periods using the same metric definitions | UG03, UG01 | O1 | Metrics share definitions from the glossary; aggregate by campaign × channel × period | RFP P1 |
| BR03 | Best-selling SKU/category and trends over time, filterable by campaign | UG01 | O1 | Standardize dates and category names; aggregate time series by SKU/category | RFP P1 |
| BR05 | RFM segmentation as of the as-of date | UG02 | O2 | Join Sales + CRM (DB); compute R/F/M by technical order as of 2019-12-31 | RFP P1 |
| BR06 | First observed buyers and returning customers by campaign | UG01, UG02 | O1, O2 | Determine the first purchase across the entire sales history, then reconcile with campaign-attributed orders | RFP P1 |
| BR08 | Build target customer groups by segment, category, purchase history | UG02, UG01 | O2 | Combine RFM results + category purchase history; apply consent policy before allowing export | RFP P1 |
| BR09 | Find customers who previously bought frequently or at high value but haven't returned in a long time | UG02 | O2 | From RFM: filter high F/M and low R as of the as-of date | RFP P2 → upgraded |
| BR10 | Budget, cost, Attributed Value / Spend Ratio, Cost per Attributed Order | UG04, UG03 | O3 | Join Advertising Cost (API) + Finance Cost (file) + Campaign; reconcile allocated/unallocated, no double counting | RFP P1 |
| BR11 | Estimate contribution: attributed gross value − reference cost of goods − campaign cost, listing items not yet available | UG04, UG03 | O3 | Join Product/ERP (cost of goods, DB) + Sales + campaign cost | RFP P2 → upgraded |
| BR12 | Evaluate campaign goal achievement to decide continue / adjust / stop | UG03 | O1, O3 | Join Goals (API) with BR01/BR06 results and BR10 cost, each campaign against its own target | RFP P1 |
| BR13 | Marketing metric catalog & glossary: look up definitions, formulas, source columns, owners | UG05 (+ all groups) | O4 | Collect metadata from all sources and processing steps; link terms to actual columns | Added |
| BR14 | Marketing data quality control, exception list, and role-based access/masking of customer data | UG05 | O4 | Run quality rules within the processing pipeline; column labels drive access policy | Added (AC01, AC02, AC06) |
| BR15 | Source & data pipeline monitoring: status, refresh time, error alerts, reload | UG06 | O4 | Track and coordinate loads from 8 source tables across 3 interface types | Added (AC07) |
| BR16 | Lineage and automatic refresh: trace metrics back to source; cost/campaign changes refresh the correct related results | UG06 (+ UG01, UG04) | O4, O3 | Automatically record lineage at each processing step; use lineage to determine what needs refreshing | Added (AC05) |

*Stretch:* BR04 (coupon status comparison), BR07 (post-campaign purchase behavior).

## 6. Business Rules & Data Conventions

The following rules are finalized for the demo; every metric in the application is computed according to these rules and recorded in the glossary (BR13).

| # | Rule | Content |
|---|---|---|
| R1 | Order key | Order = `CustomerID` + `Transaction_ID` (26,631 orders). The original `Transaction_ID` is not modified; 1,319 transaction codes that appear across multiple customers are placed on the exception list. |
| R2 | Gross value | `SUM(Quantity × Avg_Price)` per source field. **Not** called net revenue (missing returns, payments, actual discounts). |
| R3 | Shipping fee | Counted **once per order**, as a separate metric, not added into gross value. |
| R4 | Tax | GST is not added to gross value; the tax table is for reference only. |
| R5 | As-of date | Data period 2019-01-01 to 2019-12-31; recency/RFM is computed as of **2019-12-31**, not the current date. |
| R6 | Campaign attribution | Each order is attributed to at most one campaign per the simulated Attribution table. Attributed gross value **does not** mean incremental revenue caused by advertising. |
| R7 | Cost-efficiency ratio | Metric name: "Attributed Value / Spend Ratio". **Not** called "ROAS"; the glossary states the reason. |
| R8 | Cost | Campaign cost is allocated from daily online cost → **no double counting**; the allocated and unallocated portions are always shown. Budget ≠ cost. |
| R9 | New customer | "First purchase within the observed history (2019)" — may have purchased before 2019. |
| R10 | Currency unit | Keep the original numeric unit from the source, **do not assign USD/VND**; note "currency unit not verified" on the catalog and dashboard. |
| R11 | Cost of goods & contribution | Cost of goods is a reference estimate → estimated contribution (BR11) is an estimate, not net profit. |
| R12 | Customer contact | No marketing consent data available → the customer list (BR08) is for planning purposes only, contact list export is not allowed. |
| R13 | Category | Only normalize names that are truly synonymous ("Notebooks" → "Notebooks & Journals", found only in the coupon plan). `Nest`, `Nest-USA`, `Nest-Canada` are **3 separate categories**, kept as-is (campaign goals and the tax table use these exact names). |
| R14 | Campaign goals | Goals are **retrospective synthetic** (constructed after the analysis period), not real pre-campaign plans; each campaign has its own targets (attributed gross value / attributed orders / first observed buyers). |
| R15 | CRM profile | Customer attributes are a current snapshot, not inferred as of the purchase date. |
| R16 | Simulated data | Attribution, goals, cost of goods, and cost allocated to campaigns are **synthetic** data; labeled with provenance in the catalog. |
| R17 | Row-level stored data | Coupon status recorded per line item, and shipping fee repeated on every line of an order, is the **source's storage convention**, not an error; handled via R3 and analyzed at the line level, not placed on the exception list. |
| R18 | RFM scoring | R, F, M are each scored in **quintiles 1–5** over customers who purchased in 2019, as of the as-of date (R5): R = 5 most recent, F = 5 most technical orders (R1), M = 5 highest gross value (R2, shipping excluded per R3); ties broken by `customer_id` so reruns are identical (NFR-6). The **RFM Segment** is assigned by an ordered rule table (first match wins, one segment per customer): Champions (R≥4, F≥4, M≥4) · Can't Lose (R≤2 and (F≥4 or M≥4)) · At Risk (R≤2 and (F=3 or M=3)) · Loyal (R≥3, F≥4) · Potential Loyalist (R≥4, F 2–3) · Recent First Buyers (R≥4, F=1; R9) · Needs Attention (R=3) · Hibernating (R=2) · Lost (remaining). "Highest group" = quintile 5, "lowest group" = quintile 1. |

**Reconciliation marks (per `00_Data_Guide`):** 52,924 sales rows · 26,631 technical orders · 1,468 customers · 1,290 order–campaign links · online cost reconciliation discrepancy = 0 · 400 sales lines not reconcilable with the coupon plan (126 of them `Used`; categories Backpacks, Fun, Google, More Bags absent from the plan).

## 7. Features & Functional Requirements (FR)

FRs are numbered globally and stably. Each FR describes a **capability**, not a technology. The approved technology stack is defined in the [Architecture Spine](../03-architecture/ARCHITECTURE-SPINE.md).

### F1 — Simulated Data Sources & Multi-Source Integration
*Fabric capability: Multi-source (DB/API/file).*

- **FR-1** The system builds 7 simulated source systems (S1–S7 from the RFP, comprising 8 source tables) from the sample Excel dataset, matching the correct interface type: Sales, CRM, Product/ERP as **database**; Campaign, Promotion, Advertising Cost as **API**; Finance Cost (part of S5), Tax as **file**.
- **FR-2** Data is loaded in batches from all three source types into the raw storage zone; the raw copy is **never overwritten**, each load is timestamped and versioned.
- **FR-3** After each load, the system reconciles row counts/checksums between the source and the raw copy against the reconciliation marks (section 6), and displays a match/mismatch result (AC01).
- **FR-4** The system distinguishes original business tables from derived tables (e.g., a cost reconciliation table) to avoid loops and double counting.

### F2 — Unified Data & Quality
*Fabric capability: Data Quality. Serves BR14.*

- **FR-5** Create a unified order key per R1; keep the original source code alongside the unified key.
- **FR-6** Standardize date formats and category names per R13, using a mapping table that is lookup-able in the catalog.
- **FR-7** Apply a set of quality rules to each table (completeness, uniqueness, validity, consistency). Each rule has a **Critical** or **Warning** severity level. A table's **quality score** = % of rules passed; status: Green (100% of critical rules pass and ≥ 90% of all rules pass), Amber (100% of critical rules pass but < 90% of all rules pass), Red (any critical rule fails).
- **FR-8** Generate an **exception list** categorized per AC02: transaction codes appearing across multiple customers (1,319 codes), sales rows that cannot be reconciled with the coupon plan (400 lines, 126 `Used`). Category normalization (R13) must not change this baseline. Storage characteristics per R17 are not counted as exceptions.
- **FR-9** UG05 views, filters, and marks the processing status of each exception (new / seen / accepted; "seen" = reviewed).

### F3 — Marketing Metric Catalog & Glossary
*Fabric capability: Catalog + Glossary. Serves BR13.*

- **FR-10** The catalog lists every dataset (raw → unified → serving) with description, owner, source, last refresh, quality score, and provenance label (original / synthetic, R16).
- **FR-11** The glossary defines every marketing metric used in the application, including: English display name, definition, formula, source columns, related rules (section 6), interpretation limitations, owner, last refresh, and quality score (inherited from the source dataset via lineage). Canonical English names for the main metrics: *Attributed Gross Value*, *Attributed Orders*, *Average Order Value*, *Attributed Value / Spend Ratio* (not "ROAS", R7), *Cost per Attributed Order*, *Estimated Contribution*, *First Observed Buyers*, *RFM Segment*.
- **FR-12** From any metric on the dashboard, users can open its glossary definition in one action.
- **FR-13** Keyword search across the catalog and glossary.
- **FR-14** Data columns are tagged with classification labels (e.g., customer identifier, financial); these labels are inputs to access control (F5).

### F4 — Lineage & Automatic Refresh
*Fabric capability: Lineage, Action-triggering metadata. Serves BR16.*

- **FR-15** For every serving metric/table, display a **lineage diagram** as a graph from source → processing steps → metric, with timestamps and data versions (AC05).
- **FR-16** When a cost item or campaign information changes at the source, the system identifies the affected datasets and metrics (based on lineage) and refreshes **only** that part; unrelated metrics keep their values and refresh timestamps unchanged.
- **FR-16a** UG04 can edit a campaign cost item by day in the simulated cost source (a Finance business action); the change is versioned and is the trigger point for FR-16.
- **FR-17** When a dataset's quality check fails at the critical level, the downstream serving dataset is **not updated**, and the dashboard shows a warning "data is using the previous version".
- **FR-18** Change history: users can view the before/after values of a metric affected by a source change.

### F5 — Access Control & Customer Data Protection
*Fabric capability: Policies & Security. Serves BR14, BR08.*

- **FR-19** Each of the UG01–UG06 groups has a demo account; log in once, then **switch roles** instantly via a role selector (demo mode).
- **FR-20** Data view permissions are decided by policy at the platform layer based on role and column labels (FR-14), not merely hidden in the UI. E.g., UG04 can see cost of goods by SKU; UG03 only sees aggregated contribution by campaign, not SKU cost of goods; UG01 cannot see cost of goods; customer identifiers are masked for groups without a business need.
- **FR-21** The customer contact list export function is disabled when consent data is missing (R12), with a notification explaining the reason (AC06).
- **FR-22** UG05 can view the "role × dataset/column" matrix currently in effect.

### F6 — Operational Monitoring
*Fabric capability: Operational monitoring. Serves BR15.*

- **FR-23** An operations page displays the status of each source and each processing step: last run, duration, row count, success/failure.
- **FR-24** UG06 triggers a reload of a source or the entire pipeline from the UI.
- **FR-25** Load/processing errors generate alerts displayed in the application, including the cause and the failing step.
- **FR-26** Measure and display end-to-end refresh time and the response time of analytics pages (AC07).

### F7 — Campaign & Product Analysis (UG01, UG03)

- **FR-27 (BR01)** Campaign overview dashboard: number of orders, number of buying customers, attributed gross value, average order value; filterable by period and campaign.
- **FR-28 (BR02)** Compare campaigns, channels, and periods using the same metric definitions; comparison scope is 5 simulated campaigns.
- **FR-29 (BR03)** Rank best-selling SKUs/categories and trends over time; filterable by campaign.
- **FR-30 (BR06)** Separate first observed buyers (R9) and returning customers by campaign.
- **FR-31 (BR12)** A table evaluating each campaign's goal achievement against **that campaign's own targets** (R14): achievement rate = actual / target. Suggestions: **Continue** (≥ 100%), **Adjust** (70% – < 100%), **Stop** (< 70%); thresholds are displayed next to the result, with a note that targets are retrospective synthetic.

### F8 — Customer Analysis (UG02)

- **FR-32 (BR05)** RFM segmentation as of the as-of date (R5), frequency counted by technical order (R1), scored and segmented per R18; view distribution and customer list by segment.
- **FR-33 (BR08)** Build target customer groups by segment, purchased category, purchase history; save groups for planning; no contact export (FR-21).
- **FR-33a (BR09)** List of customers who previously bought frequently or at high value (F = 5 or M = 5) but haven't returned in a long time (R = 1) as of the as-of date, per R18; filterable by purchased category.

### F9 — Campaign Cost & Finance (UG04, UG03)

- **FR-34 (BR10)** Track budget, allocated cost, unallocated cost by day, Attributed Value / Spend Ratio, Cost per Attributed Order; no double counting (R8, AC04).
- **FR-35 (BR11)** Estimated contribution by campaign = attributed gross value − reference cost of goods − campaign cost; list the items not yet available.

## 8. Acceptance Scenarios by BR

Each BR is accepted when the demo scenario runs correctly on the system built with `docker compose` and the corresponding automated test (NFR-7) passes. "Reconciles" = the number on the application equals the result of an independent query on detailed data per the rules in section 6.

| BR | Role | Demo scenario | Expected result | Fabric capability | Test |
|---|---|---|---|---|---|
| BR01 | UG01 | Open the overview, select a campaign and period | Number of orders, number of buying customers, attributed gross value, average order value reconcile; total attributed orders for the whole period = 1,290 | Lineage (opened from the metric) | T-BR01 |
| BR02 | UG03 | Compare 5 campaigns and channels for the same period | Every column uses the same glossary definition; definitions can be opened from the column header | Glossary | T-BR02 |
| BR03 | UG01 | View top SKU/category, filter by campaign | Ranking reconciles; `Nest`, `Nest-USA`, `Nest-Canada` are shown separately (R13) | Data quality (standardization) | T-BR03 |
| BR05 | UG02 | View the RFM distribution as of 2019-12-31 | Total customers across segments = number of customers who made a purchase; frequency by technical order | Data quality (unified order key) | T-BR05 |
| BR06 | UG01 | View new / returning customers for a campaign | Total new + returning = customers who bought within the campaign; label "first within observed history" | Glossary | T-BR06 |
| BR08 | UG02 | Build a customer group by segment + category, save it; try exporting contacts | Group saves successfully; contact export button is locked with a reason of missing consent | Access control & policy | T-BR08 |
| BR09 | UG02 | Open the list of high-value customers who haven't returned in a long time | Every customer on the list satisfies (F = 5 or M = 5) and R = 1 per R18, and every such customer is listed | Multi-source (Sales + CRM) | T-BR09 |
| BR10 | UG04 | View budget, allocated/unallocated cost by day, Attributed Value / Spend Ratio | Allocated + unallocated = daily online cost (discrepancy 0); budget is shown separately from cost | Multi-source (API + file) | T-BR10 |
| BR11 | UG04 → UG03 | View contribution by campaign as UG04, then switch to UG03 | UG04 sees SKU cost of goods; UG03 only sees the aggregate; the list of items not yet available is shown | Column-label-based access control | T-BR11 |
| BR12 | UG03 | View the goal-achievement table for 5 campaigns | Each campaign is evaluated against its own targets; suggestion matches the FR-31 thresholds | Glossary + synthetic label | T-BR12 |
| BR13 | UG05 | Search "Attributed Value / Spend Ratio" in the catalog | See definition, formula, source columns, owner, note "not ROAS", synthetic label | Catalog + glossary | T-BR13 |
| BR14 | UG05 | View table quality scores and the exception list; view the permission matrix | 1,319 duplicate transaction codes and 400 coupon-mismatch lines (126 `Used`) are listed; score/status per FR-7; permission matrix matches FR-20 | Data quality + policy | T-BR14 |
| BR15 | UG06 | View source statuses; break a simulated source then reload it | An error alert appears with the failing step; reload succeeds, row count matches the reconciliation marks | Operational monitoring | T-BR15 |
| BR16 | UG04 → UG06 | UG04 edits one day's cost for a campaign; UG06 views lineage and change history | Within < 2 minutes (NFR-4), only that campaign's metrics (BR10, BR11, BR12) change; other metrics keep their refresh timestamps; before/after values are viewable | Lineage + action-triggering metadata | T-BR16 |

## 9. Non-Functional Requirements (NFR)

| Code | Requirement | Measurement criteria |
|---|---|---|
| NFR-1 | **Runs locally** | The entire system is built with a single `docker compose` command on a 16GB RAM machine (Docker/WSL2), no cloud services required. |
| NFR-2 | **Resource budget** | Total RAM across services running concurrently ≤ ~12GB, leaving room for the OS. |
| NFR-3 | **Data correctness** | Every aggregate figure reconciles with detailed data per the rules in section 6; an automated reconciliation test suite exists. (AC03) |
| NFR-4 | **Performance** | Measure and report: end-to-end refresh time, partial refresh time (FR-16), analytics page response time. Targets: analytics page responds in < 3 seconds; full refresh < 10 minutes; partial refresh after a source change < 2 minutes (on the sample dataset). |
| NFR-5 | **Benchmark by architecture layer (Big Data context)** | Each layer (storage, processing, catalog/metadata, quality, serving) has at least one alternative solution compared using measured figures (time, resources, integration effort) and a rationale for the choice — per the course requirement. Processing layer: compare two distributed engines on the **same ETL job** (building the unified order + computing RFM) with data replicated ×1, ×10, ×100; the alternative engine only runs during benchmarking, not alongside the demo system (to preserve NFR-2). |
| NFR-6 | **Reproducible** | Re-running the load pipeline multiple times produces the same result; simulated source data can be re-initialized from the sample Excel dataset. |
| NFR-7 | **End-to-end testing** | An automated test suite exists from source → unified data → displayed metric, for each BR. |
| NFR-8 | **Ease of use** | Visual, clear, easy-to-understand UI; a first-time user finds the metrics for their role without guidance. UI language: **English**. |
| NFR-9 | **Demo-level security** | Access rights are enforced at the platform layer (FR-20); demo login credentials are not hard-coded in public source code. |
| NFR-10 | **Full alternative solution** | Compare the Data Fabric architecture with a **traditional warehouse** architecture (ETL straight into one database → dashboard, with no metadata/governance layer) on the same subset of BRs (at minimum BR01, BR10, BR16). Criteria: build effort, traceability, response time to source changes, data correctness. |

## 10. Scope

**In scope:** 14 BRs (section 5), 6 user groups UG01–UG06 (section 4), FR-1…FR-35 plus FR-16a, FR-33a (37 FRs, section 7), NFR-1…NFR-10 (section 9).

**Stretch (if time permits):**
- AI-generated suggestions to help the Marketing Manager decide continue / adjust / stop for a campaign, based on BR12 results and using only governed data.
- BR04 (coupon status comparison), BR07 (post-campaign purchase behavior).
- UG07 Marketing Data Scientist (data access via API).

**Out of scope:** streaming/real-time processing; cross-source queries (data virtualization); cloud deployment; sending real customer contacts; a React UI (later phase, after the Streamlit version is stable); real data beyond the 2019 sample dataset.

## 11. Risks & Assumptions

| Risk | Impact | Mitigation |
|---|---|---|
| Insufficient RAM when running catalog + processing + storage concurrently | Cannot demo on a 16GB machine | Choose a lightweight component at the catalog layer; measure RAM early in week 1 (NFR-2) |
| Effort to connect components (lineage → catalog, labels → policy) exceeds expectations | Schedule delay (the whole project is only 1 month) | Build the minimal end-to-end framework first, then progressively add the BRs |
| Simulated data (attribution, cost of goods, goals) mistaken for real figures | Viewers draw wrong conclusions | Section 6 rules (R14, R16) shown in the glossary, synthetic labels in the catalog, and notes on the dashboard |
| 14 BRs for 4 people in 1 month | Not enough time to accept all of them | Do the RFP's P1 BRs first; fabric BRs (BR13–BR16) done in parallel since they are the foundation for the other BRs |

**Key assumption:** the 2019 sample dataset is sufficient to illustrate every BR; no real personal data is needed; demo viewers are the instructor and the class.

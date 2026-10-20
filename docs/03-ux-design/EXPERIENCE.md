---
name: 'Marketing Data Fabric Demo'
type: experience-md
status: final
created: '2026-09-28'
updated: '2026-09-28'
design: ./DESIGN.md
sources:
  - ../01-requirements/prd.md
  - ../03-architecture/ARCHITECTURE-SPINE.md
---

# Marketing Data Fabric Demo — Experience Spine

*Mockups illustrate; this spine wins on conflict.*

## Foundation

| Item | Decision |
|---|---|
| Form-factor | Desktop web only, demoed on laptop + classroom projector (see Responsive & Platform). No mobile. |
| UI system | Streamlit 1.64, multipage app. Theme via `.streamlit/config.toml`; one CSS layer confined to `app/shell` (DESIGN.md → Colors, Streamlit mapping). This spine specifies only the behavioral delta over Streamlit defaults. |
| Visual identity | `DESIGN.md` (Direction A "Clean SaaS"). Light mode only. |
| Language | English UI (NFR-8). |
| Audience / stakes | Lecturer + class, academic demo, synthetic data, no real PII. |
| Hard contracts | Every metric rendered via `shell.metric(term_id, value, freshness)` (AD-16, FR-12); freshness per displayed value (AD-19); access enforced in Postgres, UI only renders the result (AD-8, FR-20); catalog / glossary / lineage shown inside Streamlit, never OM UI (AD-2); ops pages read `ops_v` only (AD-13); page response < 3 s (NFR-4). |
| Component behavior convention | Badge variants (`badge-fresh/refreshing/stale/synthetic/masked/denied`), `status-chip`, `skeleton`, and `button-disabled` have visual specs in `DESIGN.md → Components`; their behavioral rules live in **State Patterns** below, not restated in Component Patterns. |
| Rule | No showcase / explainer pages. The fabric is proven by working capabilities inside real pages. |

## Information Architecture

**Shell** (every page): login (once, FR-19) · sidebar with {components.role-switcher} pinned top · {components.alert-indicator} (FR-25) · role-filtered nav · stale {components.banner-stale} slot (FR-17) · page timing capture (FR-26, AD-13) · page footnote strip.

**16 pages in 5 nav groups.** ✓ = in nav · ◐ = partial (platform-masked/denied columns) · H = role's home · blank = hidden from nav.

| Group | Page | FR | UG01 | UG02 | UG03 | UG04 | UG05 | UG06 |
|---|---|---|---|---|---|---|---|---|
| Campaigns | Campaign Overview | FR-27 | H | | ✓ | | | |
| | Campaign Comparison | FR-28 | ✓ | | ✓ | | | |
| | Targets | FR-31 | | | H | | | |
| | Products & Categories | FR-29 | ✓ | | | | | |
| | New vs Returning | FR-30 | ✓ | ✓ | | | | |
| Customers | RFM Segments | FR-32 | | H | | | | |
| | Audience Builder | FR-33, FR-21 | ✓ | ✓ | | | | |
| | Win-back | FR-33a | | ✓ | | | | |
| Finance | Budget & Spend | FR-34, FR-16a | | | ✓ (read) | H (edit) | | |
| | Contribution | FR-35 | | | ◐ | ✓ | | |
| Data trust | Catalog & Glossary | FR-10..13 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| | Lineage | FR-15 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| | Data Quality & Exceptions | FR-7..9 | | | | | H | |
| | Access Matrix | FR-22 | | | | | ✓ | |
| Operations | Pipeline Status | FR-23..26 | | | | | | H |
| | Change History | FR-18 | ✓ | | ✓ | ✓ | | ✓ |

Matrix source: memlog homes + UG03 partial on Contribution; remaining cells derived from PRD §5 "Nhóm dùng" and BR13 "(+ mọi nhóm)", BR16 "(+ UG01, UG04)"; Change History, Lineage, Catalog & Glossary, Audience Builder and Campaign Overview cells confirmed 2026-09-28 (memlog).

| Rule | Behavior |
|---|---|
| Homes | After login and after every role switch with no permitted current page, land on the role's H page. |
| Hidden-nav | Pages outside a role are **not in nav** (not shown-locked). Implemented with `st.navigation` built from the role's page list, so a hidden page is unreachable by URL too. |
| Access inside pages | Denied/masked data is demonstrated inside permitted pages via platform mask/deny (AD-8) — e.g. UG03 on Contribution sees campaign aggregate, SKU cost "not permitted for role" (BR11). |
| Two paths to metadata | Metric-first: ⓘ on any metric → {components.dialog} (definition). Dataset-first: Catalog & Glossary and Lineage pages. |
| Modal depth | One level. Dialog never opens another dialog. |

## Voice and Tone

Short, precise, neutral English. Buttons are verbs. Every block/disable message states its reason. Metric names are the glossary `display_name` verbatim (FR-11): *Attributed Gross Value*, *Attributed Orders*, *Attributed Buyers*, *Average Order Value*, *Attributed Value / Spend Ratio*, *Cost per Attributed Order*, *Campaign Budget*, *Allocated Spend*, *Unallocated Spend*, *Estimated Contribution*, *First Observed Buyers*, *RFM Segment*.

| Do | Don't |
|---|---|
| "Attributed Gross Value" | "Revenue", "Sales" |
| "Attributed Value / Spend Ratio" | "ROAS" |
| "Contact export disabled — no marketing consent data (R12)" | "Export unavailable" |
| "Using previous version — quality check failed on `unified/orders`" | "Data may be outdated" |
| "not permitted for role" | "Access denied!", "Error 403" |
| "Change saved · partial refresh started" | "Success! 🎉" |
| "Save change", "Reload source", "Save audience", "Mark accepted" | "OK", "Submit", "Go" |
| "First within observed history" (R9 note via shell) | "New customers" without qualifier |

**Number & date format** (all pages, all roles):

| Kind | Format | Example |
|---|---|---|
| Counts / money | Thousands separator, no currency symbol; one "currency unverified" footnote per page (R10) | 154,800 |
| Ratios | 2 decimals + × | 3.42× |
| Percents | 1 decimal | 87.5% |
| Dates | ISO | 2019-12-31 |
| Times (freshness) | 24h HH:MM | Refreshed 10:42 |

## Component Patterns

Behavioral. Visual specs live in `DESIGN.md → Components`.

| Component | Use | Behavioral rules |
|---|---|---|
| **metric-card** (`shell.metric`) | Every metric on every page | Only rendering path for metrics (AD-16). Draws label, value, freshness badge (`max(_refreshed_at)` of the rows behind that value, AD-19), synthetic badge (term has Synthetic ancestor, AD-2), stale badge (from `status()`), notes from term `notes`. `currency_unverified` is collected into the page {components.footnote-strip} once, not repeated per card — `shell.metric` renders the note itself, consistent with AD-16. ⓘ opens {components.dialog} (definition). Unknown `term_id` fails e2e test. |
| **table** | Lists, comparisons, triage | Metric column headers carry ⓘ → same {components.dialog} (BR02). Masked cells {components.badge-masked}; `<col>__denied` or PG `permission denied` → {components.badge-denied}. Sortable; numeric right-aligned. |
| **chart** | Trends, comparisons | Hover tooltip; titled; legend + direct labels (≤4 series); every chart has a "Table view" toggle showing the same data. Campaign color fixed by slot `{colors.series-1}`..`{colors.series-5}`. |
| **dialog** (definition) (`st.dialog`) | ⓘ on metric card / column header | Tabs **Definition · Lineage · Quality** (FR-12 + FR-15 in one action). Definition: display name, definition, formula, source columns, rules R-xx, limitations, owner, synthetic label, cautions (e.g. "Not ROAS"). Lineage: {components.lineage-graph} source → steps → metric with time + version. Quality: dataset score + status Green/Amber/Red (FR-7), last refresh. Esc / close returns to the page with filters intact. Mock: [mockups/key-campaign-overview.html](mockups/key-campaign-overview.html). |
| **filter-bar** | Top of analytics pages | Period + Campaign (+ page-specific). Applies on change (no Apply button). Filters persist per page in session, including across role switch. |
| **role-switcher** | Sidebar top | Instant switch (FR-19): changes PG connection (AD-8), re-renders nav; stays on current page if permitted, else goes to new home with toast "Switched to <Role> (UGxx)". Caption always shows current role code. |
| **alert-indicator** | Shell | Count of open alerts (`ops_v` alerts, FR-25). Visible to UG05 (quality check failures) and UG06 (pipeline failures) only. Hidden entirely when the count is 0. Click → Pipeline Status filtered to failed runs (UG06) or Data Quality & Exceptions filtered to failures (UG05). |
| **banner-stale** | Any page with a stale value | Names the failed dataset and says the page is "Using previous version". One banner per page even if several datasets are stale (lists them). Disappears when the gated dataset is written successfully (AD-19). |
| **spend edit form** | Budget & Spend, UG04 only | `st.form`: campaign, date, allocated spend value. Save → mock API (AD-5). 4xx → reason inline under the offending field, form values kept. Success → {components.toast} "Change saved · partial refresh started"; {components.progress-strip} appears inline below the form. Not rendered for other roles (UG03 sees the table read-only). Mock: [mockups/key-budget-spend.html](mockups/key-budget-spend.html). |
| **progress-strip** | Budget & Spend, inline below the spend edit form after a successful save | "Refreshing N datasets · m:ss" with per-dataset steps queued → running → done; elapsed timer counts up. While active, every affected metric card — on this page and on Contribution / Targets — shows {components.badge-refreshing} "Refreshing…" in place of its freshness badge, value unchanged, then flips to {components.badge-fresh} independently as each dataset completes; this is never {components.badge-stale} (Stale is gated/quality-failure only, AD-19). On completion, replaced by "N metrics changed — see Change History"; presenter switches role to UG06 for full Pipeline Status detail. |
| **allocated/unallocated spend bar** ({components.spend-stack-bar}) | Budget & Spend | Daily stacked bar per {components.spend-stack-bar}: Allocated segment `{colors.accent}`; Unallocated segment `{colors.series-neutral}` (never a campaign `series-n` color or a status color), 2px `{colors.surface}` gap between segments. Same chart rules apply (title, legend + direct labels, hover tooltip, table-view toggle). |
| **audience builder** | Audience Builder | Criteria: RFM segment, purchased category, purchase history. Live count of matching customers. "Save audience" stores it for planning (FR-33). "Export contacts" is always {components.button-disabled} with reason "Contact export disabled — no marketing consent data (R12)" shown beneath (FR-21, `can_export()`). Customer IDs masked per role. |
| **win-back list** | Win-back | Customers with (F = 5 or M = 5) and R = 1 at 2019-12-31 (FR-33a, PRD R18); filter by purchased category. "Build audience from this list" button prefills Audience Builder. |
| **exceptions triage** | Data Quality & Exceptions (FR-8, FR-9) | Filter by class (e.g. transaction ID shared across customers — 1,319) and status. Per row status {components.status-chip} new / seen / accepted; change via row select + "Mark seen" / "Mark accepted" (multi-select allowed). Status keyed by stable `exception_id`; vanished IDs show "resolved at source" (AD-7). R17 storage traits never listed. |
| **DQ scoreboard** | Data Quality & Exceptions | Per dataset: score %, Green/Amber/Red chip (FR-7), failing rules with severity Critical/Warning. |
| **access matrix** | Access Matrix (FR-22) | Role × dataset/column grid read from `ops.policy_effective`; cells allow / mask / deny with icon + word. Read-only. |
| **pipeline status** | Pipeline Status (FR-23..26) | Per source and step: last run, duration, rows in/out, status chip queued → running → success / failed / gated, failing step + cause. While any run is active, auto-refresh every 5 s via `st.fragment(run_every=5)`; stops when none active. Filter by `event_id` (deep link) shows the partial-refresh run with elapsed timer vs "2 min target" (NFR-4). "Reload source" / "Reload all" (FR-24) with confirm. Shows end-to-end and partial refresh times and page response times (FR-26). Mock: [mockups/key-pipeline-status.html](mockups/key-pipeline-status.html). |
| **change history** | Change History (FR-18) | Per event: metric, campaign, old → new, delta. Each metric row carries a row-label ⓘ opening the same {components.dialog} (definition) as a metric-card ⓘ. Summary line "N metrics changed · M unchanged kept refresh time HH:MM". Filterable by `event_id`. Mock: [mockups/key-change-history.html](mockups/key-change-history.html). |
| **lineage-graph** | Dialog Lineage tab, Lineage page | Read via `fabric_control`; click node → side detail (dataset id, refreshed time, version, quality). Stale nodes marked. |
| **catalog search** | Catalog & Glossary (FR-13) | Keyword search across datasets and terms; results show provenance (original / synthetic), owner, last refresh, quality. Selecting a term opens the {components.dialog} (definition). Zero-match state: State Patterns → Surface-specific. |
| **toast** | Save, role switch, reload | Auto-dismiss (Streamlit default); never the only place an error is shown. |

## State Patterns

Applies to **every metric, table and chart** (B2).

| State | Treatment |
|---|---|
| Loading | Gray {components.skeleton} shaped like the final element. No centered spinner. |
| Fresh | {components.badge-fresh} "Refreshed HH:MM" (per value, AD-19). |
| Refreshing | {components.badge-refreshing} "Refreshing…" (icon + text); affected value is kept unchanged (previous value) until its dataset completes, then flips to {components.badge-fresh} "Refreshed HH:MM". No page banner. Distinct from Stale — Stale is gated/quality-failure only (AD-19); an in-flight refresh is never shown as Stale. |
| Stale | {components.badge-stale} "Using previous version" on each affected value + page {components.banner-stale} naming the failed dataset (FR-17). Gated/quality-failure only (AD-19) — never used for a normal in-flight refresh (see Refreshing). |
| Synthetic | {components.badge-synthetic} "Synthetic" (R16). |
| Masked | Value like `C****42` + 🔒 ({components.badge-masked}). |
| Denied | Italic gray "not permitted for role" ({components.badge-denied}); same text for `__denied` flag and PG permission error. |
| Empty | Explanatory sentence + clear-filter hint, e.g. "No attributed orders for CMP-03 in this period. Clear the Campaign filter to see all." |
| Error | {components.banner-error} red box with cause; never swallowed. |

Surface-specific:

| Surface | State | Treatment |
|---|---|---|
| Shell (login) | Login failure | Inline error "Invalid demo credentials"; no role hint. |
| Spend edit form | Validation / 4xx | Inline under field in `{colors.danger}`; values kept; Save re-enabled. |
| Spend edit form | Submitting | Save disabled, "Saving…". |
| Pipeline Status | Run active | Auto-refresh 5 s, elapsed timer; target overrun shown as warning chip "Over 2 min target". |
| Pipeline Status | Failed | status-chip danger + step + cause (FR-25); alert-indicator count increments. |
| Change History | No events yet | "No source changes recorded yet." |
| Audience Builder | Zero matches | "No customers match these criteria." + hint to widen segment. |
| Win-back | Zero matches | "No lapsed high-value customers for this filter." + hint to widen filter. |
| Catalog & Glossary | Zero matches | "No datasets or terms match '<q>'." |
| Exceptions | Filter empty | Empty pattern; "resolved at source" rows remain visible under status filter. |
| Role switch | Current page not permitted | Redirect to new home + toast. |

## Interaction Primitives

- Pointer-first, fully keyboard-operable (Streamlit native widgets; Tab order = reading order; Esc closes dialog).
- Filters apply immediately on change; forms (`st.form`) only for writes (spend edit, audience save).
- One action to a definition: ⓘ on any metric or metric column header (FR-12).
- Deep links via query params: `?event_id=` on Pipeline Status and Change History.
- No auto-refresh anywhere except Pipeline Status during an active run.
- Writes: only spend edit (UG04), audience save (UG02/UG01), exception status (UG05), reload (UG06). Destructive-ish reloads confirm once.
- Each page must render < 3 s (NFR-4); shell records timing (AD-13).
- Banned: shown-locked nav items, nested dialogs, centered spinners, hover-only information, dual-axis charts.

## Accessibility Floor

Behavioral. Visual contrast lives in `DESIGN.md → Colors`.

- WCAG AA contrast for all text pairs (verified ratios in DESIGN.md).
- Status never color-only: icon + text on every badge, chip, banner (projector color shift).
- Full keyboard operability; visible focus ring `{colors.accent}`.
- Charts: title, labeled axes, legend, table-view toggle; aqua/yellow series always direct-labeled or table-backed.
- Each campaign keeps one fixed color across all pages.
- Disabled controls always state the reason in visible text, not tooltip.
- Body text ≥15px (`{typography.body}`), KPI `{typography.kpi-value}`.

## Key Flows

### Flow 1 — Linh (UG01 Marketing Analyst), Monday weekly report

Mock: [mockups/key-campaign-overview.html](mockups/key-campaign-overview.html).

Linh needs last period's campaign numbers and has to be able to defend them.

1. Logs in → lands on **Campaign Overview**. Skeletons resolve into four metric-cards: *Attributed Orders*, *Attributed Buyers*, *Attributed Gross Value*, *Average Order Value*, each "Refreshed HH:MM" + "Synthetic".
2. Sets filter-bar Period and Campaign; values update in place.
3. Clicks ⓘ on *Attributed Orders* → {components.dialog} (definition), Definition tab (formula, source columns, R1/R6, "attributed ≠ incremental").
4. **Climax:** switches to the Lineage tab — the number traces back through unified orders to the Sales DB and Attribution API sources with time and version. She can say where 1,290 comes from.
5. Opens **Campaign Comparison** (same definitions), **Products & Categories** (Nest, Nest-USA, Nest-Canada separate), **New vs Returning** (First Observed Buyers with R9 note).
6. **Failure path:** a stale source → {components.banner-stale} names it and stale badges appear on the affected metric-cards; Linh reports with "Using previous version" visible.

Lands: BR01 (total attributed orders = 1,290), BR02, BR03, BR06.

### Flow 2 — Minh (UG03 Marketing Manager), Friday stop/keep decision

Minh must decide which of the 5 campaigns to continue, adjust or stop.

1. Lands on **Targets**: one shared achievement ruler, achievement = actual / target on each campaign's own target metric (R14), thresholds shown on the ruler (≥100% Continue, 70–<100% Adjust, <70% Stop), footnote "Goals were set after the fact for this demo", Synthetic badge.
2. Opens ⓘ on the target column header to confirm the definition.
3. Opens **Budget & Spend** (read-only) for *Attributed Value / Spend Ratio* and *Cost per Attributed Order*.
4. Opens **Contribution**: *Estimated Contribution* per campaign visible; SKU reference cost column shows "not permitted for role".
5. **Climax:** Summer Drinkware sits exactly on the Stop line at 70%, Adjust, with its own target and threshold beside it — Minh decides from one governed table, and sees that cost detail he may not see is hidden by the platform, not the page.
6. **Failure path:** if a target's source dataset is stale, Targets shows {components.banner-stale} naming it; that campaign's recommendation still displays, tagged with a stale badge, and Minh defers the stop/keep decision until it refreshes.

Lands: BR12, BR11 (UG03 aggregate only), BR02.

### Flow 3 — Hà (UG04 Finance Controller), catches a wrong spend entry — **demo climax**

Mock: [mockups/key-budget-spend.html](mockups/key-budget-spend.html) (spend edit form); [mockups/key-change-history.html](mockups/key-change-history.html) (climax).

Hà, reconciling daily spend, has a corrected invoice for one campaign-day (CMP19_05, 2019-11-12).

1. Lands on **Budget & Spend**: *Campaign Budget* shown separately from spend; *Allocated Spend* + *Unallocated Spend* = online spend per day (difference 0).
2. Has a corrected invoice on CMP19_05 2019-11-12; opens the spend edit form (campaign, date, value) and enters the corrected allocated spend.
3. Enters an invalid value → mock API 4xx; reason appears inline under the field; values kept.
4. Corrects and clicks "Save change" → toast "Change saved · partial refresh started"; {components.progress-strip} appears below the form: "Refreshing N datasets for {campaign}, {date}" plus an m:ss timer, one step per affected dataset (business label, dataset id below), steps queued → running → done. The affected metric cards switch to {components.badge-refreshing} "Refreshing…" (previous value kept) — not Stale (AD-19).
5. Strip completes → "N metrics changed — see Change History"; presenter switches to UG06 for full **Pipeline Status** detail (steps queued → running → success, elapsed timer vs 2-min target).
6. **Climax:** **Change History** shows a summary line, a lineage flow of the refreshed datasets, and a table of old → new and delta for that campaign's metrics only, with "N metrics changed · M unchanged kept refresh time HH:MM"; back on Budget & Spend / Contribution / Targets, only that campaign's badges flip from {components.badge-refreshing} to {components.badge-fresh} with a new refresh time.
7. **Failure path:** an invalid spend value triggers the inline 4xx in step 3 before save ever starts; if the partial-refresh run itself fails after save, Pipeline Status shows a failed status-chip and cause, and the alert-indicator increments.

Lands: BR16 (< 2 min, only BR10/BR11/BR12 metrics of that campaign change, before/after visible), BR10.

### Flow 4 — Tuấn (UG06 Data Ops), source failure alert → reload

Mock: [mockups/key-pipeline-status.html](mockups/key-pipeline-status.html).

1. Lands on **Pipeline Status**; the alert-indicator shows 1.
2. Clicks it → failed run for one source: failed step and cause (FR-25).
3. Dependent pages keep previous values; where a DQ gate blocked the write, pages show banner-stale naming the dataset.
4. Clicks "Reload source" → confirm → run queued → running → success, auto-refresh 5 s.
5. **Climax:** reconciliation for the reloaded source shows row counts matching the baseline (FR-3); alert clears.
6. Opens the standalone **Lineage** page for the reloaded source dataset and confirms its downstream datasets (raw → unified → mart) show the new refreshed time and version.
7. **Failure path:** if the reload itself fails, the alert stays open, the failed step and cause are shown again, and Tuấn retries "Reload source".

Lands: BR15 (fault injected outside the app via `make break-source SRC=<source>`; no in-app break button).

### Flow 5 — Mai (UG02 CRM), win-back audience prep

1. Lands on **RFM Segments** at 2019-12-31: distribution; segment totals = buyers.
2. Opens **Win-back**: high-F/M, low-R customers; filters by purchased category; Customer IDs masked.
3. Builds the audience in **Audience Builder** (segment + category + history), live count, "Save audience".
4. **Climax:** reaches for "Export contacts" — it is disabled with "Contact export disabled — no marketing consent data (R12)" under it; the audience stays saved for planning.
5. **Failure path:** if the Audience Builder filters yield zero customers, an empty state shows "No customers match these criteria." + a clear-filter hint; "Export contacts" stays disabled with its consent reason regardless.

Lands: BR05, BR09, BR08.

### Flow 6 — Quân (UG05 Data Steward), exceptions review + access matrix

1. Lands on **Data Quality & Exceptions**: dataset scores with Green/Amber/Red.
2. Filters exceptions to transaction IDs shared across customers → 1,319 rows.
3. Selects rows → "Mark seen" / "Mark accepted"; chips update.
4. Searches "Attributed Value / Spend Ratio" in **Catalog & Glossary**: definition, formula, source columns, owner, "Not ROAS", Synthetic.
5. **Climax:** opens **Access Matrix** — role × column cells show UG03 deny on SKU cost, UG01 deny on cost, customer ID mask for non-CRM roles, read from what the platform actually enforces.
6. **Failure path:** marking an exception whose `exception_id` has since vanished shows "resolved at source" instead of updating status (AD-7).

Lands: BR14, BR13.

## Demo Script

~15 min, one laptop + projector, role switcher drives the story; minute splits below.

| # | Min | Role | Page / action | Proves |
|---|---|---|---|---|
| 1 | 0–2 | UG01 | Campaign Overview → ⓘ dialog Definition + Lineage | BR01, catalog/glossary, lineage |
| 2 | 2–4 | UG03 | Targets → Continue/Adjust/Stop | BR12 |
| 3 | 4–6 | UG04 | Budget & Spend → edit one day's spend (show one 4xx first, then inline progress strip + Refreshing badges on affected metrics) | BR10, FR-16a |
| 4 | 6–9 | UG06 | Pipeline Status (event) → Change History — **CLIMAX: partial refresh (affected metrics show Refreshing, not Stale), only that campaign changes, others keep refresh time** | BR16 |
| 5 | 9–10 | UG03 | Contribution → SKU cost "not permitted for role" | BR11, policy |
| 6 | 10–11 | UG02 | Audience Builder → export locked with reason | BR08 |
| 7 | 11–13 | UG05 | Data Quality & Exceptions (1,319) → Access Matrix | BR14 |
| 8 | 13–15 | UG06 | Presenter runs `make break-source SRC=<source>` → alert → Reload → counts match | BR15 |

Pre-demo: full refresh done, all badges fresh, alert count 0, fault toggle off.

## Mock Coverage

4 of the 16 pages have HTML mocks in `mockups/`: Campaign Overview (+ dialog, definition), Budget & Spend, Pipeline Status, Change History — the highest-stakes, most state-heavy surfaces (demo climax + trust surfaces). The other 12 pages are specified by `DESIGN.md` and this experience spine without separate HTML mocks.

## Responsive & Platform

| Target | Behavior |
|---|---|
| Laptop + projector, 1366×768 baseline | `layout="wide"`; KPI row ≤4 cards stays one line; sidebar expanded. |
| Larger desktop | Same layout, more whitespace; no extra columns. |
| Mobile / tablet | Out of scope; not tested. |

Light mode only; browser zoom 100% during demo.

## Inspiration & Anti-patterns

- **Chosen:** Direction A "Clean SaaS" (Stripe/Linear dashboards) — see DESIGN.md.
- **Rejected:** Direction B editorial report, Direction C control room (navy sidebar); C hybrid not taken.
- **Rejected:** shown-locked nav items; OM UI for end users (AD-2); centered spinners; showcase/explainer pages; dual-axis charts; magenta series and default orange+yellow adjacency (CVD fail).

## Open Questions

None — all prior open questions were resolved into the decisions recorded in this document.

---
name: 'Marketing Data Fabric Demo'
type: design-md
status: final
created: '2026-09-28'
updated: '2026-09-28'
sources:
  - ../01-requirements/prd.md
  - ../03-architecture/ARCHITECTURE-SPINE.md
description: 'Clean SaaS visual layer for a Streamlit 1.64 marketing analytics app (6 demo roles). Light mode only, projector-legible. Theme via .streamlit/config.toml + one CSS layer confined to app/shell.'
colors:
  # --- Canvas & ink (Direction A "Clean SaaS") ---
  canvas: '#F6F7F9'            # page background (main area)
  surface: '#FFFFFF'           # cards, dialogs, tables, inputs
  sidebar-bg: '#FBFBFC'
  surface-sunken: '#EEF0F3'    # footnote strip, synthetic badge fill, skeleton base
  surface-code: '#F1F2F5'      # inline code / column names in glossary
  info-icon-bg: '#EEF1F5'
  text: '#1A1F29'              # primary ink
  text-secondary: '#3A4150'    # nav items, synthetic badge text
  muted: '#5B6472'             # labels, captions, freshness meta
  border: '#E4E7EC'            # hairlines, card + table borders
  # --- Accent (single) ---
  accent: '#2F5BEA'            # primaryColor: buttons, focus ring, links, selected tab
  accent-strong: '#1F3FAE'     # active nav text, tag text on tint
  accent-tint: '#E8EEFE'       # active nav fill, selected row
  on-accent: '#FFFFFF'
  # --- Status (reserved: never a chart series) ---
  success: '#146C2E'
  success-tint: '#E5F3E9'
  warning: '#92400E'
  warning-tint: '#FCEEDC'
  warning-border: '#F3D9B8'    # stale metric-card border
  danger: '#99180C'
  danger-tint: '#FBE7E6'
  neutral-status: '#5B6472'    # queued / new / denied text
  neutral-status-tint: '#EEF0F3'
  # --- Campaign categorical series (fixed order; color follows campaign, never rank) ---
  series-1: '#2a78d6'          # blue
  series-2: '#d95926'          # orange
  series-3: '#1baf7a'          # aqua   (contrast WARN -> legend + direct labels required)
  series-4: '#4a3aa7'          # violet
  series-5: '#eda100'          # yellow (contrast WARN -> legend + direct labels required)
  series-neutral: '#848B97'    # unallocated / non-entity bar, 3.43:1 on white
  # --- Sequential (single blue ramp, 3 stops lifted from accent family) ---
  seq-low: '#E8EEFE'
  seq-mid: '#7D9AF2'
  seq-high: '#1F3FAE'
typography:
  # System sans stack (Direction A). Body >= 15px for projector legibility.
  font-sans:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
  font-mono:
    fontFamily: 'ui-monospace, Consolas, monospace'
  page-title:
    fontFamily: '{typography.font-sans.fontFamily}'
    fontSize: 28px
    fontWeight: '700'
    lineHeight: '1.25'
    letterSpacing: -0.01em
  section-title:
    fontFamily: '{typography.font-sans.fontFamily}'
    fontSize: 19px
    fontWeight: '700'
    lineHeight: '1.3'
  body:
    fontFamily: '{typography.font-sans.fontFamily}'
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  body-strong:
    fontFamily: '{typography.font-sans.fontFamily}'
    fontSize: 16px
    fontWeight: '600'
    lineHeight: '1.5'
  label:
    fontFamily: '{typography.font-sans.fontFamily}'
    fontSize: 15px
    fontWeight: '600'
    lineHeight: '1.35'
  kpi-value:
    fontFamily: '{typography.font-sans.fontFamily}'
    fontSize: 40px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.01em
  table-cell:
    fontFamily: '{typography.font-sans.fontFamily}'
    fontSize: 15px
    fontWeight: '400'
    lineHeight: '1.4'
  table-header:
    fontFamily: '{typography.font-sans.fontFamily}'
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1.3'
    letterSpacing: 0.02em
  badge:
    fontFamily: '{typography.font-sans.fontFamily}'
    fontSize: 14px
    fontWeight: '700'
    lineHeight: '1.2'
  caption:
    fontFamily: '{typography.font-sans.fontFamily}'
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.4'
  masked-value:
    fontFamily: '{typography.font-mono.fontFamily}'
    fontSize: 16px
    fontWeight: '600'
rounded:
  xs: 5px        # inline code, chart bar tops
  sm: 8px        # inputs, filters, buttons, role switcher, nav items, banners
  md: 12px       # cards, tables, dialogs
  full: 9999px   # badges, status chips
spacing:
  '1': 4px
  '2': 8px
  '3': 12px
  '4': 16px
  '5': 20px
  '6': 24px
  '7': 32px
  gutter: 16px          # gap between cards / grid columns
  card-padding: 20px
  page-padding: 32px
  sidebar-width: 244px  # close to Direction A 236px; Streamlit sidebar width set in shell CSS
components:
  metric-card:
    background: '{colors.surface}'
    border: '1px solid {colors.border}'
    radius: '{rounded.md}'
    padding: '{spacing.card-padding}'
    shadow: '0 1px 2px rgba(16,24,40,0.04), 0 2px 8px rgba(16,24,40,0.06)'
    label: '{typography.label}'
    label-color: '{colors.muted}'
    value: '{typography.kpi-value}'
    value-color: '{colors.text}'
    info-button-bg: '{colors.info-icon-bg}'
    info-button-color: '{colors.muted}'
    stale-border: '1px solid {colors.warning-border}'
    stale-value-color: '{colors.warning}'
  badge-fresh:
    background: '{colors.success-tint}'
    foreground: '{colors.success}'
    radius: '{rounded.full}'
    type: '{typography.badge}'
    icon: 'check_circle'
  badge-refreshing:
    background: '{colors.accent-tint}'
    foreground: '{colors.accent-strong}'
    radius: '{rounded.full}'
    type: '{typography.badge}'
    icon: 'sync'
  badge-stale:
    background: '{colors.warning-tint}'
    foreground: '{colors.warning}'
    radius: '{rounded.full}'
    type: '{typography.badge}'
    icon: 'warning'
  badge-synthetic:
    background: '{colors.surface-sunken}'
    foreground: '{colors.text-secondary}'
    radius: '{rounded.full}'
    type: '{typography.badge}'
    icon: 'science'
  badge-masked:
    background: 'transparent'
    foreground: '{colors.text}'
    type: '{typography.masked-value}'
    icon: 'lock'
  badge-denied:
    background: 'transparent'
    foreground: '{colors.muted}'
    type: '{typography.body}'
    fontStyle: 'italic'
    icon: 'lock'
  status-chip:
    radius: '{rounded.full}'
    type: '{typography.badge}'
    success: { background: '{colors.success-tint}', foreground: '{colors.success}' }
    warning: { background: '{colors.warning-tint}', foreground: '{colors.warning}' }
    danger: { background: '{colors.danger-tint}', foreground: '{colors.danger}' }
    info: { background: '{colors.accent-tint}', foreground: '{colors.accent-strong}' }
    neutral: { background: '{colors.neutral-status-tint}', foreground: '{colors.neutral-status}' }
  banner-stale:
    background: '{colors.warning-tint}'
    foreground: '{colors.warning}'
    border-left: '4px solid {colors.warning}'
    radius: '{rounded.sm}'
    icon: 'warning'
  banner-error:
    background: '{colors.danger-tint}'
    foreground: '{colors.danger}'
    border-left: '4px solid {colors.danger}'
    radius: '{rounded.sm}'
    icon: 'error'
  footnote-strip:
    background: '{colors.surface-sunken}'
    foreground: '{colors.muted}'
    border: '1px solid {colors.border}'
    radius: '{rounded.sm}'
    type: '{typography.caption}'
  progress-strip:
    background: '{colors.accent-tint}'
    foreground: '{colors.accent-strong}'
    border: '1px solid {colors.border}'
    radius: '{rounded.sm}'
    type: '{typography.caption}'
    step-done-icon: 'check_circle'
  dialog:
    background: '{colors.surface}'
    radius: '{rounded.md}'
    padding: '{spacing.6}'
    title: '{typography.section-title}'
    tab-active: '{colors.accent}'
    field-key: '{typography.caption}'
    code-bg: '{colors.surface-code}'
  table:
    background: '{colors.surface}'
    border: '1px solid {colors.border}'
    radius: '{rounded.md}'
    header: '{typography.table-header}'
    header-color: '{colors.muted}'
    cell: '{typography.table-cell}'
    row-divider: '1px solid {colors.border}'
    row-selected: '{colors.accent-tint}'
    numeric-align: 'right, tabular-nums'
  button-primary:
    background: '{colors.accent}'
    foreground: '{colors.on-accent}'
    radius: '{rounded.sm}'
    type: '{typography.body-strong}'
  button-secondary:
    background: '{colors.surface}'
    foreground: '{colors.text}'
    border: '1px solid {colors.border}'
    radius: '{rounded.sm}'
  button-disabled:
    background: '{colors.surface-sunken}'
    foreground: '{colors.muted}'
    radius: '{rounded.sm}'
    icon: 'lock'
  form-field:
    background: '{colors.surface}'
    border: '1px solid {colors.border}'
    focus-ring: '2px solid {colors.accent}'
    error-border: '1px solid {colors.danger}'
    error-text: '{colors.danger}'
    radius: '{rounded.sm}'
  filter-bar:
    control-background: '{colors.surface}'
    control-border: '1px solid {colors.border}'
    radius: '{rounded.sm}'
    gap: '{spacing.3}'
  sidebar:
    background: '{colors.sidebar-bg}'
    border-right: '1px solid {colors.border}'
    width: '{spacing.sidebar-width}'
    nav-item: '{typography.body}'
    nav-item-color: '{colors.text-secondary}'
    nav-active-bg: '{colors.accent-tint}'
    nav-active-fg: '{colors.accent-strong}'
    group-label: '{typography.caption}'
  role-switcher:
    background: '{colors.surface}'
    border: '1px solid {colors.border}'
    radius: '{rounded.sm}'
    type: '{typography.body-strong}'
    caption: '{typography.caption}'
    caption-role-code: '{colors.accent-strong}'
  alert-indicator:
    background: '{colors.danger-tint}'
    foreground: '{colors.danger}'
    radius: '{rounded.full}'
    icon: 'notifications'
  toast:
    note: 'Streamlit st.toast default; icon carries status'
  skeleton:
    background: '{colors.surface-sunken}'
    radius: '{rounded.sm}'
  lineage-graph:
    node-background: '{colors.surface}'
    node-border: '1px solid {colors.border}'
    node-radius: '{rounded.sm}'
    node-focus: '2px solid {colors.accent}'
    edge: '{colors.muted}'
    node-stale-border: '2px solid {colors.warning}'
  chart:
    series: ['{colors.series-1}', '{colors.series-2}', '{colors.series-3}', '{colors.series-4}', '{colors.series-5}']
    sequential: ['{colors.seq-low}', '{colors.seq-mid}', '{colors.seq-high}']
    grid: '{colors.border}'
    axis-label: '{typography.caption}'
  spend-stack-bar:
    allocated: '{colors.accent}'
    unallocated: '{colors.series-neutral}'
    segment-gap: '2px solid {colors.surface}'
    legend: true
    direct-labels: true
    table-view: '{components.chart}'
---

*Mockups illustrate; this spine wins on conflict.*

## Brand & Style

A university data-fabric demo that has to earn a lecturer's trust in 15 minutes on a classroom projector. The posture is **trustworthy · clear · calm**: numbers first, and the trust signals that make them believable (freshness, stale, synthetic, definition) sit right beside each number but are always quieter than it. Register: Stripe/Linear-style clean SaaS — white and light-gray canvas, one confident blue, roomy spacing, 12px cards, soft shadows, system sans. No logo, no illustration, no explainer or showcase pages; the fabric is proven by working capabilities.

Foundation is **Streamlit 1.64**. Tokens are split across two layers (see table in Colors). Pages never add their own CSS; only `app/shell` owns the CSS layer (metric card, badges, banner, lineage, sidebar/role-switcher polish). Light mode only (lit room + projector).

Visual reference: [mockups/direction-a-clean-saas.html](mockups/direction-a-clean-saas.html) — Campaign Overview with KPI row, chart + by-campaign table, footnote strip, glossary panel, masked/denied samples. Editorial-report and dark control-room directions were considered but not selected. Where the mock and this spine differ (e.g. mock's sub-15px labels, red "denied" text, per-card "currency unverified" note), **this spine wins**.

## Colors

| Group | Tokens | Use | Never |
|---|---|---|---|
| Canvas & ink | `canvas`, `surface`, `sidebar-bg`, `surface-sunken`, `text`, `text-secondary`, `muted`, `border` | Page, cards, text hierarchy, hairlines | Tinted/gradient page backgrounds |
| Accent | `accent`, `accent-strong`, `accent-tint`, `on-accent` | Primary button, focus ring, links, selected tab, active nav | Status meaning; a chart series |
| Status | `success*`, `warning*`, `danger*`, `neutral-status*` | Badges, status chips, banners, form errors | Chart series; decoration; ever alone without icon + text |
| Campaign series | `series-1`..`series-5` | One fixed color per campaign slot (CMP-01..05) on every page | Re-ordering by rank; text color |
| Non-entity | `series-neutral` | Unallocated / non-entity segment in stacked bars (e.g. `spend-stack-bar`) | Campaign series; status meaning |
| Sequential | `seq-low` → `seq-high` | Single-hue magnitude (e.g. RFM heat) | Mixing with status colors |

**Contrast (WCAG, on stated background):** `text`/`surface` 16.5:1 · `text`/`canvas` 15.4:1 · `muted`/`surface` 6.0:1 · `muted`/`canvas` 5.6:1 · `accent`/`surface` 5.5:1 (and `on-accent`/`accent` 5.5:1) · `accent-strong`/`accent-tint` 7.6:1 · `success`/`success-tint` 5.7:1 · `warning`/`warning-tint` 6.2:1 · `danger`/`danger-tint` 7.1:1. All text pairs pass AA. Series marks vs white: violet 8.6, blue 4.4, orange 3.9, **aqua 2.8, yellow 2.2 (below 3:1 graphic target)** → relief rule: every chart has a legend plus direct labels (≤4 series) or its table view. `series-neutral` (unallocated/non-entity bar) 3.43:1 on white. Palette validated for CVD (worst ΔE 9.1) per memlog.

**Streamlit mapping.**

| config.toml `[theme]` key | Token |
|---|---|
| `base` | `"light"` |
| `primaryColor` | `{colors.accent}` |
| `backgroundColor` | `{colors.canvas}` |
| `secondaryBackgroundColor` | `{colors.surface-sunken}` (widget fills) |
| `textColor` | `{colors.text}` |
| `borderColor` / `dataframeBorderColor` | `{colors.border}` |
| `greenColor` / `orangeColor` / `redColor` / `blueColor` / `grayColor` | `{colors.success}` / `{colors.warning}` / `{colors.danger}` / `{colors.accent}` / `{colors.muted}` (so `st.badge`, `:color[]`, `st.success/warning/error` match) |
| `chartCategoricalColors` | `series-1..5` in order |
| `chartSequentialColors` | `seq-low`, `seq-mid`, `seq-high` |
| `font` / `codeFont` | `{typography.font-sans}` / `{typography.font-mono}` |
| `baseFontSize` | 16 (`{typography.body.fontSize}`) |
| `baseRadius` / `buttonRadius` | `{rounded.sm}` |
| `[theme.sidebar] backgroundColor` | `{colors.sidebar-bg}` |

Shell CSS layer only: `surface` (card fill), `warning-border`, `accent-strong`/`accent-tint` nav state, `info-icon-bg`, card shadow, `{rounded.md}` card radius, KPI numeral size, badge pills, lineage node styling. Use the exact Streamlit 1.64 key names, including `baseFontSize` and `baseRadius`.

## Typography

System sans (no web font download; projector laptops vary). Roles: `{typography.page-title.fontSize}` page-title · `{typography.section-title.fontSize}` section-title · `{typography.body.fontSize}` body · `{typography.label.fontSize}` label · `{typography.table-cell.fontSize}` table-cell · `{typography.table-header.fontSize}` table-header · `{typography.badge.fontSize}` badge/caption · `{typography.kpi-value.fontSize}` kpi-value · `{typography.masked-value.fontSize}` masked-value (mono).

- **Floor:** body text ≥15px; nothing on screen below 14px (badges, captions, table headers, footnotes). 14px floor for meta text — memlog fixes body ≥15 only.
- KPI numerals are the loudest element on any page; badges beneath them are bold but ~⅓ the size.
- Numbers in tables and cards use tabular figures, right-aligned.
- Metric labels use the glossary `display_name` verbatim (FR-11); never uppercase-transform a metric name. Table headers may use uppercase + tracking (`table-header`).

## Layout & Spacing

4px base scale (`spacing.1`–`spacing.7`). Page padding `{spacing.page-padding}`; card padding `{spacing.card-padding}`; grid gap `{spacing.gutter}`.

Page anatomy (every analytics page): page title + "Viewing as: <Role name> (UGxx)" right-aligned → optional page banner → filter bar → KPI row (max 4 metric cards per row) → content grid (chart ~1.3fr + table ~1fr, or full-width table) → footnote strip. Streamlit `layout="wide"`. Designed at 1366×768 (projector/laptop baseline taken from mock frame); KPI row must stay one line at that width.

## Elevation & Depth

One elevation: cards, tables, filter controls and role switcher carry the soft card shadow (`components.metric-card.shadow`). Dialog uses Streamlit's default modal overlay. No stacked shadows, no hover lift. Depth also comes from tonal layering: `canvas` < `surface`; `surface-sunken` for recessed strips.

## Shapes

`{rounded.md}` 12px for containers (cards, tables, dialogs) · `{rounded.sm}` 8px for controls (inputs, buttons, filters, nav items, banners, role switcher) · `{rounded.full}` only for badges and status chips · `{rounded.xs}` for inline code and chart bar tops.

## Components

Icons are Material Symbols names rendered via Streamlit `:material/<name>:` shortcodes (🔒/⚠ glyphs in text are acceptable equivalents). Icon set and names: `check_circle`, `warning`, `science`, `lock`, `error`, `notifications`, `sync`.

| Component | Anatomy & visual spec |
|---|---|
| **metric-card** (`shell.metric`) | Top row: label (`label`, `muted`) + circular ⓘ button (18–24px, `info-icon-bg`). Value (`kpi-value`). Badge row below (gap `{spacing.2}`): freshness, synthetic, stale. Stale variant: border `warning-border`, value `{colors.warning}`, `badge-stale` replaces `badge-fresh`. Refreshing variant: value unchanged (previous value kept), `badge-refreshing` replaces `badge-fresh` in place, no border/value color change — distinct from the stale variant. |
| **badge-fresh** | Pill, `success-tint`/`success`, ✓ icon + "Refreshed HH:MM". |
| **badge-refreshing** | Pill, `accent-tint`/`accent-strong`, sync icon + "Refreshing…"; flips to `badge-fresh` "Refreshed HH:MM" on success. Distinct from `badge-stale` — reserved for an in-flight update, never for a gated/quality failure (AD-19). |
| **badge-stale** | Pill, `warning-tint`/`warning`, ⚠ icon + "Using previous version"; may wrap to two lines. |
| **badge-synthetic** | Pill, `surface-sunken`/`text-secondary`, icon + "Synthetic". |
| **badge-masked** | Inline in cell: masked value in `masked-value` mono (e.g. `C****42`) + 🔒. No fill. |
| **badge-denied** | Inline in cell: 🔒 + italic `muted` "not permitted for role". No red (overrides mock). |
| **status-chip** | Pill with icon + word. Variants → mapping: `success` (run success · DQ Green · target Continue), `warning` (DQ Amber · target Adjust · run gated), `danger` (run failed · DQ Red · target Stop), `info` (run running), `neutral` (queued · exception new/seen/accepted · resolved at source). |
| **banner-stale / banner-error** | Full-width under page title, 4px left rule, icon + one sentence naming the dataset/cause. |
| **footnote-strip** | Bottom of page, `caption`; holds the single "currency unverified" note (R10) and page-level interpretation notes. |
| **progress-strip** | Inline strip below the spend edit form (Budget & Spend, UG04) after save, `accent-tint`/`accent-strong`, `{rounded.sm}`; per-dataset step dots (done = ✓ icon) beside "Refreshing N datasets · m:ss", replaced on completion by "N metrics changed — see Change History". |
| **dialog** (definition) | Streamlit `st.dialog` large; title "<display_name>" in `accent`; tabs Definition · Lineage · Quality; field grid of key (`caption` uppercase, `muted`) / value (`body`); column names as inline code on `surface-code`; "Not ROAS"-type cautions as `status-chip.danger`; quality score as status-chip. |
| **table** | `st.dataframe` with themed border; numeric right-aligned tabular; campaign cells show name + muted `CMP-0x` id; selected row `accent-tint`. |
| **button-primary / -secondary / -disabled** | Verb labels. Disabled = sunken fill + 🔒 + reason text directly beneath in `caption` (never tooltip-only). |
| **form-field** | Label above; focus ring `accent`; error = `danger` border + message under field in `danger`, `caption` size. |
| **filter-bar** | Row of select/date controls, small uppercase label + bold value. |
| **sidebar** | App name (bold 16) + subtitle "CO5173 · Academic demo" → role-switcher → nav groups (group label `caption` uppercase) → items with icon; active item `accent-tint` fill + `accent-strong` bold text. |
| **role-switcher** | Select pinned at sidebar top, label "Role (demo mode)", value = role name; caption "Signed in as **UGxx** · nav filtered to this role". |
| **alert-indicator** | Shell-level pill (bell icon + count) in sidebar under role switcher, `danger-tint`/`danger`; hidden when 0. Sidebar placement confirmed. |
| **toast** | `st.toast` with status icon; short sentence + optional link text. |
| **skeleton** | Gray blocks (`surface-sunken`) shaped like the final card/table/chart; no centered spinner. |
| **lineage-graph** | Left-to-right DAG: source → raw → unified → mart → metric; nodes are rounded rectangles with dataset id + refreshed time + version; stale nodes get warning border + ⚠. |
| **Composites** (spend edit form, audience builder, win-back list, exceptions triage, DQ scoreboard, access matrix, pipeline status, change history, catalog search) | No new visuals: built from card + table + form-field + status-chip + button tokens above. Access-matrix cells use status-chip (`success` allow · `warning` mask · `neutral` deny) with icon + word. Pipeline elapsed timer uses `label` type beside the run's status-chip. |
| **spend-stack-bar** | Daily stacked bar (Budget & Spend): Allocated segment `{colors.accent}`; Unallocated segment `{colors.series-neutral}` (never a campaign `series-n` or status color); 2px `{colors.surface}` gap between the two segments. Legend + direct labels always on (not reliant on hue alone); carries the same `chart` table-view toggle. |
| **chart** | Thin marks, recessive `border`-colored grid, titled, labeled axes, legend, hover tooltip, table-view toggle. Campaigns always `series-n` by slot. No dual axis. Status colors never used as series. |

## Do's and Don'ts

| Do | Don't |
|---|---|
| Keep the number the loudest thing; badges adjacent and quieter | Put trust badges above or larger than the value |
| Pair every status color with icon + text | Signal state by color alone (projector shifts hues) |
| Give each campaign its fixed `series-n` everywhere | Recolor campaigns by rank or per page |
| Theme via config.toml; custom CSS only in `app/shell` | Per-page CSS or `unsafe_allow_html` styling in pages |
| One accent (`accent`) | Add a second brand color or use status colors decoratively |
| Body ≥15px, KPI 40px | Streamlit default small captions for anything the class must read |
| Light mode | Dark mode, gradients, logos, illustrations |

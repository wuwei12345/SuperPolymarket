---
phase: 01
slug: market-universe-metadata
status: approved
shadcn_initialized: false
preset: internal-quant-workbench
created: 2026-04-18
---

# Phase 01 — UI Design Contract

> Visual and interaction contract for Phase 1. This page is an internal read-only operator surface for validating Polymarket market universe sync, filtering, and field provenance.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | Streamlit-style internal web app |
| Preset | internal-quant-workbench |
| Component library | Native framework components first; no external UI kit required for Phase 1 |
| Icon library | None required; simple text labels and status markers are sufficient |
| Font | System UI stack: `Inter`, `SF Pro Display`, `Segoe UI`, `Arial`, sans-serif |

## Layout Contract

| Region | Position | Size Contract | Behavior |
|--------|----------|---------------|----------|
| Filter panel | Left side | 260px desktop width; full-width collapsible block on narrow screens | Always controls the table; filters apply immediately |
| Market table | Right side primary area | Fills remaining width; horizontal overflow allowed for long IDs | Primary visual focus of the page |
| Sync timeline log | Bottom | Collapsed height 56px; expanded height 220-320px | Can be opened and closed without changing filter state |
| Header strip | Top | 56-72px height | Shows page title, last sync status, manual sync action |

**No details panel:** Clicking a row may select/highlight it, but Phase 1 must not add a market detail drawer or drill-down page.

---

## Spacing Scale

Declared values (must be multiples of 4):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Inline badges, compact metadata gaps |
| sm | 8px | Field labels, table cell inner gaps |
| md | 16px | Default control spacing, filter groups |
| lg | 24px | Page gutters, table/log separation |
| xl | 32px | Major panel spacing |
| 2xl | 48px | Empty state top spacing |
| 3xl | 64px | Reserved for full-page empty/error states only |

Exceptions: none

---

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body | 14px | 400 | 1.45 |
| Label | 12px | 600 | 1.35 |
| Table cell | 13px | 400 | 1.40 |
| Table header | 12px | 700 | 1.25 |
| Heading | 20px | 700 | 1.25 |
| Status text | 12px | 500 | 1.30 |

**Text rules:**
- Long `conditionId` and token IDs must truncate in table cells with copyable full values available through native text selection or tooltip.
- Table cells must not wrap token IDs into multi-line blocks by default.
- Question text may wrap to two lines; after two lines it truncates.

---

## Color

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `#F6F7F9` | Page background |
| Secondary (30%) | `#FFFFFF` | Table surface, filter panel, log surface |
| Border | `#D7DDE2` | Table grid, panel separation, input borders |
| Text primary | `#1F2930` | Primary text |
| Text muted | `#66727C` | Secondary metadata and timestamps |
| Accent (10%) | `#0F8B8D` | Sync action, active filter indicator, selected row edge |
| Success | `#2E7D32` | Successful sync events |
| Warning | `#B7791F` | Retry events and stale data notices |
| Destructive | `#C2413A` | Failed sync status only |

Accent reserved for: manual sync action, active filter count, selected row edge, source badges when a source needs emphasis. Accent must not color every clickable element.

**Palette guardrails:**
- Do not use purple/purple-blue gradients.
- Do not use beige/tan/brown/orange-dominant backgrounds.
- Do not make the UI a one-color theme; neutral surface, teal accent, and semantic status colors must stay distinct.

---

## Core Surface Contracts

### Filter Panel

Required filters:
- Category
- Minimum liquidity
- End date range
- Restricted status
- Text search over question

Behavior:
- Filters apply immediately.
- Active filter count is visible near the filter header.
- Clearing filters returns to the default `active + accepting orders` universe, not to all markets.

### Market Table

Required default columns:
- `question`
- `category`
- `liquidity`
- `endDate`
- `conditionId`
- `yes token`
- `no token`
- `source`

Required sorting:
- `liquidity`
- `endDate`
- At least one deterministic fallback sort such as `question` or `updatedAt` if available

Data presentation:
- `source` must identify whether the row field values came from Gamma, CLOB, or a merged Gamma+CLOB normalization.
- Source information must be visible in the table itself, not hidden only in developer tools.
- Rows that cannot provide complete `conditionId` + two token IDs must be excluded from the default successful result set or clearly counted as sync errors, not silently displayed as valid rows.

### Sync Timeline Log

Timeline event types:
- Sync started
- Gamma fetch started/completed
- CLOB fetch started/completed
- Retry scheduled
- Retry failed
- Normalization completed
- Sync succeeded
- Sync failed

Each timeline item must show:
- Timestamp
- Step name
- Source label when applicable (`Gamma`, `CLOB`, `Normalizer`)
- Status (`running`, `retrying`, `success`, `failed`)
- Short message

The collapsed log must still show the last sync status and most recent event.

---

## Copywriting Contract

| Element | Copy |
|---------|------|
| Page title | `Market Universe` |
| Primary CTA | `Sync markets` |
| Filter heading | `Filters` |
| Active filters label | `{N} active` |
| Empty state heading | `No markets match these filters` |
| Empty state body | `Change the filters or sync markets again.` |
| First-run empty state heading | `No market universe yet` |
| First-run empty state body | `Sync markets to load active markets that are accepting orders.` |
| Error state | `Sync failed. Check the timeline and try again.` |
| Retry event copy | `Retrying {source} after request failure` |
| Success event copy | `Market universe updated` |

No promotional or marketing copy belongs on this page. Copy must describe the operator action or data state directly.

---

## Responsiveness

| Viewport | Layout |
|----------|--------|
| Desktop ≥ 1200px | Left filter panel, right table, bottom collapsible timeline |
| Tablet 768-1199px | Filter panel remains left if space allows; table scrolls horizontally for ID columns |
| Mobile < 768px | Filters become a collapsible top block; table remains the primary surface; timeline stays bottom collapsible |

Stable layout requirements:
- Expanding/collapsing the timeline must not reset filters or table sort.
- Long IDs must not push the page wider than the viewport without a controlled table scroll region.
- Header, filter panel, table, and timeline must keep stable dimensions during loading and retry states.

---

## Accessibility

- All filters must have visible labels.
- The sync action must be keyboard reachable.
- Timeline expand/collapse must expose a clear text label.
- Status must not rely on color alone; use text labels such as `success`, `retrying`, and `failed`.
- Table headers must remain readable and distinguishable from row cells.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none | not required |
| third-party UI registry | none | not allowed in Phase 1 |

No registry components are required. If a later plan introduces a UI component registry, it must explicitly justify why native framework components are insufficient for this internal table page.

---

## Checker Sign-Off

- [x] Dimension 1 Copywriting: PASS
- [x] Dimension 2 Visuals: PASS
- [x] Dimension 3 Color: PASS
- [x] Dimension 4 Typography: PASS
- [x] Dimension 5 Spacing: PASS
- [x] Dimension 6 Registry Safety: PASS

**Approval:** approved 2026-04-18

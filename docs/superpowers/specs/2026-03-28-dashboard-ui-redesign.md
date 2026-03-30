# Dashboard UI Redesign

Redesign the dashboard template to use proper DaisyUI components, a green-centric color palette derived from reference design, collapsible sidebar navigation, Lucide icons (replacing emojis), light/dark theme support, and template partials for maintainability.

## Decisions

- **Theme:** Dual light/dark mode using DaisyUI's `data-theme` system with custom `finance-light` and `finance-dark` themes. Toggle via Alpine.js `swap` component with Lucide `sun`/`moon` icons.
- **Color palette:** Green-centric, extracted from reference image. Primary `#2B6B4F` (light) / `#3FB68B` (dark). Secondary blue `#4A90D9` / `#5BA3EC`. Accent orange `#F5A623`. Error red `#E05252` / `#F47067`. Muted text `#7C8DB0`.
- **Icons:** Lucide SVGs inlined directly in templates. No CDN. Replaces all emoji usage.
- **Navigation:** Collapsible sidebar replacing horizontal tab bar. Collapsed: 64px, icons only. Expanded: 220px, icon + label. Alpine.js manages state. CSS transition for smooth expand/collapse.
- **Components:** Full DaisyUI component swap (Approach A). All custom CSS classes replaced with native DaisyUI equivalents.
- **Template structure:** Split into partials. Main template is a thin shell with includes.
- **Analytics:** Add `compute_mom_changes()` for month-over-month trend badges on KPI cards.

## Template Architecture

### Main template: `templates/dashboard.html.j2`

Thin shell containing:
- HTML head with inlined assets (DaisyUI CSS, Alpine.js, Chart.js, Lucide SVG definitions)
- Custom DaisyUI theme definitions for `finance-light` and `finance-dark`
- Outer layout: sidebar + main content area
- `{% include %}` for each tab partial
- Chart.js initialization scripts at bottom

### Partials: `templates/partials/`

| File | Content |
|---|---|
| `sidebar.html.j2` | Collapsible sidebar nav with Lucide icons, theme toggle, collapse toggle |
| `overview.html.j2` | KPI stat cards with MoM trend badges, 12-month trend chart, account balances, top merchants |
| `spending.html.j2` | Category donut, income vs expenses bar, category trends with sparklines, % of income bars, fixed costs table, subscriptions breakdown, food & dining breakdown |
| `goals.html.j2` | Savings streak grid, monthly target progress, named goals with progress bars |
| `insights.html.j2` | Health score ring + dimensions table, lifestyle insights, actionable cuts, action plan |
| `cards.html.j2` | CSP earn analysis, card portfolio table, missed rewards callout, category optimizer, upgrade recommendations |

### Renderer change

Update `dashboard/renderer.py` Jinja2 `FileSystemLoader` to include the `templates/` directory so `{% include "partials/..." %}` resolves correctly. No other backend changes.

## Component Mapping

| Current Custom | DaisyUI Replacement |
|---|---|
| `.card` with custom CSS | `card bg-base-100` with `card-body` |
| `.kpi-label` / `.kpi-value` / `.kpi-sub` | `stat` component (`stat-title`, `stat-value`, `stat-desc`) |
| `.badge-up` / `.badge-down` | `badge badge-success` / `badge badge-error` with Lucide `trending-up`/`trending-down` |
| `.tab-bar` / `.tab-btn` | Removed, replaced by sidebar `menu` |
| `.data-table` | `table table-zebra` |
| `.progress-track` / `.progress-fill` | `progress` or `radial-progress` |
| `.bar-track` / `.bar-fill` | `progress progress-primary` |
| `.insight-card` | `alert` with custom styling |
| `.cat-badge` | `badge badge-outline` |
| Period selector buttons | `join` with `btn btn-sm` |
| Theme toggle | `swap` with Lucide `sun`/`moon` |
| Sidebar nav | `menu` with active state via Alpine |

## Color System

### Light theme (`finance-light`)

| DaisyUI Variable | Color | Usage |
|---|---|---|
| `--p` (primary) | `#2B6B4F` | Sidebar active, positive trends |
| `--pf` (primary focus) | `#1F5A3F` | Hover states |
| `--pc` (primary content) | `#FFFFFF` | Text on primary |
| `--s` (secondary) | `#4A90D9` | Chart accents, info badges |
| `--a` (accent) | `#F5A623` | Warnings, streak indicators |
| `--n` (neutral) | `#1A1A2E` | Headings |
| `--b1` (base-100) | `#FFFFFF` | Card backgrounds |
| `--b2` (base-200) | `#F7F8FA` | Page background |
| `--b3` (base-300) | `#E2E8F0` | Borders, dividers |
| `--bc` (base content) | `#1A1A2E` | Body text |
| `--su` (success) | `#2B6B4F` | Positive change, income |
| `--er` (error) | `#E05252` | Negative change, expenses |
| `--wa` (warning) | `#F5A623` | At-risk goals |

### Dark theme (`finance-dark`)

| DaisyUI Variable | Color | Usage |
|---|---|---|
| `--p` | `#3FB68B` | Primary green (brighter) |
| `--s` | `#5BA3EC` | Secondary blue |
| `--a` | `#F5A623` | Accent orange |
| `--n` | `#E6EDF3` | Light text |
| `--b1` | `#161B22` | Card backgrounds |
| `--b2` | `#0D1117` | Page background |
| `--b3` | `#21262D` | Borders |
| `--bc` | `#E6EDF3` | Body text |
| `--su` | `#3FB68B` | Positive |
| `--er` | `#F47067` | Negative |

Chart.js reads colors from CSS variables via `getComputedStyle()` so charts respect the active theme.

## Analytics Change

### New function: `compute_mom_changes(transactions, current_month)`

Returns dict:
- `income_change_pct`: percentage change in income vs prior month
- `expenses_change_pct`: percentage change in expenses vs prior month
- `saved_change_pct`: percentage change in savings vs prior month
- `net_worth_change_pct`: `None` (no historical net worth tracking)

Logic: filter transactions for current and prior month, sum income/expenses, compute `(current - prior) / prior * 100`. Returns `None` per field if prior month has no data. Guards against division by zero.

### `build_context()` update

Call `compute_mom_changes()` and add result to context as `mom_changes`.

## Testing

| Test | What |
|---|---|
| `test_compute_mom_changes_normal` | Two months of data, verify percentage calculations |
| `test_compute_mom_changes_no_prior` | Only current month, all fields return `None` |
| `test_compute_mom_changes_zero_prior` | Prior month zero values, no division by zero |
| `test_build_context_includes_mom` | `mom_changes` key present in context |

The existing `dashboard --no-open` integration test exercises the full render pipeline including all partials. 100% coverage maintained.

## Sidebar Behavior

- **Collapsed (default):** 64px wide, Lucide icons only, tooltip on hover for labels
- **Expanded:** 220px wide, icon + text label, smooth CSS transition (`width` + `opacity` on labels)
- **Toggle:** Button at sidebar bottom with Lucide `panel-left-close` / `panel-left-open`
- **State:** Alpine.js `x-data="{ sidebarOpen: false, theme: 'finance-light' }"` on `<body>`
- **Active tab:** Alpine.js `tab` variable, same as current but wired to sidebar menu items instead of horizontal tabs

## Scope Boundaries

- Template-only redesign + one new analytics function
- No changes to CLI commands, data store, importers, categorizer, or any other module
- No new dependencies (Lucide icons are inlined SVG, DaisyUI CSS already loaded)
- No changes to the dashboard context dict shape (only addition: `mom_changes`)

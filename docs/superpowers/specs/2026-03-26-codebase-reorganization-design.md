# Codebase Reorganization Design

## Goal

Move all Python modules out of the root directory into logical subdirectories grouped by responsibility. The root retains only `main.py` (the CLI entry point) and non-code project files.

## Current State

Seven Python modules live flat in the project root alongside config, docs, and data files:

| File | Lines | Role |
|---|---|---|
| `finance.py` | 344 | Click CLI entry point |
| `data_store.py` | 99 | CSV-backed transaction storage |
| `categorizer.py` | 63 | Keyword-based merchant categorization |
| `goals.py` | 87 | Savings goals persistence |
| `dashboard.py` | 83 | Dashboard render orchestrator |
| `dashboard_data.py` | 514 | Dashboard analytics and KPI computation |
| `import_real_data.py` | 583 | Bank-specific PDF parsers + import script |

`importers/` (csv_parser, pdf_parser) and `scripts/` (hooks) are already organized as sub-packages.

## Target Structure

```
main.py                        ← finance.py renamed (CLI entry point)
config.json                    ← unchanged
requirements.txt               ← unchanged
pytest.ini / .coveragerc       ← unchanged (see Coverage section)
README.md / CHANGELOG.md       ← README requires module-path updates (see below)
statements_manifest.example.json ← unchanged

core/
  __init__.py
  data_store.py                ← moved from root
  categorizer.py               ← moved from root
  goals.py                     ← moved from root

importers/
  __init__.py                  ← already exists
  csv_parser.py                ← already here
  pdf_parser.py                ← already here
  real_data.py                 ← import_real_data.py renamed + moved

dashboard/
  __init__.py                  ← re-exports build_dashboard and _load_files
  renderer.py                  ← dashboard.py moved + renamed
  analytics.py                 ← dashboard_data.py moved + renamed

scripts/                       ← unchanged
templates/                     ← unchanged
tests/                         ← unchanged location; imports updated
data/                          ← unchanged
docs/                          ← unchanged
reports/                       ← unchanged
```

## Package Boundaries

### `core/`
Single responsibility: domain model and flat-file persistence.
- `data_store.py` — `DataStore`, `generate_id`, `COLUMNS`
- `categorizer.py` — `Categorizer`, `normalize_merchant`
- `goals.py` — `load_goals`, `save_goals`, `set_monthly_target`, `add_named_goal`, `get_goal_progress`

No dependency on `importers/` or `dashboard/`. Used by `main.py` and `importers/`.

### `importers/`
Single responsibility: parse external files and populate the store.
- `csv_parser.py` — config-driven CSV parser (`CSVParser`)
- `pdf_parser.py` — generic pdfplumber table parser (`PDFParser`)
- `real_data.py` — bank-specific text parsers for Chase, BofA, Robinhood; retains its `if __name__ == "__main__":  # pragma: no cover` guard verbatim so it runs as `python3 -m importers.real_data`

Depends on `core/`. Used by `main.py`.

### `dashboard/`
Single responsibility: compute analytics and render HTML report.
- `analytics.py` — all KPI and trend computation (`build_context`, `compute_*`, private helpers)
- `renderer.py` — Jinja2 orchestrator (`build_dashboard`, `_load_files`)
- `__init__.py` — re-exports both `build_dashboard` and `_load_files` from `renderer.py`:
  ```python
  from dashboard.renderer import build_dashboard, _load_files
  __all__ = ["build_dashboard", "_load_files"]
  ```
  This keeps the two existing test imports (`from dashboard import build_dashboard` and `from dashboard import _load_files`) unchanged.

Depends on `core/`. Used by `main.py`.

### `main.py` (root)
Thin Click CLI. Imports from `core/`, `importers/`, `dashboard/`. No business logic beyond routing.

## Import Path Changes

### Module-level imports

| Old import | New import |
|---|---|
| `from data_store import DataStore, generate_id` | `from core.data_store import DataStore, generate_id` |
| `from categorizer import Categorizer` | `from core.categorizer import Categorizer` |
| `from goals import add_named_goal, ...` | `from core.goals import add_named_goal, ...` |
| `from importers.csv_parser import CSVParser` | unchanged |
| `from importers.pdf_parser import PDFParser` | unchanged |
| `from dashboard import build_dashboard` | unchanged (re-exported from `dashboard/__init__.py`) |
| `from dashboard import _load_files` | unchanged (re-exported from `dashboard/__init__.py`) |
| `import import_real_data as ird` (tests) | `from importers import real_data as ird` |
| `from finance import cli` (tests) | `from main import cli` |

### `unittest.mock.patch` string arguments (tests)

`patch()` targets must use the dotted path of the module where the symbol is looked up. Only the `_add_tx` patches reference the old module path and must be updated:

| Old patch target | New patch target | Occurrences |
|---|---|---|
| `"import_real_data._add_tx"` | `"importers.real_data._add_tx"` | 3 (lines 426, 444, 480 of `test_import_real_data.py`) |

All `patch("pdfplumber.open", ...)` calls already target the canonical stdlib module path and require **no change** after the move.

The `patch("webbrowser.open", ...)` call in `test_cli_summary.py` also targets the canonical stdlib path and requires **no change**.

## Files Deleted from Root

After migration the following root-level files are removed:
`finance.py`, `data_store.py`, `categorizer.py`, `goals.py`, `dashboard.py`, `dashboard_data.py`, `import_real_data.py`

## Test Impact

All test files in `tests/` require import-path updates. No test logic changes. The test runner (`pytest`) discovers tests the same way since `tests/` stays in place.

| Test file | Import changes required |
|---|---|
| `tests/test_data_store.py` | `from data_store import ...` → `from core.data_store import ...` |
| `tests/test_categorizer.py` | `from categorizer import ...` → `from core.categorizer import ...` |
| `tests/test_goals.py` | `from finance import cli` → `from main import cli` |
| `tests/test_dashboard.py` | `from dashboard import _load_files` unchanged; `from dashboard import build_dashboard` unchanged |
| `tests/test_dashboard_data.py` | `from dashboard_data import ...` → `from dashboard.analytics import ...` |
| `tests/test_import_real_data.py` | `import import_real_data as ird` → `from importers import real_data as ird`; `from data_store import DataStore` → `from core.data_store import DataStore`; `from categorizer import Categorizer` → `from core.categorizer import Categorizer`; three `_add_tx` patch strings updated (see above) |
| `tests/test_cli_import.py` | `from finance import cli` → `from main import cli` |
| `tests/test_cli_summary.py` | `from finance import cli` → `from main import cli` |
| `tests/test_csv_parser.py` | `from importers.csv_parser import ...` unchanged |
| `tests/test_pdf_parser.py` | `from importers.pdf_parser import ...` unchanged |
| `tests/test_check_changelog.py` | Line 12: `is_nontrivial_file("finance.py")` — update the argument to `"main.py"` for clarity (the function only checks the `.py` extension, so this is a cosmetic change not a functional one). All other `"finance.py"` string literals in this file are incidental test-data arguments to mock helpers and do not need changing. |

## Coverage Configuration

`pytest.ini` uses `--cov=.` which instruments the current working directory. After reorganization the new `core/` and `dashboard/` packages are within `.` and will be discovered automatically — no change to `pytest.ini` or `.coveragerc` is required.

The `if __name__ == "__main__":  # pragma: no cover` guard in `real_data.py` must be preserved verbatim when the file is moved; it is what keeps the `__main__` block excluded from coverage measurement.

## Documentation Updates

### CLAUDE.md
Update all references to:
- `finance.py` → `main.py` (Commands section and Key Modules table)
- `import_real_data.py` → `importers/real_data.py`
- `dashboard.py` → `dashboard/renderer.py`
- `dashboard_data.py` → `dashboard/analytics.py`
- CLI invocation `python3 import_real_data.py` → `python3 -m importers.real_data`

### README.md
Specific items to update:
- All `python finance.py <command>` invocations throughout the Command Reference → `python3 main.py <command>`
- Line 57: `use import_real_data.py instead` → `use python3 -m importers.real_data instead`
- Any prose references to `dashboard.py` or `dashboard_data.py` module names

## Success Criteria

- `pytest` passes with 100% coverage after reorganization
- `python3 main.py dashboard` generates the dashboard
- `python3 -m importers.real_data` runs the bank statement import
- Root directory contains only `main.py` and non-code project files
- No `patch()` string in any test file references an old module path

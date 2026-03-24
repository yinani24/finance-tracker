# Security Policy

## 1. Overview

This is a personal finance tool that processes real bank statement data — PDFs and CSVs downloaded directly from financial institutions. The security model is built around one non-negotiable principle:

**Real financial data (statements, transaction CSVs, account names, and any file containing account identifiers) must never be committed to git.**

This matters even for a private repository. Git history is permanent. A file committed and then deleted is still retrievable from the reflog, from clones made before deletion, and from services that cached the repository. The only safe posture is to prevent the commit from happening in the first place.

The controls in this repository reflect that posture:

- `.gitignore` rules exclude every known sensitive file path by default
- A pre-commit hook (`scripts/check_secrets.py`) scans staged content for card-number patterns and data file references, blocking the commit if any are found
- A second hook check (`scripts/check_changelog.py`) reminds contributors to update the changelog when they make code changes (non-blocking)
- `statements_manifest.json` is the bridge between gitignored statement files on your local disk and the import scripts — it is itself gitignored

The rest of this document describes each layer in detail, what it protects against, and what to do if something goes wrong.

---

## 2. Threat Model

### What We Protect Against

**Git history leaks**

The primary risk for a personal finance tracker is that real data ends up in git commits. This happens more often than expected: a developer imports a file, the tool writes to `data/transactions.csv`, and then `git add .` or a careless staging captures it. Once committed, the data is in the repository's object store regardless of whether it appears in the working tree.

This repository defends against this with both a `.gitignore` layer (prevents files from appearing as untracked/staged by default) and a pre-commit hook (blocks the commit even if files are somehow staged).

**Data file commits**

Files like `data/transactions.csv`, `data/accounts.json`, and `data/goals.json` hold the complete financial picture: every transaction, every account balance, every savings goal. These are gitignored by path. The pre-commit hook additionally blocks any commit that attempts to stage these files, even if `.gitignore` was bypassed with `git add --force`.

**Statement commits**

PDF and CSV bank statements contain full transaction histories, merchant names, running balances, and often partial account numbers. The entire `statements/` directory is gitignored. The pre-commit hook also detects any file whose content references the `statements/` path, since a stray reference in a config file or script could expose file names that hint at real account details.

**Hardcoded identifiers**

Partial card numbers (e.g., `ending in 4242`) and account number fragments sometimes end up in log output, comments, or test files. The pre-commit hook scans for patterns matching `\d{4}-\d{4}` (card-number group format), `-\d{4}` (last-four suffix), and `\d{12,16}` (unbroken digit strings of card-number length). These patterns are intentionally conservative — they may flag false positives (e.g., a ZIP+4 postal code) to ensure no real card data slips through.

**Accidental manifest commits**

`statements_manifest.json` maps account keys to local file paths like `statements/eStmt_2026-01-15.pdf`. The file name itself can hint at the account holder's financial institutions. This file is gitignored.

### What We Do NOT Protect Against

**Local machine compromise**

All data files live in plaintext on disk in the project directory. If your machine is compromised, an attacker with local access can read them. This tool does not encrypt data at rest. If you need stronger local protection, use full-disk encryption (FileVault on macOS, BitLocker on Windows, LUKS on Linux).

**Network attacks**

This is a fully local tool. It opens a local HTTP server for the dashboard (`localhost` only) and makes no outbound network requests. There is no authentication layer because there is no network exposure by design.

**Shared machine scenarios**

If multiple users share the same machine account, they can all read the data directory. This tool assumes single-user, single-machine deployment.

---

## 3. Sensitive Data Inventory

The following table lists every file or directory that may contain sensitive financial data, whether it is gitignored, and why.

| File / Directory | What It Contains | Gitignored? | Why |
|---|---|---|---|
| `statements/` | Real PDF and CSV bank statements downloaded from your financial institutions | Yes | Contains full transaction histories, running balances, and partial account numbers |
| `data/transactions.csv` | Every imported transaction: date, amount, merchant, category, account, source | Yes | The complete financial record; exposure reveals spending patterns and account activity |
| `data/accounts.json` | Account names and current balances | Yes | Contains institution-identifying account names and balance amounts |
| `data/goals.json` | Savings goal names, target amounts, and current progress amounts | Yes | Reveals financial targets and savings capacity |
| `statements_manifest.json` | Local filesystem paths to real bank statement files, keyed by account | Yes | File paths often include date ranges and institution names that identify accounts |
| `.env` | API keys for future integrations (e.g., Plaid) | Yes | Contains credentials that could authorize access to live bank account data |
| `config.json` | Bank format definitions, import account name mappings, spending category keywords | No — safe to commit | Contains no personal data; only structural configuration |
| `reports/` | Any generated report files | Yes (with `.gitkeep` exception) | Generated output may embed real transaction data |

Note: `data/` as a directory does contain a `.gitkeep` file (via the reports rule pattern) to preserve the directory in git without committing its real contents. The individual file paths `data/transactions.csv`, `data/accounts.json`, and `data/goals.json` are listed explicitly in `.gitignore` rather than blanket-ignoring `data/` so that future safe files (e.g., schema versions) can live there.

---

## 4. Gitignore Policy

The `.gitignore` at the repository root contains the following security-relevant entries. Each is explained below.

```
.env
data/transactions.csv
data/accounts.json
data/goals.json
reports/*
!reports/.gitkeep
statements/
statements_manifest.json
```

**`.env`**
Standard environment variable file. Excluded to prevent API keys and secrets from being committed. Even if currently empty, this file should never appear in git history so that future additions are not accidentally committed.

**`data/transactions.csv`**
The primary data store for all imported transactions. This is the most sensitive file in the project. It accumulates every import operation. Gitignored by explicit path so that `git add data/` or `git add .` cannot accidentally stage it.

**`data/accounts.json`**
Stores account names and balances. Account names in this project follow the pattern `Chase-CreditCard`, `BofA-Visa`, etc. — they identify the financial institutions you use. Gitignored explicitly.

**`data/goals.json`**
Stores savings goal definitions including target amounts and current progress. Reveals financial targets and savings velocity. Gitignored explicitly.

**`reports/*` with `!reports/.gitkeep`**
The `reports/` directory is used for generated output files. Any generated file may contain real transaction data. The wildcard excludes all contents. The `!reports/.gitkeep` negation allows git to track the empty directory so that the directory structure is preserved after cloning without committing any real report content.

**`statements/`**
The directory where you download real bank statements before importing. The trailing slash ensures the entire directory tree is excluded, including any subdirectories you might create to organize statements by year or institution.

**`statements_manifest.json`**
The file that maps account keys to local file paths. It is gitignored rather than added to `.gitignore` by name so that contributors do not accidentally commit it after creating it from the example template. The example template (`statements_manifest.example.json`) is safe to commit because it contains only placeholder paths.

---

## 5. Pre-Commit Hook Design

The pre-commit hook runs two scripts in sequence:

1. `scripts/check_secrets.py` — **blocking**: exits 1 if sensitive patterns are found, preventing the commit
2. `scripts/check_changelog.py` — **non-blocking**: prints a warning if code files are staged without a changelog update, but always exits 0

### check_secrets.py

The script retrieves staged files with:
```
git diff --cached --name-only --diff-filter=ACMR
```

The `--diff-filter=ACMR` flag limits the scan to Added, Copied, Modified, and Renamed files — it skips deleted files since their content is being removed, not added.

For each staged file, the script performs two checks:

**Path-level check (blocks the file outright)**

If the file path matches any of the sensitive data file names, the commit is blocked immediately without reading the file content:
- `data/transactions.csv`
- `data/accounts.json`
- `data/goals.json`

This check uses a suffix match so that `--data-dir`-style custom paths are also caught.

**Content-level checks (reads the file)**

Non-binary files are read with UTF-8 encoding (errors ignored). The content is scanned against two compiled regular expressions:

```python
_CARD_RE = re.compile(r'\b\d{4}[-\s]\d{4}\b|\b\d{12,16}\b|-\d{4}\b')
_STATEMENTS_RE = re.compile(r'\bstatements/')
```

The `_CARD_RE` pattern matches three distinct forms:
- `\b\d{4}[-\s]\d{4}\b` — four digits, a hyphen or space, four more digits (card number group format, e.g., `1234-5678`)
- `\b\d{12,16}\b` — an unbroken run of 12 to 16 digits (full card number without separators)
- `-\d{4}\b` — a hyphen followed by exactly four digits (the "ending in XXXX" suffix pattern)

The `_STATEMENTS_RE` pattern matches any occurrence of the literal string `statements/` as a word-boundary-prefixed token, catching path references in config files, Python strings, or shell scripts.

If any violation is detected, the script prints a formatted error report and exits with code 1:

```
COMMIT BLOCKED — sensitive data detected:
  finance.py: contains card-number-like digit pattern (e.g. XXXX-XXXX)

Fix the above issues before committing.
See docs/SECURITY.md for guidance.
```

### check_changelog.py

This script checks whether any staged file has a non-trivial extension (`.py`, `.html`, `.j2`, `.json`) while `CHANGELOG.md` is not also staged. If so, it prints a reminder. It always exits 0 — it never blocks the commit.

The intent is to prompt contributors to document what they changed, not to enforce it mechanically.

---

## 6. Hook Installation

After cloning the repository, install the pre-commit hook before making any commits:

```bash
sh scripts/install_hooks.sh
```

This script does the following:
1. Determines the repository root with `git rev-parse --show-toplevel`
2. Copies `scripts/pre-commit` to `.git/hooks/pre-commit`
3. Makes the hook executable with `chmod +x`
4. Prints a confirmation message

The hook file itself (`scripts/pre-commit`) is a shell script that calls both Python scripts in sequence:

```sh
#!/bin/sh
python3 scripts/check_secrets.py "$@"
if [ $? -ne 0 ]; then
  exit 1
fi

python3 scripts/check_changelog.py "$@"
exit 0
```

If `check_secrets.py` exits non-zero, the hook exits immediately with code 1, which causes git to abort the commit. The changelog check only runs if secrets passed.

**Important:** `.git/hooks/` is not tracked by git (the `.git/` directory is never committed). This means the hook is not automatically present after cloning — you must run the install script manually. This is by design: git does not execute hooks it did not install itself.

---

## 7. Bypass Procedure

If you need to commit content that legitimately triggers the secret patterns — for example, a test fixture file that contains synthetic card-number-shaped strings for parser testing — you can bypass the pre-commit hook with:

```bash
git commit --no-verify -m "test: add fixture with synthetic card pattern for parser test"
```

The `--no-verify` flag skips all pre-commit and commit-msg hooks.

**Use this sparingly.** Every bypass bypasses both the secrets check and the changelog reminder. When you use `--no-verify`, include a clear explanation in your commit message describing what pattern triggered the hook and why it is safe (e.g., "fixture data uses completely synthetic numbers").

If you find yourself using `--no-verify` regularly for legitimate reasons, consider updating `check_secrets.py` to accept an allowlist file (e.g., `tests/fixtures/*.csv` paths) rather than bypassing wholesale.

---

## 8. statements_manifest.json

`statements_manifest.json` is the configuration file that tells the import script (`import_real_data.py`) where your real bank statement files live on your local disk. It is gitignored by design — it bridges the gap between your real files (which must not be committed) and the code that processes them.

### Setup

```bash
cp statements_manifest.example.json statements_manifest.json
# Edit statements_manifest.json with your real file paths
```

### Full Schema

The manifest is a JSON object where each key corresponds to an account identifier defined in `config.json → import_accounts`. The value is an array of statement entries.

```json
{
  "_comment": "Copy this to statements_manifest.json and fill in your real paths. Never commit statements_manifest.json.",

  "chase_credit": [
    {
      "path": "statements/YYYYMMDD-statements-XXXX-.pdf",
      "closing_year": 2026,
      "closing_month": 1
    }
  ],

  "bofa_visa": [
    {
      "path": "statements/eStmt_YYYY-MM-DD.pdf",
      "year": 2026
    }
  ],

  "bofa_checking": [
    {
      "path": "statements/eStmt_YYYY-MM-DD.pdf"
    }
  ],

  "robinhood_csv": [
    {
      "path": "statements/transactions.CSV"
    }
  ],

  "robinhood_pdf": [
    {
      "path": "statements/<uuid>.pdf"
    }
  ]
}
```

**Field annotations by account type:**

`chase_credit` entries require:
- `path` — path to the Chase PDF statement (relative to repo root), typically named `YYYYMMDD-statements-XXXX-.pdf`
- `closing_year` — the calendar year of the statement closing date (integer)
- `closing_month` — the calendar month of the statement closing date (integer, 1–12)

These date fields are needed because Chase PDF statements do not embed the year in the transaction dates — the parser uses `closing_year` and `closing_month` to reconstruct full dates.

`bofa_visa` entries require:
- `path` — path to the BofA Visa PDF statement, typically named `eStmt_YYYY-MM-DD.pdf`
- `year` — the statement year (integer), used for the same date reconstruction reason

`bofa_checking` entries require:
- `path` — path to the BofA checking PDF statement

`robinhood_csv` entries require:
- `path` — path to the Robinhood transaction CSV export

`robinhood_pdf` entries require:
- `path` — path to the Robinhood account statement PDF, typically a UUID-named file

You can include multiple entries per account to batch-import multiple statement periods. The import script processes all entries for all accounts in a single run.

---

## 9. How to Handle Real Statements Safely

Follow these steps every time you import new statements. Deviating from this workflow is the most common way real data ends up in an unintended place.

**Step 1: Download statements to the `statements/` directory**

Log in to your bank's web interface and download statement PDFs or CSV exports to `statements/` in the project directory. This directory is gitignored, so its contents will never appear as untracked files in `git status`.

```
statements/
  2026-01-chase-credit.pdf
  eStmt_2026-01-15.pdf
  transactions.CSV
```

**Step 2: Update statements_manifest.json**

Edit `statements_manifest.json` to add the new file paths. Use paths relative to the repository root (e.g., `statements/2026-01-chase-credit.pdf`).

If this is your first import, run `cp statements_manifest.example.json statements_manifest.json` first to create the file from the template.

**Step 3: Run the import script**

```bash
python3 import_real_data.py
```

The script reads `statements_manifest.json`, parses each statement file, and appends new transactions to `data/transactions.csv` (deduplication is handled automatically — re-running the import on the same statement is safe).

**Step 4: Verify the import**

```bash
python3 finance.py summary
```

This shows income, expenses, and net saved for the current month. If the numbers look reasonable, the import succeeded.

You can also check the row count:
```bash
python3 finance.py top-categories --last 1month
```

**Step 5: Confirm nothing sensitive is staged**

Before your next commit, run `git status` and verify that no files from `data/` or `statements/` appear. They should not — they are gitignored — but a quick check costs nothing.

The pre-commit hook will independently verify this when you commit.

**The statement files remain in `statements/` on your local disk and are never committed.**

---

## 10. Incident Response

### If You Accidentally Committed Sensitive Data (Not Yet Pushed)

**Stop immediately — do not push.**

**Step 1: Undo the commit**

```bash
git reset HEAD~1
```

This moves `HEAD` back one commit and unstages all changes from that commit. Your working directory is unchanged — the files are still there, they are just no longer committed. The commit object still exists in the object store but is unreachable and will be garbage-collected.

**Step 2: Remove the file from git tracking if needed**

If the sensitive file was previously tracked (i.e., it was committed in an earlier commit), git will still track it. Remove it from the index without deleting it from disk:

```bash
git rm --cached data/transactions.csv
```

Replace `data/transactions.csv` with the actual file path.

**Step 3: Add to `.gitignore`**

If the file is not already gitignored, add it:

```
data/transactions.csv
```

**Step 4: Re-commit the safe version**

Stage your non-sensitive changes and commit:

```bash
git add .gitignore
git add <other-safe-files>
git commit -m "fix: remove accidentally staged data file, update gitignore"
```

Run `git log --oneline` to verify the sensitive commit is gone.

---

### If You Accidentally Committed and Already Pushed

This is a more serious situation. The data is now on the remote server and potentially cached by any system that fetched between the bad push and the force-push.

**Step 1: Force-push to overwrite the remote**

```bash
git push --force
```

This is a destructive operation. Anyone who has already pulled the bad commit will have the sensitive data in their local clone. Notify all collaborators immediately and ask them to run `git fetch --all && git reset --hard origin/main`.

**Step 2: Rotate any exposed credentials**

If the committed data included anything that could be used to authenticate to a service:
- Change your online banking passwords at every institution whose data was exposed
- Revoke any API keys (e.g., Plaid access tokens) that were in the committed files
- Contact your bank's fraud department if you believe account numbers were exposed

**Step 3: Treat the exposed data as permanently compromised**

Force-pushing rewrites the remote, but it does not delete the data from any system that fetched it before the force-push. GitHub, GitLab, and similar services may retain the original commit objects for some time after a force-push, even if they are unreachable. Contact the hosting provider to request permanent deletion from their object storage if account numbers or statements were exposed.

---

## Appendix: Quick Reference Checklist

Before every commit:
- [ ] `git status` shows no files from `data/` or `statements/`
- [ ] No hardcoded account numbers or card numbers in changed source files
- [ ] No `statements/` path references in changed source files
- [ ] `statements_manifest.json` is not staged

After cloning:
- [ ] `sh scripts/install_hooks.sh` has been run
- [ ] `statements_manifest.json` has been created from the example template
- [ ] Real statements have been placed in `statements/` (not committed)

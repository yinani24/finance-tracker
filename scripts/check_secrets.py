"""
Pre-commit hook: scans staged files for sensitive data patterns.

Blocks the commit (exit code 1) if any violation is found.
Run via .git/hooks/pre-commit — see scripts/install_hooks.sh.
"""
import re
import subprocess
import sys


# Patterns that indicate sensitive data
_CARD_RE = re.compile(r'\b\d{4}[-\s]\d{4}\b|\b\d{12,16}\b|-\d{4}\b')
_STATEMENTS_RE = re.compile(r'\bstatements/')
_DATA_FILES = frozenset(["transactions.csv", "accounts.json", "goals.json"])


def contains_card_pattern(text: str) -> bool:
    """Return True if text contains a card-number-like digit pattern."""
    return bool(_CARD_RE.search(text))


def contains_statements_path(text: str) -> bool:
    """Return True if text references the statements/ directory."""
    return bool(_STATEMENTS_RE.search(text))


def contains_data_file(filepath: str) -> bool:
    """Return True if filepath is one of the sensitive data files under data/."""
    return any(filepath.endswith(f"data/{name}") or filepath == f"data/{name}"
               for name in _DATA_FILES)


def check_content(content: str, filepath: str) -> list[str]:
    """
    Check file content for secret patterns.

    Args:
        content: The text content of the file.
        filepath: The file path (used in violation messages).

    Returns:
        List of violation message strings (empty if clean).
    """
    violations: list[str] = []
    if contains_card_pattern(content):
        violations.append(
            f"  {filepath}: contains card-number-like digit pattern (e.g. XXXX-XXXX)"
        )
    if contains_statements_path(content):
        violations.append(
            f"  {filepath}: references statements/ directory — use statements_manifest.json instead"
        )
    return violations


def get_staged_files() -> list[str]:
    """Return list of staged file paths from git."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True, text=True
    )
    return [f for f in result.stdout.strip().splitlines() if f]


def scan_staged_files() -> list[str]:
    """
    Scan all staged files for sensitive patterns.

    Returns:
        List of violation messages (empty if all clean).
    """
    staged = get_staged_files()
    all_violations: list[str] = []

    for filepath in staged:
        # Block data files outright
        if contains_data_file(filepath):
            all_violations.append(
                f"  {filepath}: sensitive data file — must not be committed"
            )
            continue

        # Skip binary files and non-text
        try:
            with open(filepath, encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except (OSError, IsADirectoryError):
            continue

        all_violations.extend(check_content(content, filepath))

    return all_violations


def main() -> int:
    """
    Entry point for pre-commit hook.

    Returns:
        0 if no violations, 1 if violations found.
    """
    violations = scan_staged_files()
    if violations:
        print("COMMIT BLOCKED — sensitive data detected:")
        for v in violations:
            print(v)
        print("\nFix the above issues before committing.")
        print("See docs/SECURITY.md for guidance.")
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

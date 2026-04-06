"""
Pre-commit hook: warns when CHANGELOG.md is not updated alongside code changes.

Warning only — always exits 0 (does not block the commit).
Run via .git/hooks/pre-commit — see scripts/install_hooks.sh.
"""

import os
import subprocess
import sys

_NONTRIVIAL_EXTENSIONS = frozenset([".py", ".html", ".j2", ".json"])


def is_nontrivial_file(filepath: str) -> bool:
    """Return True if the file is a code or config file (not docs/markdown)."""
    _, ext = os.path.splitext(filepath)
    return ext in _NONTRIVIAL_EXTENSIONS


def changelog_is_staged(staged_files: list) -> bool:
    """Return True if CHANGELOG.md is in the staged files list."""
    return "CHANGELOG.md" in staged_files


def should_warn(staged_files: list, changelog_staged: bool) -> bool:
    """
    Return True if a warning should be printed.

    Args:
        staged_files: List of staged file paths.
        changelog_staged: Whether CHANGELOG.md is already staged.

    Returns:
        True if nontrivial files are staged but CHANGELOG.md is not.
    """
    if changelog_staged:
        return False
    return any(is_nontrivial_file(f) for f in staged_files)


def get_staged_files() -> list:
    """Return list of staged file paths from git."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
    )
    return [f for f in result.stdout.strip().splitlines() if f]


def main() -> int:
    """Entry point for pre-commit hook. Always returns 0."""
    staged = get_staged_files()
    cl_staged = changelog_is_staged(staged)
    if should_warn(staged, cl_staged):
        print("WARNING  CHANGELOG.md not updated. Did you mean to add a changelog entry?")
        print("    (This is a reminder, not a blocker — commit will proceed.)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

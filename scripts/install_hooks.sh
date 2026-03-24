#!/bin/sh
# Installs the pre-commit hook. Run once after cloning:
#   sh scripts/install_hooks.sh

REPO_ROOT="$(git rev-parse --show-toplevel)"
cp "$REPO_ROOT/scripts/pre-commit" "$REPO_ROOT/.git/hooks/pre-commit"
chmod +x "$REPO_ROOT/.git/hooks/pre-commit"
echo "Pre-commit hook installed successfully."

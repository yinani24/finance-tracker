#!/bin/sh
# Installs pre-commit hooks. Run once after cloning:
#   sh scripts/install_hooks.sh
#
# Requires: pip install pre-commit (included in requirements.txt)

set -e

if ! command -v pre-commit >/dev/null 2>&1; then
  echo "Installing pre-commit..."
  pip3 install pre-commit
fi

pre-commit install
echo "Pre-commit hooks installed successfully."
echo "Run 'pre-commit run --all-files' to check the entire repo."

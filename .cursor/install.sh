#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for Domus.
# Creates a project virtualenv in .venv and installs pinned dependencies.
set -euo pipefail

cd "$(dirname "$0")/.."

# The default base image may not ship the venv/ensurepip module.
if ! python3 -c "import venv, ensurepip" >/dev/null 2>&1; then
  echo "Installing python3-venv..."
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-venv
fi

# Create the virtualenv only once; re-runs reuse it.
if [ ! -x .venv/bin/python ]; then
  echo "Creating virtualenv in .venv..."
  python3 -m venv .venv
fi

echo "Installing dependencies..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "Domus environment ready. Run the bot with: PYTHONPATH=src .venv/bin/python -m domus"

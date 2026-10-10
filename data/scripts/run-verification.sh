#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/python scripts/validate_workspace.py
./scripts/python ontology/validate.py --normalized-dir normalized

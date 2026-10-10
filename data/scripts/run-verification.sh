#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/python scripts/validate_workspace.py
./scripts/python ontology/validate.py --normalized-dir normalized
./scripts/python scripts/validate_campaign.py
./scripts/python scripts/test_acquisition_invariants.py

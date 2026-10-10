#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/krail --version
./scripts/python -c 'import jsonschema, yaml; print("Validation dependencies available")'

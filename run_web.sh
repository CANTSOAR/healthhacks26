#!/usr/bin/env bash
# Starts the HospitalGym web app on http://localhost:3000 (expects the server on http://localhost:8000;
# set NEXT_PUBLIC_API_URL to point elsewhere). Without the server it runs on its bundled fixtures.
set -euo pipefail
cd "$(dirname "$0")"
pnpm --dir web install
exec pnpm --dir web dev

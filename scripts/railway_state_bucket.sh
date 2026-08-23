#!/usr/bin/env bash
# Wire Sir-5rM8 to the shared ALICE bot-state bucket on Railway.
# Run from the Sir-5rM8 repo after: railway login && railway link (Sir-5rM8 bot service).
set -euo pipefail

railway variable set \
  STORAGE_ENDPOINT='https://storage.railway.app' \
  STORAGE_REGION='auto' \
  'STATE_BUCKET=${{bot-state.BUCKET}}' \
  'STATE_ACCESS_KEY_ID=${{bot-state.ACCESS_KEY_ID}}' \
  'STATE_SECRET_ACCESS_KEY=${{bot-state.SECRET_ACCESS_KEY}}'

echo "Sir-5rM8 bucket variables set. Redeploy the service, then check logs for:"
echo "  Object cache: Railway bucket (...)"
echo "  Object cache probe: read/write OK"

#!/usr/bin/env bash
# Wire Sir-5rM8 to its own Railway state bucket.
# Run from the Sir-5rM8 repo after: railway login && railway link (Sir-5rM8 bot service).
set -euo pipefail

resource="${1:-${SIR5RM8_STATE_BUCKET_RESOURCE:-}}"
if [[ -z "${resource}" ]]; then
  echo "Usage: $0 <dedicated-railway-bucket-resource-name>" >&2
  echo "Create a separate bucket (for example: sir-5rm8-state) and pass its Railway resource name." >&2
  exit 2
fi
if [[ "${resource}" == "bot-state" ]]; then
  echo "Refusing the shared ALICE bot-state resource; provision a dedicated Sir-5rM8 bucket." >&2
  exit 2
fi

bucket_ref="\${{${resource}.BUCKET}}"
access_ref="\${{${resource}.ACCESS_KEY_ID}}"
secret_ref="\${{${resource}.SECRET_ACCESS_KEY}}"

railway variable set \
  STORAGE_ENDPOINT='https://storage.railway.app' \
  STORAGE_REGION='auto' \
  "STATE_BUCKET=${bucket_ref}" \
  "STATE_ACCESS_KEY_ID=${access_ref}" \
  "STATE_SECRET_ACCESS_KEY=${secret_ref}"

echo "Sir-5rM8 bucket variables set. Redeploy the service, then check logs for:"
echo "  Object cache: Railway bucket (...)"
echo "  Object cache probe: read/write OK"
echo "Expected object prefixes: cache/ (ASA + database copies), state/ (sticky ids)."

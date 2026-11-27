#!/usr/bin/env bash
# Smoke test through the ingress (TLS, body limit, API key). No LLM calls.
set -euo pipefail
source "$(dirname "$0")/common.sh"
KEY=$(api_key)
fail() { echo "FAIL: $*" >&2; exit 1; }

[[ $(status "$BASE/health") == 200 ]] || fail "/health"
"${CURL[@]}" "$BASE/ready"; echo
[[ $(status "$BASE/ready") == 200 ]] || fail "/ready"

body='{"text":"Does metformin reduce cardiovascular events in type 2 diabetes?"}'
[[ $(status -X POST -H 'Content-Type: application/json' -d "$body" "$BASE/questions") == 401 ]] \
  || fail "write without API key must be 401"
created=$("${CURL[@]}" -X POST -H 'Content-Type: application/json' -H "X-API-Key: $KEY" -d "$body" "$BASE/questions")
id=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$created")
[[ $(status "$BASE/questions/$id") == 200 ]] || fail "read back question"
echo "smoke: created and read question $id"

big=$(python3 -c 'import json; print(json.dumps({"text": "x" * 70000}))')
code=$(status -X POST -H 'Content-Type: application/json' -H "X-API-Key: $KEY" --data-binary "$big" "$BASE/questions")
[[ $code == 413 ]] || fail "70 KB body must be rejected by the ingress with 413 (got $code)"
echo "smoke: 70 KB body rejected at the ingress with 413"

http_code=$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' -H "Host: $HOST" http://127.0.0.1:8080/health)
[[ $http_code == 301 || $http_code == 308 ]] || fail "plain HTTP must redirect to HTTPS (got $http_code)"
echo "smoke: plain HTTP redirected to HTTPS ($http_code)"
echo "smoke: OK"

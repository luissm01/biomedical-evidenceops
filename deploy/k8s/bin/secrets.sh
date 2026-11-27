#!/usr/bin/env bash
# Create the Secrets the manifests reference (M12.1, D038). Nothing is written to
# the repository. Existing Secrets are kept: regenerating the database password
# would not match the already-initialised PostgreSQL volume.
#
# Optional input: EVIDENCEOPS_GEMINI_API_KEY in the environment. Without it a
# placeholder is stored: the API starts, but generation/RAG calls will fail.
set -euo pipefail
NS=evidenceops
kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

if kubectl -n "$NS" get secret postgres-credentials >/dev/null 2>&1; then
  echo "secrets: keeping existing secrets in namespace $NS"
else
  pg_password=$(openssl rand -hex 24)
  api_key=$(openssl rand -hex 24)
  kubectl -n "$NS" create secret generic postgres-credentials \
    --from-literal=POSTGRES_PASSWORD="$pg_password" >/dev/null
  kubectl -n "$NS" create secret generic evidenceops-secrets \
    --from-literal=EVIDENCEOPS_DATABASE_URL="postgresql+psycopg://evidenceops:${pg_password}@postgres:5432/evidenceops" \
    --from-literal=EVIDENCEOPS_API_KEYS="$api_key" \
    --from-literal=EVIDENCEOPS_GEMINI_API_KEY="${EVIDENCEOPS_GEMINI_API_KEY:-placeholder-generation-not-configured}" \
    >/dev/null
  echo "secrets: created postgres-credentials and evidenceops-secrets"
fi

if ! kubectl -n "$NS" get secret evidenceops-tls >/dev/null 2>&1; then
  tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
  openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj "/CN=evidenceops.local" \
    -addext "subjectAltName=DNS:evidenceops.local" \
    -keyout "$tmp/tls.key" -out "$tmp/tls.crt" 2>/dev/null
  kubectl -n "$NS" create secret tls evidenceops-tls --cert="$tmp/tls.crt" --key="$tmp/tls.key" >/dev/null
  echo "secrets: created self-signed TLS secret for evidenceops.local (30 days)"
fi

#!/usr/bin/env bash
# Deploy EvidenceOps on a local kind cluster from scratch (M12.1, D038).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(cd ../.. && pwd)
CLUSTER=evidenceops

kind get clusters 2>/dev/null | grep -qx "$CLUSTER" || kind create cluster --config kind-config.yaml --wait 120s
kubectl config use-context "kind-$CLUSTER" >/dev/null

docker build -q -t evidenceops:local "$ROOT" >/dev/null
kind load docker-image evidenceops:local --name "$CLUSTER"

kubectl apply -f traefik.yaml
kubectl apply -f namespace.yaml
bin/secrets.sh
kubectl apply -f configmap.yaml -f postgres.yaml
kubectl -n evidenceops rollout status statefulset/postgres --timeout=180s

# API and worker may start now: the API stays not-ready until migrations finish.
kubectl apply -f api.yaml -f worker.yaml -f ingress.yaml
kubectl -n evidenceops delete job migrate --ignore-not-found
kubectl apply -f migrate-job.yaml
kubectl -n evidenceops wait --for=condition=complete job/migrate --timeout=180s
# Pick up a new image tag content on redeploys (same tag, new digest).
kubectl -n evidenceops rollout restart deployment/api deployment/worker >/dev/null
kubectl -n evidenceops rollout status deployment/api --timeout=180s
kubectl -n evidenceops rollout status deployment/worker --timeout=180s
kubectl -n ingress rollout status deployment/traefik --timeout=120s
# Traefik may be running before it has synced the Ingress: wait for a route.
source bin/common.sh
ok=0
for _ in $(seq 1 60); do
  if [[ $(status "$BASE/health") == 200 ]]; then ok=$((ok+1)); else ok=0; fi
  [[ $ok -ge 5 ]] && break; sleep 1
done
[[ $ok -ge 5 ]] || { echo "up: ingress not routing steadily" >&2; exit 1; }
echo "up: ready — run bin/smoke.sh"

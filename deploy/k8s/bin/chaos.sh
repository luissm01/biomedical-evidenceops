#!/usr/bin/env bash
# Failure drills (M12.1): delete an API pod, then stop PostgreSQL and recover it.
set -euo pipefail
source "$(dirname "$0")/common.sh"
fail() { echo "FAIL: $*" >&2; exit 1; }
ts() { date +%H:%M:%S; }

echo "== drill 1: delete one API pod"
victim=$(kubectl -n "$NS" get pods -l app=api -o jsonpath='{.items[0].metadata.name}')
kubectl -n "$NS" delete pod "$victim" --wait=false >/dev/null
ok=0; total=0
for _ in $(seq 1 20); do
  total=$((total+1)); [[ $(status "$BASE/health") == 200 ]] && ok=$((ok+1)); sleep 1
done
echo "$(ts) /health through ingress while the pod is replaced: $ok/$total OK"
kubectl -n "$NS" rollout status deployment/api --timeout=120s
kubectl -n "$NS" get pod "$victim" >/dev/null 2>&1 && fail "deleted pod still present"
echo "$(ts) replacement pod ready; restarts: $(restarts)"

echo "== drill 2: PostgreSQL outage"
before=$(restarts)
kubectl -n "$NS" scale statefulset/postgres --replicas=0 >/dev/null
kubectl -n "$NS" wait --for=delete pod/postgres-0 --timeout=120s
echo "$(ts) postgres stopped"
# Readiness is evaluated per pod; query one pod directly (the Service drops
# not-ready pods, so through the ingress the API becomes 503 from Traefik).
pod=$(kubectl -n "$NS" get pods -l app=api -o jsonpath='{.items[0].metadata.name}')
kubectl -n "$NS" port-forward "pod/$pod" 18000:8000 >/dev/null 2>&1 & pf=$!
trap 'kill $pf 2>/dev/null || true' EXIT
sleep 3
echo "$(ts) pod /ready: $(curl -s --max-time 10 -w ' [%{http_code}]' http://127.0.0.1:18000/ready)"
echo "$(ts) pod /health: $(curl -s --max-time 10 -w ' [%{http_code}]' http://127.0.0.1:18000/health)"
echo "$(ts) ingress /questions/<random>: $(status "$BASE/questions/00000000-0000-0000-0000-000000000000")"
sleep 15
kubectl -n "$NS" get pods -l app=api -o wide --no-headers | awk '{print "   ", $1, "READY="$2, "STATUS="$3, "RESTARTS="$4}'
[[ $(restarts) == "$before" ]] || fail "API restarted during the outage"

kubectl -n "$NS" scale statefulset/postgres --replicas=1 >/dev/null
kubectl -n "$NS" rollout status statefulset/postgres --timeout=180s >/dev/null
echo "$(ts) postgres back"
for _ in $(seq 1 30); do [[ $(status "$BASE/ready") == 200 ]] && break; sleep 2; done
echo "$(ts) ingress /ready: $("${CURL[@]}" -w ' [%{http_code}]' "$BASE/ready")"
kubectl -n "$NS" wait --for=condition=ready pod -l app=api --timeout=60s >/dev/null
after=$(restarts)
echo "restarts before: $before"
echo "restarts after:  $after"
[[ $after == "$before" ]] || fail "API restarted"
echo "chaos: OK (recovered without restarting the API)"

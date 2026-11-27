# Shared helpers for the verification scripts.
NS=evidenceops
HOST=evidenceops.local
BASE="https://$HOST:8443"
# Self-signed certificate: -k skips verification; --resolve avoids touching DNS.
CURL=(curl -sk --max-time 10 --resolve "$HOST:8443:127.0.0.1")
api_key() {
  kubectl -n "$NS" get secret evidenceops-secrets -o jsonpath='{.data.EVIDENCEOPS_API_KEYS}' \
    | base64 -d | cut -d, -f1
}
status() { "${CURL[@]}" -o /dev/null -w '%{http_code}' "$@"; }
restarts() {
  kubectl -n "$NS" get pods -l app=api -o jsonpath='{range .items[*]}{.metadata.name}={.status.containerStatuses[0].restartCount} {end}'
}

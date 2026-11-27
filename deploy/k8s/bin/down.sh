#!/usr/bin/env bash
# Remove the whole local cluster (volumes included).
set -euo pipefail
kind delete cluster --name evidenceops

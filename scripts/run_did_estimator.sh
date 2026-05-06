#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/run_did_estimator.sh path/to/config.yml" >&2
  exit 1
fi

Rscript .agents/skills/did-estimators/scripts/run_estimator.R "$1"

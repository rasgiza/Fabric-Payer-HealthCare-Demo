#!/bin/sh
# =============================================================================
# postprovision.sh — azd postprovision hook (POSIX).
#
# Runs after `azd provision` creates the Foundry account/project/model. Creates
# the Foundry-hosted agents (orchestrator + hosted copilots) on the freshly
# provisioned project via tools/deploy_data_agents.py --live --foundry-only.
#
# azd exports the Bicep outputs as environment variables:
#   FOUNDRY_PROJECT / AZURE_AI_PROJECT_ENDPOINT, FABRIC_WORKSPACE_ID,
#   PAYER_SEMANTIC_MODEL.
#
# Python interpreter resolution: $PYTHON -> repo-sibling ../.venv -> python3.
# =============================================================================
set -e

PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
  if [ -x "$SCRIPT_DIR/../../.venv/bin/python" ]; then
    PY="$SCRIPT_DIR/../../.venv/bin/python"
  else
    PY="python3"
  fi
fi

PROJECT="${FOUNDRY_PROJECT:-$AZURE_AI_PROJECT_ENDPOINT}"
WORKSPACE="${FABRIC_WORKSPACE_ID:-}"
MODEL="${PAYER_SEMANTIC_MODEL:-PayerAnalytics}"

if [ -z "$PROJECT" ]; then
  echo "FOUNDRY_PROJECT / AZURE_AI_PROJECT_ENDPOINT not set; cannot create agents." >&2
  exit 1
fi
if [ -z "$WORKSPACE" ]; then
  echo "WARNING: FABRIC_WORKSPACE_ID not set; orchestrator function-tool binding context will be incomplete." >&2
fi

echo "[postprovision] Creating Foundry agents on $PROJECT (fabric ws $WORKSPACE) using $PY"
"$PY" tools/deploy_data_agents.py --live --foundry-only --foundry-project "$PROJECT" --workspace-id "$WORKSPACE" --semantic-model "$MODEL"
echo "[postprovision] Foundry agents deployed."

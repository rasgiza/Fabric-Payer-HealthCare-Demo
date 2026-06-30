#Requires -Version 7
# =============================================================================
# postprovision.ps1 — azd postprovision hook (Windows).
#
# Runs after `azd provision` creates the Foundry account/project/model. Creates
# the Foundry-hosted agents (orchestrator + hosted copilots) on the freshly
# provisioned project via tools/deploy_data_agents.py --live --foundry-only.
#
# azd exports the Bicep outputs as environment variables for this hook:
#   FOUNDRY_PROJECT / AZURE_AI_PROJECT_ENDPOINT, FABRIC_WORKSPACE_ID,
#   PAYER_SEMANTIC_MODEL.
#
# Python interpreter resolution: $env:PYTHON -> repo-sibling ..\.venv -> python.
# =============================================================================
$ErrorActionPreference = 'Stop'

$py = $env:PYTHON
if (-not $py) {
    $venv = Join-Path $PSScriptRoot '..\..\.venv\Scripts\python.exe'
    if (Test-Path $venv) { $py = (Resolve-Path $venv).Path } else { $py = 'python' }
}

$project = $env:FOUNDRY_PROJECT
if (-not $project) { $project = $env:AZURE_AI_PROJECT_ENDPOINT }
$workspace = $env:FABRIC_WORKSPACE_ID
$model = $env:PAYER_SEMANTIC_MODEL
if (-not $model) { $model = 'PayerAnalytics' }

if (-not $project) {
    Write-Error 'FOUNDRY_PROJECT / AZURE_AI_PROJECT_ENDPOINT not set; cannot create agents.'
}
if (-not $workspace) {
    Write-Warning 'FABRIC_WORKSPACE_ID not set; orchestrator function-tool binding context will be incomplete.'
}

Write-Host "[postprovision] Creating Foundry agents on $project (fabric ws $workspace) using $py"
& $py tools/deploy_data_agents.py --live --foundry-only --foundry-project $project --workspace-id $workspace --semantic-model $model
if ($LASTEXITCODE -ne 0) { Write-Error "deploy_data_agents.py failed (exit $LASTEXITCODE)" }
Write-Host '[postprovision] Foundry agents deployed.'

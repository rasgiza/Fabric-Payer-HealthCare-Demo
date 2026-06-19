# Operations Runbook

Known failure modes and recovery for the Payer demo. Distinct from
[EXECUTIVE_RUNBOOK.md](EXECUTIVE_RUNBOOK.md) which is the 15-min / 45-min demo
presentation script.

> See [ARCHITECTURE.md](ARCHITECTURE.md) for what the launcher and `tools/deploy.py`
> actually do. This file is what to do when a step fails.

---

## Deploy-time failures (`tools/deploy.py`)

### `Item displayName does not match folder stem`

```
[deploy] FAIL  workspace/CFOAgent.DataAgent/  displayName='CFO Agent' != 'CFOAgent'
```

**Cause**: `tools/deploy.py` line ~109 guards against fabric-cicd silently
publishing the wrong-named item. The `.platform` `displayName` must equal the
folder stem.

**Fix**: edit `workspace/<Folder>.<Type>/.platform` so
`metadata.displayName == "<Folder>"`. Use the human-friendly name in
`Files/Config/publish_info.json` `description` instead.

### `Missing FABRIC_WORKSPACE_ID_<ENV>`

**Cause**: `workspace/parameter.yml` references `$(env:FABRIC_WORKSPACE_ID_DEV)`
which fabric-cicd resolves from the environment at publish time.

**Fix**:
```powershell
$env:FABRIC_WORKSPACE_ID_DEV = "<your dev workspace GUID>"
$env:AZURE_TENANT_ID         = "<tenant GUID>"
az login --tenant $env:AZURE_TENANT_ID
```

Dry-run does **not** require these; only live publish does.

### `Item type DataAgent not supported`

**Cause**: fabric-cicd `<` 0.1.30 — DataAgent shipped in 0.1.30. Ontology
shipped in 1.0.0.

**Fix**: `pip install -U "fabric-cicd>=1.1.0"`. Pin in `requirements.txt`.

### Topological order failures

Symptom: SemanticModel publishes before its source Lakehouse exists, or
DataAgent publishes before the SM it binds exists.

**Fix**: `tools/deploy.py` SUPPORTED_TYPES is ordered intentionally —
`Lakehouse → Environment → Notebook → DataPipeline → SemanticModel → Report →
Ontology → DataAgent → Eventhouse → KQLDatabase → Reflex → Eventstream`. If
fabric-cicd reports the inverse error, do not reorder; instead check that the
upstream item committed in the same commit and is present on disk.

---

## Launcher failures (`Healthcare_Launcher` Run All)

### Cell 1 — Knowledge upload returns 403 / 404 / rate-limit

Symptom (visible in cell output):
```
  GitHub Contents API returned 403; falling back to known inventory
  [WARN] failed to upload <name>: HTTPError 404
```

**Cause**: anonymous GitHub API rate-limit (60/hour/IP), private repo
without token, or a stale branch reference.

**Fix**: in the CONFIG cell set `GITHUB_TOKEN = "<PAT with repo:read>"` and
re-run only Cell 1. If the repo went private after the launcher was authored,
ensure the PAT has access to `rasgiza/Fabric-Payer-HealthCare-Demo`.

### Cell 2 — `NB_01_Bronze_Ingest` exits with `path not found`

Symptom:
```
[NB_01_Bronze_Ingest] exit=Files/synth/smoke/members.csv not found
```

**Cause**: smoke CSVs are not yet in `lh_bronze_raw/Files/synth/smoke/`.
The launcher does NOT regenerate synthetic data (the `NB_00_Generate_Smoke_Data`
notebook is deferred to a future B.x).

**Workaround until NB_00 ships**:
```powershell
# On a machine with the repo cloned + .venv active:
python tools/run_local_etl.py --run-id smoke --scale 0.005 --seed 42
# Then upload data/synth/smoke/*.csv into lh_bronze_raw/Files/synth/smoke/
# via OneLake file explorer, Azure Storage Explorer, or AzCopy.
```

Then re-run Cell 2 with `RUN_BRONZE=True`.

### Cell 3 — `[FAIL] <Agent> getDefinition HTTP 401`

**Cause**: the Fabric runtime token returned by `notebookutils.credentials.getToken("pbi")`
lacks `DataAgent.ReadWrite.All` (or is expired in a long-running notebook session).

**Fix**: restart the Spark session, ensure the launcher's runtime identity has
**Contributor** on the workspace, re-run Cell 3.

### Cell 3 — `[DROP] <Agent>/<displayName>: unpatched placeholder`

**Cause**: the DataAgent's `datasource.json` has a `type` not in
`{lakehouse_tables, semantic_model, graph}` (e.g. a `kql_db` for an agent we
later evolve) AND its `artifactId` is the zero-GUID placeholder. The launcher
drops the part rather than publish a broken binding.

**Fix**: extend the `ds_type_map` in Cell 3 with the new datasource type and
its target item discovery rule (display-name match against `/workspaces/{wid}/items`).

### Cell 3 — `[FAIL] <Agent> updateDefinition HTTP 409`

**Cause**: the agent has a concurrent draft locked by another user editing
in the Fabric portal.

**Fix**: ask the user to discard their draft, or wait 5 minutes for the lock
to expire, then re-run Cell 3 (it's idempotent — only patches placeholders).

### Cell 4 — `[launcher] FAIL — empty gold tables: [...]`

**Cause**: Cell 2's ETL chain ran but a downstream notebook silently produced
an empty aggregate (typically because a silver fact table was empty due to a
filter mismatch).

**Fix**: open `NB_02_Silver_Transform` and `NB_03_Gold_Build`, re-run cell by
cell, watch for row-count drops between silver and gold. The 8 gold tables
the launcher checks are the surfaces the 7 DataAgents bind to — any one of
them empty means at least one agent will return zero rows for its persona's
hero question.

### Long-running operation never completes

Symptom: `getDefinition` or `updateDefinition` returns 202 but `_poll_lro` loops
60 times (~5 min at Retry-After=5) and times out.

**Fix**: the Fabric REST LRO occasionally returns `resourceLocation` with a
malformed path. The launcher falls back to `{loc}/result`. If both fail, run
the patch manually:
1. In Fabric portal → DataAgent → View definition → copy current
   `datasource.json` content.
2. Replace `artifactId` / `workspaceId` with the real ids printed by the
   launcher's discovery line ("`Discovered: lakehouse=...`").
3. Save in the portal (drives the same LRO but via UI).

---

## Hosted agent failures (`tools/deploy_data_agents.py --live`)

### `RuntimeError: foundry_project required for live deploy`

**Cause**: live branch needs the Foundry project endpoint.

**Fix**:
```powershell
python tools/deploy_data_agents.py --live `
  --foundry-project "https://<resource>.services.ai.azure.com/api/projects/<proj>"
```

### `ImportError: agent_framework_azure_ai`

**Cause**: SDK is lazy-imported only on `--live`; not installed.

**Fix**: `pip install "agent-framework-azure-ai==1.9.0"`. Pinned in
`requirements.txt`.

### `Unsupported parameter: api_version`

**Cause**: stale `agent.yaml` still has `api_version: 2026-04-01-preview`.
B.4 dropped this — Foundry GA uses the Responses API directly; classic
Assistants API retires 2027-03-31.

**Fix**: remove the `api_version` key from `data_agents/PAReviewCopilot.HostedAgent/agent.yaml`.
`tests/test_pareviewcopilot_shape.py::test_agent_yaml_uses_responses_api`
catches this in CI.

---

## Data fidelity / synthetic data failures

### `tools/data_fidelity.py` reports `near_duplicate_rx` skew

**Cause**: a refactor to `tools/gen_payer_overlay.py` randomized the month
when it should pace `min(12, f+1)` (the A.0b lesson).

**Fix**: revert the offending generator, re-run with `--scale 0.005 --seed 42`,
re-run `data_fidelity.py`.

### `near_duplicate_rx` over-fires on smoke run

Smoke (`scale=0.005` → 500 members) inherently has fewer duplicates than
production. `data_fidelity.py` has smoke tolerances built in; if you've
custom-scaled the run, adjust the threshold there rather than weakening the
generator.

---

## CI failures

### `pytest` fails only in CI, passes locally

**Cause** (most common): the smoke run is missing or stale in CI's cache.

**Fix**: ensure `.github/workflows/ci.yml` runs
`python tools/run_local_etl.py --run-id smoke` **before** `pytest`.

### `tools/deploy.py --env dev --dry-run` fails with item count != 19

Symptom:
```
[deploy] 18 item(s) would be published
```

**Cause**: one of the `workspace/<X>.<Type>/.platform` files is malformed or a
`Files/` payload is missing.

**Fix**: run `python tools/deploy.py --env dev --dry-run -v` (verbose), look
for the `[skip]` line, fix the offending folder. `test_workspace_skeleton.py`
and per-item shape tests are usually a faster path to the root cause.

---

## Escalation

If a step is not in this runbook, check:
1. `/memories/repo/fabric-payer-only-state.md` — full commit history with the
   why behind each decision.
2. `docs/_internal/known_issues.md` — issues that are open but not yet
   workarounds.
3. The relevant test under `tests/test_<item>_shape.py` — the assertions
   document the contract more precisely than prose.

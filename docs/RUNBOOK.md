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

> **Note (fabric-cicd 1.1.0):** the SDK has its own hard-coded publish order
> that ignores `deployment.yaml spec.itemOrder`. We keep `itemOrder` in YAML
> as authoritative documentation, and use `--only <Type>` to publish a single
> slice when SDK order isn't right for a one-off re-publish.

### `Data source ArtifactId cannot be an empty GUID`

```
[deploy] fabric-cicd publish failed: ... InvalidContent: Data source
ArtifactId cannot be an empty GUID. ArtifactId: '00000000-...'
```

**Cause**: The repo source-of-truth stores `00000000-...` placeholders in every
`<Agent>.DataAgent/Files/Config/{draft,published}/<type>-<name>/datasource.json`
(keeps the tree portable across tenants). fabric-cicd 1.1.0 rejects empty GUIDs
at publish time.

**Fix**: `tools/deploy.py` automatically rebinds these to live workspace GUIDs
via `tools/bind_data_agent_sources.stage_workspace()` before calling
`publish_all_items`. The rebind reads the target workspace via Fabric REST API
and rewrites a staged copy at `.staging/workspace/`. If you see this error,
your active `az login` likely can't list items in the target workspace —
verify with:

```powershell
az rest --method get --url "https://api.fabric.microsoft.com/v1/workspaces/$env:FABRIC_WORKSPACE_ID_DEV/items" --resource "https://api.fabric.microsoft.com"
```

The staged copy also removes datasource folders whose target item is absent
(e.g. `graph-Payer_Ontology` while Ontology is in `optionalItems`).

### `TMDL Format Error: InvalidLineType ... Document - './cultures/en-US'`

**Cause**: Older PayerAnalytics SM revisions embedded a `linguisticMetadata`
JSON block inside `cultures/en-US.tmdl`. The Fabric TMDL parser reads the
JSON's `"Version": "1.0.0"` line as a malformed TMDL "Other" line type.

**Fix**: keep `cultures/en-US.tmdl` minimal:

```tmdl
cultureInfo en-US
```

Fabric defaults to en-US without an explicit linguisticMetadata block.

### Q&A synonyms / SM-Ontology cross-talk after parameter-replace

Symptom: PayerAnalytics SM definition contains a `lineageTag` GUID that is
byte-identical to a `Payer_Ontology` `logicalId`. fabric-cicd's parameter
substitution treats all occurrences identically, causing wrong-target
rewrites at publish.

**Fix**: never reuse `d5...` GUIDs across item types. SM `lineageTag` values
live entirely inside the SM TMDL and should be plain `uuid4()` — they have no
cross-item semantics. The PayerAnalytics expression's `lineageTag` was changed
from `d5000005-0001-0001-0001-000000000002` (collided with Ontology) to
`d5000005-0001-0001-0001-000000000099` in v1.1.

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
catches this in CI. The same check runs for `PayerRT_Copilot.HostedAgent` via
`tests/test_payerrt_copilot_shape.py::test_agent_yaml_uses_responses_api`.

### `tool_call_failed: get_pa_latency_window`  (or get_emergency_admit_worklist / get_siu_suspect_claims)

**Cause**: `PayerRT_Copilot.HostedAgent` v1 ships PHI-minimized **zero-count stubs** for
the 3 KQL function tools — they return the right schema but don't actually query
`kqldb_payer_rt` yet. If you wired the agent live before C.x ships the real KQL
binding, the tool returns the stub envelope unchanged and the recommendation
degrades to `monitor`.

**Fix**: this is by design for v1; no action needed unless you've manually patched
the stubs and broken the contract. Run
`pytest tests/test_payerrt_copilot_shape.py -k validates` to re-prove input
validation still works.

### `PayerRT_Copilot` recommends something other than {dispatch_outreach, open_pa_investigation, open_siu_case, monitor}

**Cause**: model drift produced a free-text recommendation outside the locked
enum. The structured-output schema (`output_schema.json`) should refuse, but a
mis-pinned model snapshot may bypass it.

**Fix**: confirm `agent.yaml` `foundry.model` points to a structured-outputs-capable
model (gpt-4.1-mini or newer). The recommendation enum is locked by
`tests/test_payerrt_copilot_shape.py::test_recommendation_enum_locked`.

---

## RTI (Stream C) failure modes

### Eventhouse `eh_payer_rt` not provisioned in workspace

Symptom (Activator rule never fires; NB_RTI_02/03/04 cells fail with
`Database 'kqldb_payer_rt' not found`):

**Cause**: fabric-cicd 1.1.0 ships Eventhouse + KQLDatabase as `.platform`-only
stubs in this repo (we don't yet have a published companion-JSON shape from a
real Fabric Git export). On first deploy to a fresh workspace, the Eventhouse
resource is created but the KQL DB may need a portal-side cluster bind.

**Fix**:
1. Open the workspace → `eh_payer_rt` → confirm Eventhouse status = Active.
2. Open `kqldb_payer_rt` → if it shows "Initializing," wait 2-5 min then retry NB_RTI_01.
3. If still failing, drop and recreate via portal; the fabric-cicd manifest is
   idempotent on next `tools/deploy.py --env dev`.

### Eventstream `es_claims_arrivals` shows 0 events/sec

**Cause**: no producer is publishing to the stream. NB_RTI_01 (ingest notebook)
only *consumes* from the stream; it doesn't generate events.

**Fix**: in v1 the producer is the smoke/replay job; for live demo runs use the
portal's built-in Sample Data source temporarily, or run
`python tools/replay_rti.py --topic claim_arrivals` (deferred to v1.1 — see
"Known v1.1 follow-ups" below).

### `PayerOps_Activator` rule defined but never fires

**Cause**: rule predicates (`pa_denial_rate_spike`: `decisions>=50 AND breach_rate>0.20`,
`siu_intake_score_alert`: `intake_score>=0.6`) are tuned for steady traffic.
Smoke data has fewer than 50 decisions per window so `pa_denial_rate_spike`
intentionally suppresses.

**Fix**: for demo, override thresholds in the portal rule editor (Activator UI),
or lower the `min_decisions` floor temporarily. The locked design lives in
`tests/test_rti_c4_skeleton.py::EXPECTED_RULES`; revert any threshold edits
before committing.

### Flip hosted-agent dry-run → live

Default `python tools/deploy_data_agents.py` is `--dry-run`. To deploy
`PAReviewCopilot.HostedAgent` and `PayerRT_Copilot.HostedAgent` for real:

```powershell
$env:FOUNDRY_PROJECT     = "https://<resource>.services.ai.azure.com/api/projects/<proj>"
$env:FABRIC_WORKSPACE_ID = "<workspace GUID>"  # so KB upload path resolves
az login --tenant $env:AZURE_TENANT_ID
python tools/deploy_data_agents.py --live --foundry-project $env:FOUNDRY_PROJECT
```

Expected tail line:
```
[deploy] OK  function_tools=7  orchestrator=MissionControlOrchestrator  hosted=2
```

If you see `hosted=1`, one `*.HostedAgent/` folder failed payload build — check
the `[ERR]` line above; the most common cause is a missing knowledge_source
file referenced in `agent.yaml`.

---

## Known v1.1 follow-ups

These are deliberate v1 gaps that customers must be warned about up front:

1. **Hosted-agent KQL tool stubs.** The 3 tools on `PayerRT_Copilot.HostedAgent`
   (`get_pa_latency_window` / `get_emergency_admit_worklist` /
   `get_siu_suspect_claims`) return PHI-minimized zero-count envelopes in v1.
   v1.1 wires them to the real `kqldb_payer_rt` queries shipped in
   NB_RTI_02/03/04.
2. **Foundry Hosted agents are PREVIEW.** Both `PAReviewCopilot.HostedAgent`
   and `PayerRT_Copilot.HostedAgent` run on the Foundry Hosted-agent service,
   currently in preview. Production deployments must call this out in the
   customer's risk register.
3. **MCP custom server runtime is preview.** The `/runtime/webhooks/mcp` path
   (Azure Functions) used by the v1.1 customer-extension story is still in
   preview as of 2026-06-10.
4. **Reflex Git-exportable rule descriptor JSON is not yet published.** Microsoft
   has not yet documented the companion-JSON shape for Reflex rules; the v1
   `PayerOps_Activator.Reflex` ships as a `.platform`-only stub with the rule
   designs locked in `tests/test_rti_c4_skeleton.py`. When the JSON shape lands,
   we'll generate the descriptor from those test fixtures (no rule-design rework).
5. **NB_00_Generate_Smoke_Data deferred.** Fresh-workspace one-click still
   requires the user to upload smoke CSVs out-of-band (see
   `python tools/run_local_etl.py --run-id smoke` flow above).
6. **Ontology (Payer_Ontology) deferred to phase 2.** The Fabric Ontology
   preview backend rejects fabric-cicd 1.1.0's `updateDefinition` payload
   (`ALMOperationImportFailed`). The GA DataAgent path = SemanticModel +
   Lakehouse (already wired); the optional graph datasource targets Ontology
   when present. Re-enable by removing `Payer_Ontology.Ontology` from
   `spec.optionalItems` in `deployment.yaml`. The seven DataAgents will pick
   up the `graph-Payer_Ontology` datasource on the next
   `tools/deploy.py --confirm` run; `tools/bind_data_agent_sources.py`
   automatically resolves Ontology GUIDs once it appears in the workspace.

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

# Fabric Payer Healthcare Demo

End-to-end Microsoft Fabric demo for **U.S. health-insurance payers** — synthetic data, medallion lakehouse, payer ontology + graph, semantic model, **7 Foundry data agents + 2 hosted Copilots**, real-time intelligence (Eventhouse + KQL DB + Eventstream + Activator + RTI hosted Copilot), and a one-click launcher.

> **Status:** **Streams A + B + C shipped** through commit [`933e59a`](https://github.com/rasgiza/Fabric-Payer-HealthCare-Demo/commit/933e59a). Workspace-shaped artifacts under `workspace/` (4 lakehouses, 9 notebooks incl. `Healthcare_Launcher` + 3 RTI analytic notebooks, 2 data pipelines, `PayerAnalytics` Direct Lake semantic model, `Payer_Ontology`, 7 Foundry data agents, `kqldb_payer_rt` KQLDatabase, `eh_payer_rt` Eventhouse, `es_claims_arrivals` Eventstream, `PayerOps_Activator` Reflex) publish via fabric-cicd 1.1.0; `PAReviewCopilot.HostedAgent` + `PayerRT_Copilot.HostedAgent` deploy via Foundry SDK out-of-band. The launcher is Jumpstart-ready: pulls `payer_knowledge/*.md` from GitHub raw and rebinds the 7 agents' zero-GUID placeholders to live workspace ids on Run All. **Streams D (eval automation + observability) is next.**
>
> **Two install paths**: (1) **Analyst / Jumpstart** — open `Healthcare_Launcher` in a Fabric workspace that has the items deployed, Run All, done. (2) **Platform team / CI** — `tools/deploy.py` wraps fabric-cicd for dev / staging / prod promotion.

> **Preview disclosures:** `PAReviewCopilot.HostedAgent` and `PayerRT_Copilot.HostedAgent` run on the Foundry **Hosted-agent service** which is currently in **PREVIEW**. The Power BI report uses **PBIR (still preview)** as of 2026-06-10. Customer production deployments must call out both.

---

## Why this demo exists

U.S. payers lose billions per year to denial leakage, Stars cut-point gaps, risk-adjustment under-coding, fraud, and disconnected operational data. This demo shows how a single Microsoft Fabric workspace + Foundry agents collapses that toolchain into one industry-grounded experience.

Every artifact in this repo — every table, every measure, every agent question, every dashboard — traces back to a documented industry pain point with a public citation. See [`docs/pain_points.md`](docs/pain_points.md) (31 pain points) and [`docs/coverage_matrix.md`](docs/coverage_matrix.md) (pain points → questions → tables → measures → agents).

## Personas covered (v1)

| # | Persona | Foundry agent | Top concerns |
|---|---|---|---|
| 1 | CFO / Revenue Cycle | `CFOAgent` | Denial rate, AR days, MLR, leakage, NSA/IDR backlog |
| 2 | Stars / Quality | `StarsAgent` | Cut-point gaps, HEDIS MY2026, PDC, CMR completion |
| 3 | Risk Adjustment | `RiskAdjustmentAgent` | RAF accuracy, HCC V28 suspect codes, OIG audit posture |
| 4 | SIU / Fraud, Waste & Abuse | `SIUAgent` | Upcoding, phantom billing, telefraud, scheme detection |
| 5 | Care Management / Pop Health | `CareMgmtAgent` | Rising-risk, ED super-utilizers, SDOH integration |
| 6 | Network & Contracting | `NetworkAgent` | Network adequacy, VBC/APM mix, contract analytics |
| 7 | UM / Prior Authorization | `UMAgent` | TAT, CMS-0057-F readiness, peer-to-peer overturn |
| + | UM Reviewer Copilot | `PAReviewCopilot.HostedAgent` | Hosted PA-decision support; pointer-not-text policy citation discipline |
| + | RTI Ops Triage Copilot | `PayerRT_Copilot.HostedAgent` | Routes live RTI signals to UM / CareMgmt / SIU; routing-only (never adjudicates); CMS-0057-F cited when opening PA investigation |

All 7 data agents bind 1:1 to the **PayerAnalytics** semantic model (`fabric_data_agent.max_items = 1`, the documented Foundry constraint). The hosted Copilot is a separate reviewer-side agent that calls `ask_um_agent` and `ask_risk_agent` as function tools.

## Microsoft Foundry surfaces in use

Canonical names per Microsoft Learn (verified 2026-06-10):

- **Fabric data agents** (GA): one agent per persona, bound to `PayerAnalytics.SemanticModel`.
- **Foundry Prompt agents** (GA): the 7 `*.DataAgent` definitions.
- **Foundry Hosted agents** (PREVIEW): `PAReviewCopilot.HostedAgent` (UM reviewer; calls UMAgent + RiskAdjustmentAgent) and `PayerRT_Copilot.HostedAgent` (RTI ops triage; 3 KQL function tools + delegates to UMAgent / CareMgmtAgent / SIUAgent).
- **Foundry platform tools** — canonical brand names for v1.1 hookups: **Fabric IQ** (data + analytics into Fabric), **WorkIQ** (M365 work-context grounding), **SharePoint** (doc libraries).
- **Foundry Toolbox** (preview) and **custom MCP servers on Azure Functions** (`/runtime/webhooks/mcp`) — the two MCP integration paths for v1.1 customer extensions.
- **Eventhouse** (GA) — Phase 6 RTI backbone.
- **Microsoft Agent Framework** (`github.com/microsoft/agent-framework`) — canonical Microsoft framework if Hosted-agent orchestration is ever lifted out of the demo's MCPTool path.

Full surface inventory + verify-before-coding queue: [`docs/_internal/api_delta_2026-06.md`](docs/_internal/api_delta_2026-06.md).

## Repo layout

```
docs/                 industry truth: pain points, coverage matrix, sample questions, story, runbook
  ARCHITECTURE.md     ← one-page architecture (4 lakehouses + SM + ontology + 7 agents + hosted Copilot)
  RUNBOOK.md          ← ops failure modes + recovery (distinct from EXECUTIVE_RUNBOOK demo script)
  personas/           one-page card per persona
  _internal/          api_delta scan, adopt list, known issues (not customer-facing)
data_agents/          one folder per Foundry agent
  *.DataAgent/        7 Fabric-bound prompt agents (aiInstructions.md + binding.yaml + fewshots + eval)
  *.HostedAgent/      1 hosted Copilot (agent.yaml + tool_schemas + output_schema + fewshots + eval)
mission_control/      orchestrator router (orchestrator.{yaml,py}) — 6 refusal pattern families
payer_knowledge/      KB for grounded RAG (HEDIS / CMS / OIG / policy_citation_pattern.md)
infra/                Bicep / Fabric workspace provisioning (Phase 7)
notebooks/            Synthea generation, ETL, RTI scoring, launcher (Phase 7)
report/               PayerAnalytics semantic model + report (TMDL + PBIR)
tools/                check_citations.py, audit_data.py, audit_rels.py, data_fidelity.py,
                      eval_agents_offline.py, deploy_data_agents.py, gen_*
tests/                pytest harness (15 tests) — wraps audits + fidelity + agent-shape checks
.github/workflows/    CI: lint (ruff), citations, tests (pytest)
citations.yaml        single source of truth — 20 industry citations, all with year + url + quote
pyproject.toml        ruff config + pytest config
requirements-dev.txt  pyyaml, pandas, networkx, jsonschema, pytest, ruff
```

## Phase plan

| Phase | What | Status |
|---|---|---|
| 0a | Repo skeleton + citation backbone + persona cards + API delta scan | ✅ shipped |
| 0b | Pain points + coverage matrix + sample questions + red-team review | ✅ shipped (31 PP, 116 questions, 20 citations) |
| 0c | Per-agent `aiInstructions.md` + demo story + executive runbook | ✅ shipped |
| 1 | Synthea + payer overlay (claims, eligibility, RA, quality, PA, appeals) | ✅ shipped (`d8f4110`) |
| 2 | Medallion lakehouse + ETL | ✅ shipped (`d8f4110`) |
| 3 | Payer ontology + NetworkX graph | ✅ shipped (`b2be975`) — 12/12 KPI, 16/16 calibration |
| 4 | PayerAnalytics TMDL semantic model + PBIR report | ✅ shipped (`e28aa9f`) |
| 5 | 7 Foundry data agents + MissionControlOrchestrator + payer KB | ✅ shipped (`05ef942`) |
| 5.5 | PAReviewCopilot hosted Foundry agent | ✅ shipped (`0e42e49`) |
| 1A | api_delta refresh against 2026-06-10 MS Learn | ✅ shipped (`c698b20`) |
| 1B | pytest harness + ruff + CI | ✅ shipped (`b052bd4`) — 15 tests, ruff clean |
| 1C | data-fidelity gate (9 checks) | ✅ shipped (`fe98a8f`) |
| 1D | README accuracy pass | ✅ shipped |

### Stream A — workspace skeleton + medallion (Fabric Git Integration v2.0)

| Phase | What | Status |
|---|---|---|
| A.0a/b/c | Catalog expansion + data realism + ETL extension | ✅ `ca91c10` / `34dcfeb` / `7cab69b` |
| A.1 | 4 lakehouses (`lh_bronze_raw`, `lh_silver_stage`, `lh_silver_ods`, `lh_gold_curated`) | ✅ `4c96510` |
| A.2 | 3 medallion notebooks (NB_01 / NB_02 / NB_03) | ✅ `f217c4c` |
| A.3 | 2 data pipelines (PL_Payer_Full_Load + PL_Payer_Master) | ✅ `09c5f89` |
| A.4-A.7 | `Healthcare_Launcher` + `tools/deploy.py` + CI + README | ✅ `168825e` |

### Stream B — Foundry agents + Jumpstart launcher

| Phase | What | Status |
|---|---|---|
| B.0 | Platform alignment (DefaultAzureCredential, agent-framework 1.9.0, Ontology in itemOrder) | ✅ `f0e8ccc` |
| B.1 | `PayerAnalytics.SemanticModel` (Direct Lake, 35 tables, 32 rels, 15 measures) | ✅ `4f47807` |
| B.2 | `Payer_Ontology` (26 entities, 32 relationships) | ✅ `7cc3919` |
| B.3 | 7 Foundry DataAgents (CFO / Stars / RA / SIU / CareMgmt / Network / UM) | ✅ `406c821` |
| B.3.5 | Launcher extended for Jumpstart (knowledge upload + DataAgent ID patching) | ✅ `538f3cb` |
| B.4 | `PAReviewCopilot.HostedAgent` made deployable (Responses API; tool stubs; live deploy path) | ✅ `b1b0826` |
| B.5-B.7 | Tests polish + deploy.py polish + docs (this commit) | 🟡 in flight |

### Stream C — RTI (Eventhouse + KQL + Eventstream + Activator + hosted RTI Copilot)

| Phase | What | Status |
|---|---|---|
| C.1 | `eh_payer_rt` Eventhouse + `kqldb_payer_rt` KQLDatabase skeletons + tests | ✅ `d22f43f` |
| C.2 | `es_claims_arrivals` Eventstream + NB_RTI_01 ingest notebook | ✅ `d77ea0b` |
| C.3 | 3 RTI analytic notebooks (NB_RTI_02 auth_lifecycle / NB_RTI_03 adt_admissions / NB_RTI_04 claim_arrivals) | ✅ `5d59749` |
| C.4 | `PayerOps_Activator.Reflex` skeleton + 2 locked rule designs (pa_denial_rate_spike, siu_intake_score_alert) | ✅ `1f676a8` |
| C.5 | `PayerRT_Copilot.HostedAgent` (6 tools: 3 KQL function tools + 3 DataAgent delegates; routing-only; RTIOpsEnvelope) | ✅ `933e59a` |

### Stream D — Eval automation + observability

| Phase | What | Status |
|---|---|---|
| D.1 | `tools/run_evals.py` + `tests/test_eval_thresholds.py` (Foundry batch-eval for both hosted Copilots) | ⏳ next |
| D.2 | App Insights wiring on hosted-agent deploy + `monitoring/*.json` workbooks | ⏳ next |

### Deferred

| Phase | What | Status |
|---|---|---|
| Future B.x | `NB_00_Generate_Smoke_Data` (the remaining gap before true fresh-workspace one-click) | ⏳ deferred |

Detailed planning substrate: [`docs/_internal/api_delta_2026-06.md`](docs/_internal/api_delta_2026-06.md), [`docs/_internal/adopt_list.md`](docs/_internal/adopt_list.md), [`docs/_internal/known_issues.md`](docs/_internal/known_issues.md).

## Getting started (local)

The repo is reproducible offline against the bundled smoke run; no Fabric workspace or Foundry account is required to validate the gates.

```powershell
# 1. Install dev deps (pyyaml, pandas, networkx, jsonschema, pytest, ruff)
pip install -r requirements-dev.txt

# 2. Lint
ruff check .

# 3. Run the test suite (15 tests, ~3s)
pytest

# 4. Audit referential integrity + distributions on the bundled smoke run
python tools/audit_data.py --run-dir data/synth/smoke

# 5. Audit ontology relationships
python tools/audit_rels.py --run-id smoke

# 6. Run the strict data-fidelity gate (9 checks)
python tools/data_fidelity.py --run-dir data/synth/smoke

# 7. Run the offline eval gate (routing >=90% / refusals 100% / hosted 0-fail)
python tools/eval_agents_offline.py

# 8. Citation linter (every [CIT:<id>] in any markdown resolves to citations.yaml)
python tools/check_citations.py

# 9. Validate the workspace tree (dry-run; no Fabric workspace needed)
python tools/deploy.py --env dev --dry-run
```

CI runs all of the above on every push and PR (`.github/workflows/ci.yml`).

## Deploying to a Fabric workspace

Stream A ships a self-contained medallion deployment: 4 lakehouses, 4 notebooks
(NB_01 bronze + NB_02 silver + NB_03 gold + Healthcare_Launcher), and 2 data
pipelines (PL_Payer_Full_Load chain + PL_Payer_Master orchestrator). All items
live under `workspace/` in Fabric Git Integration v2.0 format and publish via
[fabric-cicd 1.1.0](https://pypi.org/project/fabric-cicd/) wrapped by
`tools/deploy.py`.

```powershell
# Set per-environment workspace IDs (or use Azure Key Vault in CI)
$env:FABRIC_WORKSPACE_ID_DEV = "<your dev workspace GUID>"
$env:AZURE_TENANT_ID         = "<tenant GUID>"

# Authenticate (DefaultAzureCredential — az login, MSI, or service principal)
az login --tenant $env:AZURE_TENANT_ID

# Preview the deploy
python tools/deploy.py --env dev --dry-run

# Publish to the dev workspace
python tools/deploy.py --env dev

# Production publish (guarded by --confirm)
python tools/deploy.py --env prod --confirm
```

After publish, open the `Healthcare_Launcher` notebook in the Fabric workspace
and **Run All**. As of B.3.5, the launcher does four things in order:

1. **Upload** all 15 `payer_knowledge/*.md` from GitHub raw → `lh_gold_curated/Files/payer_knowledge/`
   (Fabric Git Integration ships workspace items, not loose markdown).
2. **Run** the medallion notebook chain `NB_01` → `NB_02` → `NB_03` against
   `Files/synth/smoke/` with `RUN_ID="smoke"`, `MODE="overwrite"`.
3. **Patch** all 7 Foundry DataAgent definitions in place: discovers the live
   ids of `lh_gold_curated`, `PayerAnalytics`, `Payer_Ontology` via
   `/workspaces/{wid}/items` and rewrites the zero-GUID `artifactId` /
   `workspaceId` placeholders committed in each agent's
   `Files/Config/{draft,published}/<ds>/datasource.json` via Fabric REST
   `getDefinition` → `updateDefinition` (handles 202 LRO with `Retry-After`).
4. **Verify** the 8 must-have gold tables and print a workspace publish-state
   summary.

Each step has a toggle in the launcher's CONFIG cell
(`UPLOAD_KNOWLEDGE_DOCS`, `RUN_ETL`, `PATCH_DATA_AGENTS`, `RUN_SANITY_CHECK`)
so you can iterate on any single step without re-running the others.

The `PAReviewCopilot.HostedAgent` and `PayerRT_Copilot.HostedAgent` hosted Foundry
agents deploy separately via
`python tools/deploy_data_agents.py --live --foundry-project <endpoint>` —
they're not fabric-cicd item types. Run `--dry-run` first to preview
(`hosted-agents=2`).

**Known gap** before true fresh-workspace one-click: smoke CSVs must be
present at `lh_bronze_raw/Files/synth/smoke/` for Step 2 to succeed. Today
that's the job of `python tools/run_local_etl.py` against an OneLake-mounted
path; a future `NB_00_Generate_Smoke_Data` notebook will close that gap. See
[docs/RUNBOOK.md](docs/RUNBOOK.md) for the workaround.

## Sample questions

116 sample questions across all 7 personas + the hosted Copilot, plus refusal cases for the safety gate:

- 99 happy-path questions (16 CFO, 16 Stars, 13 RA, 13 SIU, 13 CareMgmt, 9 Network, 9 UM, 4 Copilot, 6 cross-persona)
- 17 refusal cases (PHI exfil, hallucination bait, decision-authority probes, clinical-diagnosis requests, out-of-scope, coding-violations)

See [`docs/sample_questions.md`](docs/sample_questions.md).

## What's intentionally not in v1

- LangChain / Semantic Kernel / AutoGen orchestration layers (Foundry SDK + MCPTool composition only)
- PBIX binary format (TMDL + PBIR only — PBIR is preview, disclosed)
- Account-scoped MSI on connections (project-scoped only — see [`/memories/repo/foundry-mcp-gotchas.md`](https://github.com/) for the gotcha that bit us)
- DocIntake and SIUCase hosted agents (deferred to v1.1; pattern is established by `PAReviewCopilot.HostedAgent`)

Full Tier-4 exclusion list: [`docs/_internal/adopt_list.md`](docs/_internal/adopt_list.md#tier-4--explicitly-not-used-in-v1).

## Demo vs accelerator

Currently shipping as a **reproducible reference demo**. Conversion to an **accelerator** (one-click multi-tenant deploy with parameterized workspace IDs, capacity SKUs, and tenant secrets) is gated on the Phase 7 launcher and the Fabric Variable Library hookup. See `docs/_internal/api_delta_2026-06.md` row 26 for the parameterization design.

## License

[Apache-2.0](LICENSE).


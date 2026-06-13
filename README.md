# Fabric Payer Healthcare Demo

End-to-end Microsoft Fabric demo for **U.S. health-insurance payers** — synthetic data, medallion lakehouse, payer ontology + graph, semantic model, **7 Foundry data agents + 1 hosted reviewer Copilot**, real-time intelligence, and a one-click launcher.

> **Status:** **Phase 5.5 trimmed shipped** (commit [`0e42e49`](https://github.com/rasgiza/Fabric-Payer-HealthCare-Demo/commit/0e42e49)). 7 Foundry data agents (CFO / Stars / Risk Adjustment / SIU / Care Mgmt / Network / UM) + 1 hosted PA-review Copilot, MissionControlOrchestrator router, payer KB, offline eval gate, pytest + ruff CI, data-fidelity gate. Phase 6 (RTI Eventhouse + Activator) and Phase 7 (launcher + governance + 3D story page) are next.

> **Preview disclosures:** `PAReviewCopilot.HostedAgent` runs on the Foundry **Hosted-agent service** which is currently in **PREVIEW**. The Power BI report uses **PBIR (still preview)** as of 2026-06-10. Customer production deployments must call out both.

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

All 7 data agents bind 1:1 to the **PayerAnalytics** semantic model (`fabric_data_agent.max_items = 1`, the documented Foundry constraint). The hosted Copilot is a separate reviewer-side agent that calls `ask_um_agent` and `ask_risk_agent` as function tools.

## Microsoft Foundry surfaces in use

Canonical names per Microsoft Learn (verified 2026-06-10):

- **Fabric data agents** (GA): one agent per persona, bound to `PayerAnalytics.SemanticModel`.
- **Foundry Prompt agents** (GA): the 7 `*.DataAgent` definitions.
- **Foundry Hosted agents** (PREVIEW): `PAReviewCopilot.HostedAgent` — container/zip ship, dedicated Entra identity, structured-outputs envelope.
- **Foundry platform tools** — canonical brand names for v1.1 hookups: **Fabric IQ** (data + analytics into Fabric), **WorkIQ** (M365 work-context grounding), **SharePoint** (doc libraries).
- **Foundry Toolbox** (preview) and **custom MCP servers on Azure Functions** (`/runtime/webhooks/mcp`) — the two MCP integration paths for v1.1 customer extensions.
- **Eventhouse** (GA) — Phase 6 RTI backbone.
- **Microsoft Agent Framework** (`github.com/microsoft/agent-framework`) — canonical Microsoft framework if Hosted-agent orchestration is ever lifted out of the demo's MCPTool path.

Full surface inventory + verify-before-coding queue: [`docs/_internal/api_delta_2026-06.md`](docs/_internal/api_delta_2026-06.md).

## Repo layout

```
docs/                 industry truth: pain points, coverage matrix, sample questions, story, runbook
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
| 1D | README accuracy pass (this commit) | 🟡 in flight |
| 6 | RTI: Eventhouse + KQL update policies + Activator + Power Automate MTTR loop | ⏳ next |
| 7 | Launcher notebook + Purview governance + 3D story page + Direct Lake rebind | ⏳ |

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
```

CI runs steps 2, 3, and 8 on every push and PR (`.github/workflows/ci.yml`).

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


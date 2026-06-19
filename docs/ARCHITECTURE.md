# Architecture

One-page reference for how the Payer demo's workspace artifacts fit together.
Companion to [README.md](../README.md) and [DEMO_STORY.md](DEMO_STORY.md).

## High-level

```
        ┌─────────────────────────────────────────────────────────────────┐
        │                    GitHub: Fabric-Payer-HealthCare-Demo         │
        │  workspace/  data_agents/  tools/  payer_knowledge/  tests/     │
        └───────────────┬────────────────────────────┬────────────────────┘
                        │ tools/deploy.py            │ Healthcare_Launcher
                        │ (fabric-cicd, CI path)     │ (Run All, analyst path)
                        ▼                            ▼
        ┌─────────────────────────────────────────────────────────────────┐
        │                  Fabric workspace (one per env)                 │
        │                                                                 │
        │   Lakehouses        Notebooks        Pipelines   SM   Ontology  │
        │   ┌───────────┐    ┌──────────┐    ┌──────────┐                 │
        │   │ bronze    │───▶│ NB_01    │───▶│ PL_Full  │                 │
        │   │ silver_*  │    │ NB_02    │    │ PL_Master│                 │
        │   │ gold      │───▶│ NB_03    │    └──────────┘                 │
        │   └─────┬─────┘    └──────────┘                                 │
        │         │                                                       │
        │         ├──── PayerAnalytics (Direct Lake, 35 tables) ──┐       │
        │         └──── Payer_Ontology (26 entities, 32 rels) ────┤       │
        │                                                         ▼       │
        │   7 Foundry DataAgents (CFO/Stars/RA/SIU/CareMgmt/Network/UM)   │
        │     each binds: lakehouse_tables + semantic_model + graph       │
        └─────────────────────────────────────────────────────────────────┘
                        ▲
                        │ function-tool calls (ask_um_agent / ask_risk_agent)
                        │
        ┌─────────────────────────────────────────────────────────────────┐
        │     PAReviewCopilot.HostedAgent  (Foundry hosted, PREVIEW)      │
        │     gpt-4.1-mini · Responses API · project_msi · structured     │
        │     output envelope · 4 tools · 3 KB sources                    │
        └─────────────────────────────────────────────────────────────────┘
```

## Layer-by-layer

### 1. Lakehouse medallion (4 lakehouses)

| Lakehouse           | Role                                                  |
|---------------------|-------------------------------------------------------|
| `lh_bronze_raw`     | Synthetic CSVs at `Files/synth/<run_id>/`, raw load   |
| `lh_silver_stage`   | Typed Delta, NDJSON-cleansed                          |
| `lh_silver_ods`     | Conformed ODS layer (member/provider/claim grain)     |
| `lh_gold_curated`   | Star-schema gold (10 dims + 16 facts + 9 aggs)        |

Driven by `NB_01_Bronze_Ingest` (21 bronze tables from
`tools.run_local_etl.BRONZE_TABLES`), `NB_02_Silver_Transform`,
`NB_03_Gold_Build`. Locked by `tests/test_notebook_shape.py`.

### 2. Semantic model — `PayerAnalytics` (Direct Lake)

- 35 tables = 10 dim + 16 fact + 9 agg (mirrors gold).
- 32 active relationships, 15 DAX measures.
- One `DirectLake - lh_gold_curated` M expression — no Import / DirectQuery.
- TMDL under `workspace/PayerAnalytics.SemanticModel/definition/`.
- Locked by `tests/test_semantic_model_shape.py`.

### 3. Graph — `Payer_Ontology`

- Single Fabric Ontology derived from PayerAnalytics SM.
- 26 EntityTypes (dims + facts; `agg_*` excluded — pre-aggregated, not entity-like).
- 32 RelationshipTypes (all `ManyToOne`).
- TMDL types → ontology types: `int64`→`BigInt`, `string`→`String`,
  `dateTime`→`DateTime`, `double`→`Double`.
- Locked by `tests/test_ontology_shape.py`.

### 4. Foundry DataAgents (7, Fabric-bound)

| Agent                 | Persona                            | Datasource binding             |
|-----------------------|------------------------------------|--------------------------------|
| `CFOAgent`            | Finance / revenue cycle            | gold + PayerAnalytics + graph  |
| `StarsAgent`          | Stars / quality                    | gold + PayerAnalytics + graph  |
| `RiskAdjustmentAgent` | Risk Adjustment / HCC              | gold + PayerAnalytics + graph  |
| `SIUAgent`            | SIU / FWA                          | gold + PayerAnalytics + graph  |
| `CareMgmtAgent`       | Care Mgmt / pop health             | gold + PayerAnalytics + graph  |
| `NetworkAgent`        | Network & contracting              | gold + PayerAnalytics + graph  |
| `UMAgent`             | UM / prior authorization           | gold + PayerAnalytics + graph  |

Each agent uses 3 of the 5 Fabric-allowed datasources per agent
(`lakehouse_tables`, `semantic_model`, `graph`). Shape conforms to Fabric Git
Integration v2 / DataAgent 2.1.0.

### 5. Hosted Foundry agent — `PAReviewCopilot.HostedAgent` (PREVIEW)

- Microsoft Agent Framework 1.9.0, Foundry Agent Service GA (Responses API).
- 4 tools: `get_pa_packet`, `lookup_policy_citation` (Python stubs in
  `tools/foundry_tools/`); `ask_um_agent`, `ask_risk_agent` (function-tool
  delegation to upstream Fabric DataAgents — no Python stub).
- 3 KB sources: `cms_0057_f_pa_rule.md`, `ama_prior_auth_survey.md`,
  `policy_citation_pattern.md`.
- Structured-output envelope locked by `output_schema.json` (4-value
  recommendation enum).
- Deploys via `python tools/deploy_data_agents.py --live --foundry-project
  <endpoint>` — NOT a fabric-cicd item type.

## Two install paths

### Path A — Platform team / CI (fabric-cicd)

```
git push → CI runs ruff + pytest + dry-run → tools/deploy.py --env dev
                                                            --env staging
                                                            --env prod --confirm
```

`tools/deploy.py` wraps fabric-cicd 1.1.0. Publishes the 19 items under
`workspace/` in topological order (Lakehouse → Notebook → DataPipeline →
SemanticModel → Ontology → DataAgent). Parameterizes workspace ids via
`workspace/parameter.yml` + per-env `FABRIC_WORKSPACE_ID_<ENV>`.

### Path B — Analyst / Jumpstart (in-workspace launcher)

```
Open Healthcare_Launcher → Run All
  ├─ Cell 1: pull payer_knowledge/*.md from raw → lh_gold_curated Files/
  ├─ Cell 2: NB_01 → NB_02 → NB_03 medallion chain
  ├─ Cell 3: rebind 7 DataAgent zero-GUID placeholders to live ids
  └─ Cell 4: 8-table gold sanity + publish-state summary
```

No laptop CLI. No `git clone`. No `pip install`. Toggles per step so the
analyst can iterate on any one without re-running the others.

## Zero-GUID placeholder convention

DataAgent definitions under `workspace/<Name>.DataAgent/Files/Config/{draft,
published}/<datasource>/datasource.json` are committed with:

```json
{
  "artifactId":  "00000000-0000-0000-0000-000000000000",
  "workspaceId": "00000000-0000-0000-0000-000000000000"
}
```

This keeps the repo **workspace-portable** — the same commit deploys
unchanged into any workspace. Two rebind paths:

- **Platform-team path**: `fabric-cicd` reads `workspace/parameter.yml` and
  substitutes at publish time.
- **Analyst path**: `Healthcare_Launcher` Cell 3 discovers live ids and
  POSTs `updateDefinition` per agent at Run All.

## What's intentionally not in v1

See [README.md "What's intentionally not in v1"](../README.md#whats-intentionally-not-in-v1)
and `docs/_internal/adopt_list.md` Tier-4 for the full exclusion list.

## Drift gates

Every commit must pass:

| Gate                                 | Locks                                            |
|--------------------------------------|--------------------------------------------------|
| `pytest`                             | 81 tests across 12 test modules                  |
| `ruff check .`                       | Python style (excludes `workspace/**/notebook-content.py`) |
| `python tools/check_citations.py`    | Every `[CIT:<id>]` reference resolves            |
| `python tools/audit_data.py`         | 22 RI edges on smoke run                         |
| `python tools/data_fidelity.py`      | 15 distribution / cardinality checks             |
| `python tools/deploy.py --env dev --dry-run` | 19 items resolve in topological order    |

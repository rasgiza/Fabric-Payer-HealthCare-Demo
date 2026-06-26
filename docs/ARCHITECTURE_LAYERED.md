# Architecture — Layered dependency view

This is the dependency view, not the topology view. For the topology
diagram see [ARCHITECTURE.md](ARCHITECTURE.md).

The repo's artifacts form a strict downward-only dependency stack:
**Lakehouse → Ontology → Semantic Model → Data Agent → Hosted Agent**.
Phase 0 also adds two cross-cutting columns (DQ contracts + Audit logs)
that read from every layer. Phase 3 introduces the Foundry IQ / Fabric
IQ split at the hosted-agent layer.

```
                 ┌────────────────────────────────────────────────────────┐
                 │  Hosted agents  (Foundry, project-MSI auth)            │
                 │                                                        │
                 │   PAReviewCopilot              PayerRT_Copilot         │
                 │   (UM Reviewer)                (RTI Ops Orchestrator)  │
                 │       │                              │                 │
                 │       │ grounding:                   │ grounding:      │
                 │       ▼ Foundry IQ                   ▼ Fabric IQ       │
                 │   payer_knowledge/*.md          (3 connection IDs)     │
                 └───────┬──────────────────────────────┬─────────────────┘
                         │                              │
                         │ function-tool calls          │
                         ▼                              ▼
                 ┌────────────────────────────────────────────────────────┐
                 │  Fabric DataAgents (max_items=1 per binding)           │
                 │                                                        │
                 │  CFO  Stars  RA  SIU  CareMgmt  Network  UM            │
                 └───────┬──────────────────────────────┬─────────────────┘
                         │                              │
                         │ DAX                          │ GQL
                         ▼                              ▼
        ┌────────────────────────────┐   ┌──────────────────────────────┐
        │  PayerAnalytics SM         │   │  Payer_Ontology graph        │
        │  (Direct Lake, 35 tables)  │   │  (26 entities, 32 rels)      │
        └──────────────┬─────────────┘   └──────────────┬───────────────┘
                       │                                │
                       │  Delta tables (lh_gold_curated)│
                       ▼                                ▼
        ┌──────────────────────────────────────────────────────────────┐
        │  lh_gold_curated (10 dim + 16 fact + 9 agg)                  │
        └──────────────────────────────────────────────────────────────┘
                       ▲
                       │  NB_03_Gold_Build
        ┌──────────────────────────────────────────────────────────────┐
        │  lh_silver_stage  + lh_silver_ods                            │
        └──────────────────────────────────────────────────────────────┘
                       ▲
                       │  NB_02_Silver_Transform
        ┌──────────────────────────────────────────────────────────────┐
        │  lh_bronze_raw                                               │
        └──────────────────────────────────────────────────────────────┘
                       ▲
                       │  NB_01_Bronze_Ingest  (21 BRONZE_TABLES)
        ┌──────────────────────────────────────────────────────────────┐
        │  Source: synthetic generator (tools/gen_payer_overlay.py)    │
        └──────────────────────────────────────────────────────────────┘
```

Cross-cutting columns (read from every layer, never block the pipeline):
- **DQ contracts**: `tools/dq_checks.py` validates each layer against
  `BRONZE_CONTRACTS` / `SILVER_CONTRACTS` / `GOLD_CONTRACTS`.
- **Audit logs**: `tools/audit_log.py` (one row per medallion stage) +
  `tools/agent_audit.py` (one row per agent invocation).

---

## Why Foundry IQ vs Fabric IQ are kept separate

A naive demo binds one agent to everything. This causes two failure modes:

1. **Citation drift**: the agent cites a Power BI measure when the
   question requires a policy citation, or vice versa. Reviewers cannot
   verify either.
2. **Auth blast radius**: a single Foundry agent with both an
   unstructured KB and a SM connection has the union of both permission
   sets. A bug in one tool can leak data from the other.

The split below is mechanical (different connection types in the
Foundry project), so a developer cannot accidentally cross the streams.

### Foundry IQ surface — `PAReviewCopilot`

- **Grounding**: 15 markdown files in [payer_knowledge/](../payer_knowledge/)
  (CMS-0057-F, AMA PA survey, CMS Stars cut-points, HCC V28, HEDIS MY2026,
  NHCAA fraud schemes, OIG RADV guidance, etc.).
- **Connection type**: knowledge-source (vector store under the Foundry
  project).
- **Output**: `output_schema.json` with a locked `recommendation` enum
  (`approve` / `pend_for_p2p` / `deny_for_criteria_not_met` / `refuse`).
- **Function tools**: `get_pa_packet`, `lookup_policy_citation`,
  `ask_um_agent` (delegates to UMAgent DataAgent), `ask_risk_agent`
  (delegates to RiskAdjustmentAgent DataAgent).
- **Owner pain point**: PP-UM-004 (per-case reviewer time + audit-grade
  citations).

### Fabric IQ surface — `PayerRT_Copilot`

- **Grounding**: 3 distinct Foundry connection IDs, one per source kind.
  - `conn-ontology`: `Payer_Ontology` graph (via Fabric).
  - `conn-data-agent`: a tool-routing front-end to the 7 Fabric DataAgents.
  - `conn-semantic-model`: `PayerAnalytics` SM (DAX surface for measure
    questions).
- **Connection type**: `FabricIQPreviewTool` (`azure-ai-projects>=2.2.0`).
- **Output**: routing recommendation + a live worklist envelope.
- **Function tools**: `get_pa_latency_window`, `get_emergency_admit_worklist`,
  `get_siu_suspect_claims` (KQL queries against `kqldb_payer_rt`), plus
  `ask_um_agent` / `ask_care_mgmt_agent` / `ask_siu_agent` delegations.
- **Owner pain point**: PP-RTI-001 (latency from event to operator action).

See [FOUNDRY_CONNECTION_SETUP.md](FOUNDRY_CONNECTION_SETUP.md) for the
exact 3-connection setup.

---

## Lane separation (RTI rule)

| | Batch lane | Real-time lane |
|---|---|---|
| Refresh cadence | hourly / daily / weekly | seconds |
| Storage | Delta (`lh_gold_curated`) | Eventhouse / KQL DB (`kqldb_payer_rt`) |
| Query language | DAX (SM) + SQL (lakehouse) + GQL (ontology) | KQL |
| Agent layer | 7 Fabric DataAgents | `PayerRT_Copilot` |
| Allowed binding | SM, lakehouse, graph | KQL DB only |

`tools/deploy_data_agents.py` rejects any bind that crosses these lanes
at deploy time.

---

## What changes when a customer adds a new entity

Adding `MeasureMLR` (Phase 2 example) requires touching exactly:

1. `ontology/payer_ontology.yaml` — new `entity` + `relationships`.
2. `workspace/Payer_Ontology.Ontology/` — sync JSON to the YAML.
3. `tools/audit_rels.py` — confirms 0 violations.
4. `tools/dq_checks.py` — add `MEASURE_MLR_CONTRACT` if a new table backs it.
5. The owning DataAgent's `binding.yaml` (CFOAgent) — add the table.
6. `tests/test_fidelity_returns_expected_check_set` — pin name if a new
   fidelity check was added.

No agent prompt edits, no NB schema bumps, no CI changes. The audit log
captures the new entity's writes automatically.

---

## What changes when a customer adds a new persona agent

Adding `PharmacyAgent` (a hypothetical 8th DataAgent) requires:

1. New folder `data_agents/PharmacyAgent.DataAgent/` with:
   - `binding.yaml` (lakehouse + SM tables for pharmacy)
   - `aiInstructions.md` (persona + scope)
   - `tool_schemas.json`
   - `output_schema.json` (locks recommendation enum)
   - `eval/cases.jsonl` (≥10 cases)
2. `tools/deploy_data_agents.py` discovers it on next run.
3. `tools/run_evals.py` discovers it on next run.
4. `tests/test_eval_thresholds.py` parametrizes over all agents automatically.

No new tooling. The repo's per-agent fan-out is the contract.

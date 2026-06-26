# Differentiation — What this demo proves that a generic Fabric demo does not

This repo is positioned against three reference points:
1. A blank Fabric workspace + a 1-page sample notebook.
2. A Databricks Lakehouse on healthcare claims with MLflow / Genie.
3. A point-tool demo (Power BI only, or Foundry only, or RTI only).

Six pillars below are what set this project apart. Each pillar names the
concrete artifact in the repo that proves it.

---

## Pillar 1 — Opinionated payer ontology, not a "generic claims" model

| Artifact | Proof |
|---|---|
| [ontology/payer_ontology.yaml](../ontology/payer_ontology.yaml) | 26 entities + 32 typed relationships, payer-shaped (HCC, HEDIS, CARC, NSA, OON, RAF, MLR, PA, SIU) |
| [tools/audit_rels.py](../tools/audit_rels.py) | Validates every relationship round-trips against the published TMDL + lakehouse schema |
| [tools/build_graph.py](../tools/build_graph.py) | Builds the executable graph on `lh_gold_curated` for the OntologyAgent |

A generic claims model carries `claim`, `member`, `provider` and nothing
else. This ontology carries `Hcc`, `HedisMeasure`, `StarsCutpoint`,
`Carc`, `AppealCase`, `PriorAuth`, `RafScore`, `MlrSegment`,
`NsaQualifyingClaim`, `SiuAlert`, `RtiAlertEnvelope` — the entities a
payer's CFO, Stars Director, RA VP, SIU Director, and CMO actually
reason about.

## Pillar 2 — Foundry IQ + Fabric IQ split (not "use one model for everything")

Most demos pick one grounding source. This one separates them deliberately:

| Surface | Grounded against | Agent |
|---|---|---|
| **Foundry IQ** (unstructured) | [payer_knowledge/*.md](../payer_knowledge/) — 15 policy and methodology docs (CMS-0057-F, NHCAA fraud schemes, CMS Stars cut-points, HCC V28, etc.) | [PAReviewCopilot](../data_agents/PAReviewCopilot.HostedAgent/) — per-case PA reviewer |
| **Fabric IQ** (structured, 3 connection IDs) | (a) `Payer_Ontology` graph, (b) 7 Fabric DataAgents, (c) `PayerAnalytics` semantic model | [PayerRT_Copilot](../data_agents/PayerRT_Copilot.HostedAgent/) — real-time ops orchestrator |

The split keeps citations honest. A PA review must cite a numbered
policy section, not an aggregate. An ops workqueue must cite a row in
a Delta table, not a paragraph. The architecture enforces that by
binding each tool to a different grounding source.

See [docs/ARCHITECTURE_LAYERED.md](ARCHITECTURE_LAYERED.md) for the
end-to-end dependency view and [docs/FOUNDRY_CONNECTION_SETUP.md](FOUNDRY_CONNECTION_SETUP.md)
for the 3-connection Fabric IQ setup.

## Pillar 3 — Deploy-ready DQ contracts + audit logs (not "happy path only")

| Artifact | Proof |
|---|---|
| [tools/dq_checks.py](../tools/dq_checks.py) | Per-layer column contracts (dtype, nullable, unique, min/max, enum, regex, composite unique_keys); 315 contract assertions on smoke |
| [tools/audit_log.py](../tools/audit_log.py) | Dual-mode (local parquet / Spark Delta) audit log; every NB emits 1 row per layer with run_id, rowcount, duration_ms, git_sha, user_principal |
| [tools/agent_audit.py](../tools/agent_audit.py) | Per-call agent log: prompt_sha256, response_sha256, prompt_tokens, response_tokens, tools_called, status |
| [.github/workflows/ci.yml](../.github/workflows/ci.yml) | `dq_checks` and `audit_log show` run in CI on every push to `main` |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Schema-contract invariants list keeps NB schemas in lockstep with module schemas |

A customer can fork this repo and ship to production without writing
their own DQ harness, audit pipeline, or PR gates.

## Pillar 4 — Per-LOB persona agents, not one "do everything" agent

Seven Fabric data agents and two Foundry hosted agents — each scoped
to a single persona's question surface:

| Agent | Persona | Scope |
|---|---|---|
| [CFOAgent](../data_agents/CFOAgent.DataAgent/) | CFO / RCM | denials, AR days, MLR, PMPM, rebate liability |
| [StarsAgent](../data_agents/StarsAgent.DataAgent/) | Stars Director | cut-points, HEI, PDC, CAHPS, HEDIS gaps |
| [RiskAdjustmentAgent](../data_agents/RiskAdjustmentAgent.DataAgent/) | RA VP | HCC suspects, RADV exposure, RAF, V28 deltas |
| [SIUAgent](../data_agents/SIUAgent.DataAgent/) | SIU Director | upcoding clusters, referral concentration, fraud schemes |
| [CareMgmtAgent](../data_agents/CareMgmtAgent.DataAgent/) | CMO / CareMgmt | high-cost cohorts, SDOH, readmission risk |
| [NetworkAgent](../data_agents/NetworkAgent.DataAgent/) | Network / Contracting | adequacy, OON spend, IDR, NSA |
| [UMAgent](../data_agents/UMAgent.DataAgent/) | UM | TAT, SLA breach, peer-to-peer |
| [PAReviewCopilot](../data_agents/PAReviewCopilot.HostedAgent/) | UM Reviewer | per-case PA recommendation |
| [PayerRT_Copilot](../data_agents/PayerRT_Copilot.HostedAgent/) | RTI Ops | live worklist routing across UM / CareMgmt / SIU |

Each agent has its own locked `output_schema.json`, persona
`aiInstructions.md`, and `eval/cases.jsonl` — so a regression in one
agent does not silently corrupt the others.

## Pillar 5 — RTI lane separation rule

> "Answer does not change in ≥1 h → semantic model / data agent.
> Answer changes in seconds-minutes → KQL DB / RTI dashboard."

| Lane | Surface | Latency |
|---|---|---|
| Batch | `lh_gold_curated` → `PayerAnalytics` SM → 7 DataAgents | hours |
| Real-time | Eventstream → `kqldb_payer_rt` → 4 KQL scoring NBs → `PayerRT_Copilot` | seconds |

The rule is enforced by binding: DataAgents cannot bind to a KQL DB,
and the RTI copilot cannot bind to the semantic model. Customers who
break the rule by accident get a deploy-time error from
`tools/deploy_data_agents.py`.

## Pillar 6 — End-to-end eval harness with locked output schemas

| Artifact | Proof |
|---|---|
| [tools/run_evals.py](../tools/run_evals.py) | Offline scorer compares each `cases.jsonl` to the agent's `output_schema.json` enum + declared tool_schemas |
| [tests/test_eval_thresholds.py](../tests/test_eval_thresholds.py) | groundedness ≥4, tool_call_accuracy ≥1, refusal recognition |
| [tools/eval_agents_offline.py](../tools/eval_agents_offline.py) | Offline scoring without a live Foundry project (CI-friendly) |
| `output_schema.json` per agent | Locks the recommendation enum so case-file drift is caught at PR time |

Customers who change an agent's prompt cannot ship without updating
its `cases.jsonl` and seeing the offline eval still pass — that
contract holds in CI without requiring a paid Foundry tenant.

---

## Databricks parity matrix

| Capability | Databricks Lakehouse | This Fabric demo |
|---|---|---|
| Medallion ETL | Delta Lake + workflows | Delta Lake + Fabric pipelines + 3 medallion NBs |
| Star schema | dbt + Unity Catalog | TMDL semantic model + `tools/build_semantic_model.py` |
| Streaming | Structured Streaming → Delta | Eventstream → KQL DB + scoring NBs |
| Vector / RAG | Vector Search index | Foundry IQ knowledge sources + `payer_knowledge/` |
| Agentic | Genie / MLflow / Agent Framework | Foundry hosted agents + Fabric DataAgents (max_items=1 per tool) |
| Graph / ontology | (custom build) | First-class `Payer_Ontology` (26 entities, 32 rels) + audit tool |
| DQ contracts | Great Expectations / Deequ (custom) | `tools/dq_checks.py` (315 assertions, CI gated) |
| Audit / lineage | Unity Catalog system tables | `lh_gold_curated.audit_log` + `agent_calls` (Phase 0b + 0c) |
| Eval harness | MLflow Evaluations | `tools/run_evals.py` + locked output_schema.json |
| Per-persona agents | (custom build) | 9 scoped agents (7 DataAgents + 2 hosted) |
| Lane separation | (manual) | Enforced at bind-time |
| PR gates | (customer-owned) | `.github/workflows/ci.yml` ships green |

The strategic pitch is **time-to-payer-demo**, not "Fabric is better than
Databricks". A Databricks-shop customer can keep their lake and adopt
just the Foundry IQ + Fabric IQ layer; a Fabric-shop customer gets the
whole stack out of the box.

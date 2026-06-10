# Adopt List — capabilities this demo will actively use

Distilled from [api_delta_2026-06.md](api_delta_2026-06.md). Each row maps a capability to the phase + file/notebook that consumes it, so we can spot gaps before authoring.

## Tier 1 — must use (gate-blocking)

| Capability | Phase | Consumed by |
|---|---|---|
| Per-agent `aiInstructions.md` published from repo | 0c | `data_agents/<persona>/aiInstructions.md` × 7 |
| `MCPTool(require_approval="never")` | 5 | `data_agents/_orchestrator/create_subagents.py` |
| Project-scoped MSI for Foundry connections (per-agent Entra identity for Hosted agents) | 5, 5.5, 7 | `infra/foundry-rbac.bicep` |
| `evaluatorThresholds` integers ≥1; ≤4 rows per batch | 0d, every phase gate | `tools/run_eval.py` |
| TMDL semantic model | 4 | `report/PayerAnalytics.SemanticModel/` |
| One Foundry agent ↔ one Fabric data agent (maxItems=1) | 5 | `data_agents/<persona>/binding.yaml` × 7 |
| Few-shots (`fewshots.jsonl`) per agent + value-set descriptions | 0c, 4 | `data_agents/<persona>/fewshots.jsonl` × 7 |
| **Fabric Data Agent GA** — acknowledge GA status in README + Phase 7 launcher | 5, 7 | `README.md`, `tools/deploy_data_agents.py` |
| **25-row / 25-col cap** in agent prompts and eval cases | 5, 5.5 | `data_agents/*/eval/cases.jsonl`, `tools/eval_agents_offline.py` |
| **Hosted-agent preview disclosure** in customer-facing docs (`PAReviewCopilot.HostedAgent`) | 5.5 | `README.md`, `docs/MICROSOFT_USE_CASE_COVERAGE.md` |

## Tier 2 — strongly preferred (not gate-blocking but lifts quality)

| Capability | Phase | Consumed by |
|---|---|---|
| `sempy_labs` for SM descriptions + BPA cleanup | 4 | `tools/apply_sm_descriptions.py`, `tools/apply_bpa_cleanup.py` |
| `semantic-link / sempy` for DAX validation | 4 | `notebooks/04_validate_model.ipynb` |
| Foundry built-in tools (`file_search`, `web_search`, `code_interpreter`) on `PAReviewCopilot.HostedAgent` | 5.5 | `data_agents/PAReviewCopilot.HostedAgent/agent.yaml` |
| Built-in evaluators (groundedness, relevance, tool_call_accuracy, content_safety, indirect_attack) | 0d, every phase gate | `tools/run_eval.py` |
| `fabric-cicd` **1.1.0** for deploy of supported item types | 7 | `infra/deploy.py` |
| `fabric-launcher` reconcile pattern (lifted from `nypproject`) | 7 | `infra/launcher/` |
| **Fabric Data Agent ALM via Git + deployment pipelines** | 7 | `infra/launcher/` |
| **Foundry tracing + App Insights** end-to-end on Hosted agent | 7 | `infra/foundry-observability.bicep` |
| **Custom MCP server on Azure Functions** (`/runtime/webhooks/mcp`) for `lookup_policy_citation` | 5.5 / v1.1 | `functions/policy-citation-mcp/` (v1.1) |
| **Variable Library** for cross-item parameterization (lakehouse-id, capacity-id) | 7 | `infra/launcher/variables.yaml` (if accelerator path) |

## Tier 3 — adopt opportunistically (verify scope first)

| Capability | Phase | Consumed by | Decision needed |
|---|---|---|---|
| Eventhouse / KQL DB for SIU + RTI | 6 | `data_agents/04-siu/realtime/`, `infra/eventhouse/` | confirmed: real-time **and** batch via OneLake mirror |
| Activator + Power Automate alert chain | 6 | `infra/activator/` | re-fetch correct docs URL (404 on 2026-06-10) |
| **Fabric Graph database** for ontology publish | 7 | `notebooks/03_ontology.ipynb` graph publish step | re-fetch correct docs URL (404 on 2026-06-10); decide gpickle vs Fabric Graph |
| OneLake Mirrored DB | 1 / v1.1 | `notebooks/01_bronze.ipynb` | mirror or batch ingest? |
| PBIR (report-as-folder) **— still preview** | 4 | `report/PayerAnalytics.Report/` | with preview disclosure in README; ship PBIX fallback |
| GraphQL Model API | v1.1 | optional persona alt-tool | only if narrative needs polyglot demo |
| **Foundry Toolbox** (preview) for curated MCP-compatible tool surface | v1.1 | `infra/foundry-toolbox/` | swap per-agent tool wiring after Toolbox GA |
| **Foundry A2A protocol** (preview) for orchestrator ↔ hosted agent | v2.0 | `mission_control/orchestrator.py` | A2A vs current MCP-tool path |
| **Foundry Entra Agent Registry** for share-with-org | v1.1 | `infra/agent-registry/` | only if customer plans M365 distribution |
| **Foundry Hosted-agent BYO-VNet + dedicated Entra identity** | v2.0 | `infra/foundry-vnet.bicep` | required for HIPAA-grade prod posture |
| **Microsoft Graph data source on Fabric Data Agent** | v1.1 | `data_agents/CareMgmtAgent.DataAgent/` (M365 task signals) | only if WorkIQ pattern is also adopted |
| **Fabric IQ / WorkIQ / SharePoint** as platform tools on `PAReviewCopilot.HostedAgent` | 5.5 / v1.1 | `data_agents/PAReviewCopilot.HostedAgent/agent.yaml` | wire after Phase 5.5 customer-pilot feedback |
| **Foundry Agent Optimizer** for auto-tuning instructions | v1.1 | `tools/optimize_agents.py` | only after we have eval traces from a real run |
| **Purview DLP + access-restriction policies** on data-agent backing stores | 7 | `infra/purview/` | confirm preview vs GA per data-source type |

## Tier 4 — explicitly not used in v1

- LangChain / Semantic Kernel orchestration layers (we use Foundry SDK directly; **Microsoft Agent Framework** at `github.com/microsoft/agent-framework` is the canonical Microsoft framework if we ever lift orchestration into a Hosted agent)
- AutoGen multi-agent framework (we use Foundry agent + MCPTool composition)
- Custom embedding pipelines (Foundry built-in `file_search` handles indexing)
- PBIX binary format (TMDL + PBIR/PBIP only)
- Account-scoped MSI on connections

## Net-new vs reused-from-nypproject

**Reused patterns** (lift, don't reinvent):
- `fabric-launcher` reconcile loop
- `apply_sm_descriptions.py` + `apply_bpa_cleanup.py` BPA flow
- `verify_demo_ready.py` smoke harness
- Foundry MCPTool gotchas (in repo memory)

**Net-new in this repo**:
- 7-persona payer ontology + persona-cards
- citations.yaml + check_citations.py linter (this is the new mechanism)
- Synthea + payer overlay (new data foundation)
- Hero stories Maria Chen + Devon Williams (Phase 0b output)
- Per-agent `aiInstructions.md` authored from industry artifacts (Phase 0c)
- Coverage matrix linking pain points → questions → tables → measures → agents

## Gate criteria recap

For each capability in Tier 1, the phase gate test is:
1. The consuming file exists and is committed.
2. The capability is actually invoked (no dead-stub adoption).
3. Where applicable, an evaluator run validates the integration end-to-end.

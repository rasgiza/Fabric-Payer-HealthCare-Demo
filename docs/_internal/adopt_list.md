# Adopt List — capabilities this demo will actively use

Distilled from [api_delta_2026-06.md](api_delta_2026-06.md). Each row maps a capability to the phase + file/notebook that consumes it, so we can spot gaps before authoring.

## Tier 1 — must use (gate-blocking)

| Capability | Phase | Consumed by |
|---|---|---|
| Per-agent `aiInstructions.md` published from repo | 0c | `data_agents/<persona>/aiInstructions.md` × 7 |
| `MCPTool(require_approval="never")` | 5 | `data_agents/_orchestrator/create_subagents.py` |
| Project-scoped MSI for Foundry connections | 5, 7 | `infra/foundry-rbac.bicep` |
| `evaluatorThresholds` integers ≥1; ≤4 rows per batch | 0d, every phase gate | `tools/run_eval.py` |
| TMDL semantic model | 4 | `report/PayerAnalytics.SemanticModel/` |
| One Foundry agent ↔ one Fabric data agent (maxItems=1) | 5 | `data_agents/<persona>/binding.yaml` × 7 |
| Few-shots (`fewshots.jsonl`) per agent + value-set descriptions | 0c, 4 | `data_agents/<persona>/fewshots.jsonl` × 7 |

## Tier 2 — strongly preferred (not gate-blocking but lifts quality)

| Capability | Phase | Consumed by |
|---|---|---|
| `sempy_labs` for SM descriptions + BPA cleanup | 4 | `tools/apply_sm_descriptions.py`, `tools/apply_bpa_cleanup.py` |
| `semantic-link / sempy` for DAX validation | 4 | `notebooks/04_validate_model.ipynb` |
| Foundry Knowledge Agent with `knowledgeSources` (RAG over policy corpus) | 5 | `data_agents/_knowledge/policy_corpus_index/` |
| Built-in evaluators (groundedness, relevance, tool_call_accuracy, content_safety, indirect_attack) | 0d, every phase gate | `tools/run_eval.py` |
| `fabric-cicd` for deploy of supported item types | 7 | `infra/deploy.py` |
| `fabric-launcher` reconcile pattern (lifted from `nypproject`) | 7 | `infra/launcher/` |

## Tier 3 — adopt opportunistically (verify scope first)

| Capability | Phase | Consumed by | Decision needed |
|---|---|---|---|
| Eventhouse / KQL DB for SIU streaming | 3 | `data_agents/04-siu/realtime/` | real-time or batch? |
| Activator + Power Automate alert chain | 6 | `infra/activator/` | needed for SIU hero moment? |
| OneLake Mirrored DB | 1 | `notebooks/01_bronze.ipynb` | mirror or batch ingest? |
| PBIR (report-as-folder) | 4 | `report/PayerAnalytics.Report/` | GA or use PBIP fallback? |
| GraphQL Model API | 5 | optional persona alt-tool | only if narrative needs polyglot demo |

## Tier 4 — explicitly not used in v1

- LangChain / Semantic Kernel orchestration layers (we use Foundry SDK directly)
- AutoGen multi-agent framework (we use Foundry agent + MCPTool composition)
- Custom embedding pipelines (Knowledge Agent handles indexing)
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

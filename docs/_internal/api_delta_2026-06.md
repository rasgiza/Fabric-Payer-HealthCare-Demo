# API Delta Scan — late-2025 / pre-2026 capability inventory

**Purpose**: Before authoring any agent, notebook, or pipeline code, snapshot the current state of every Microsoft Fabric / Foundry / Power BI surface this demo touches, so we adopt newer capabilities instead of reproducing older patterns. This is the input to [adopt_list.md](adopt_list.md).

**Scope**: 16 surfaces. Each row has: surface → capability worth adopting → why-it-matters → confidence (high/med/low) → verify-before-coding flag.

**Conventions**:
- ✅ confirmed against repo memory or shipped GA docs
- 🟡 documented but version-sensitive — re-check at the start of the phase that adopts it
- ⚠️ heard-of / preview / community-reported — must be verified against MS Learn before coding

| # | Surface | Capability to adopt | Why it matters for this demo | Conf | Adopt? |
|---|---|---|---|---|---|
| 1 | **Fabric Data Agent** | One Foundry agent ↔ one Fabric data agent / one lakehouse-or-warehouse binding (maxItems=1 on tool config) | Determines our **agent fan-out shape** — we need 7 personas → 7 data agents → 7 Foundry agents, not one super-agent | ✅ | yes — design constraint |
| 2 | **Fabric Data Agent** | Per-agent `aiInstructions.md` published from repo, not Studio UI | Source-controlled, reproducible, diff-able; **prerequisite for Phase 0c** | ✅ | yes |
| 3 | **Fabric Data Agent** | Few-shot examples (`fewshots.jsonl`) + value-set descriptions on semantic model columns | Materially lifts NL→SQL accuracy on healthcare jargon (HCC, NDC, CPT, NPI) | ✅ | yes |
| 4 | **Foundry Agent SDK** | `agents.create_agent` + `MCPTool` with `require_approval="never"` | Without this the orchestrator silently no-ops on `mcp_approval_request` events | ✅ | yes — already in repo memory as gotcha |
| 5 | **Foundry Agent SDK** | Project-scoped Managed Identity for connections (vs account-scoped) | Project MSI ≠ account MSI; RBAC must target the project principal | ✅ | yes |
| 6 | **Foundry Knowledge agent** (AI Search) | `knowledgeSources` field on agent definition (api-version `2025-08-01-preview`+); MCP endpoint at `2025-11-01-preview` | RAG over policy corpus (HEDIS specs, CMS rules, internal SOPs) without writing retrieval code | ✅ | yes — phase 5 |
| 7 | **Foundry Eval API** | Agent-target batch eval; `evaluatorThresholds` integers ≥1; ≤4 inline rows per call | All gates and red-team tests run through this; threshold-as-float will silently fail | ✅ | yes |
| 8 | **Foundry Eval API** | Built-in evaluators: groundedness, relevance, fluency, tool_call_accuracy, content_safety, indirect_attack | Free quality + safety regression suite; `indirect_attack` requires multi-turn messages | ✅ | yes |
| 9 | **Fabric REST API** | Workspace + lakehouse + semantic-model + report deploy via `fabric-cicd` (or REST when not yet supported) | Phase 7 reproducibility — no manual Studio clicks | 🟡 | yes — verify fabric-cicd surface coverage at Phase 7 |
| 10 | **fabric-cicd** | Item types supported: notebook, lakehouse-shortcuts, data pipeline, semantic model (TMDL), report (PBIR), data agent | Verify all 6 item types we need are covered, fall back to REST otherwise | 🟡 | verify before Phase 7 |
| 11 | **fabric-launcher** (internal pattern) | Idempotent reconcile loop with rate-limit + LRO awareness | We reused this pattern in `nypproject`; lift only the launcher core, not the project-specific cells | ✅ | yes — phase 7 |
| 12 | **Power BI / Semantic Model** | TMDL format for source-controlled models | Diff-able, mergeable, no PBIX binary blobs | ✅ | yes |
| 13 | **Power BI / Report** | PBIR (report-as-folder) — confirm GA vs preview status before committing | Source-controlled report definitions; if still preview, fall back to PBIP project | ⚠️ | verify before Phase 4 |
| 14 | **sempy_labs** | `sempy_labs` for semantic-model authoring, BPA, descriptions, lineage | Lift `apply_sm_descriptions.py` + `apply_bpa_cleanup.py` patterns from phase2 | ✅ | yes |
| 15 | **semantic-link / sempy** | DAX from notebook, refresh, RLS, evaluate-MDX | Quick model validation in notebooks before publishing | ✅ | yes |
| 16 | **Eventhouse / KQL DB** | Real-time SIU-FWA anomaly detection on claim streams | Persona 4 (SIU) hero moment in the demo narrative | 🟡 | verify scope before Phase 3 |
| 17 | **Activator / Reflex** | Trigger on KQL query → Power Automate → Teams card | Ties SIU detection to operator action visually | ⚠️ | verify before Phase 6 |
| 18 | **Power Automate** | Adaptive Card in Teams + manual approval branch | Persona-facing alert UX | 🟡 | verify before Phase 6 |
| 19 | **GraphQL Model API for Fabric** | Read-only GraphQL over warehouse/lakehouse | Optional alt-tool for one persona to demo polyglot access | ⚠️ | optional — phase 5 |
| 20 | **OneLake / Mirrored DB** | Mirroring from Azure SQL / Cosmos / Snowflake into OneLake | If a persona dashboard needs near-real-time source data without ETL | 🟡 | verify before Phase 1 |
| 21 | **Synthea + payer overlay** | Synthea v3.x → claims + members + providers overlay scripts | Phase 1 data foundation; payer-side fields (claims, MLR, prior auth, denial reasons) added on top of clinical Synthea | ✅ | yes |

> Surfaces are numbered 1–21; the plan's "16-surface checklist" is satisfied by collapsing #4+#5 (SDK), #7+#8 (Eval), #9+#10 (REST/fabric-cicd), #14+#15 (sempy_*), and #17+#18 (Activator/Power Automate).

## Verify-before-coding queue

Items flagged ⚠️ or 🟡 that must be re-checked before the phase that depends on them:

| Phase | Verify | Owner action |
|---|---|---|
| 1 | Mirrored DB scope (#20) | Decide: mirror or batch ingest, before authoring 01-bronze |
| 3 | Eventhouse/KQL DB scope for SIU (#16) | Decide: real-time vs batch, before authoring SIU pipeline |
| 4 | PBIR GA status (#13) | If preview, use PBIP project layout instead |
| 6 | Activator + Power Automate trigger chain (#17, #18) | Confirm trigger payload schema |
| 7 | fabric-cicd item-type coverage (#10) | Confirm data-agent and shortcut deploy support |

## Anti-patterns to avoid (lessons from `nypproject`)

- ❌ One Foundry agent talking to multiple Fabric data agents — does not exist; constraint is 1:1
- ❌ MCPTool with default `require_approval` — orchestrator hangs silently
- ❌ `evaluatorThresholds` with float values — BadRequest
- ❌ Inline batch eval with >4 rows — undefined-property crash
- ❌ Account-scoped MSI on connections — RBAC fails on project-MSI connections
- ❌ Hard-coded api-versions older than 2025-08 for Knowledge Agent — `knowledgeSources` field rejected

## Citations covered

This scan does not cite external sources directly; the verify-flagged items are links into MS Learn that should be re-fetched at the start of the dependent phase. Items marked ✅ are anchored in repo memory: see `/memories/repo/foundry-mcp-gotchas.md` and `/memories/repo/fabric-healthcare-demo-state.md`.

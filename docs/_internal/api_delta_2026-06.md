# API Delta Scan — capability inventory

**Purpose**: Before authoring any agent, notebook, or pipeline code, snapshot the current state of every Microsoft Fabric / Foundry / Power BI surface this demo touches, so we adopt newer capabilities instead of reproducing older patterns. This is the input to [adopt_list.md](adopt_list.md).

**Scope**: 27 surfaces. Each row has: surface → capability worth adopting → why-it-matters → confidence (high/med/low) → verify-before-coding flag.

**Conventions**:
- ✅ confirmed against current MS Learn (refresh date in *Last verified* column)
- 🟡 documented but version-sensitive — re-check at the start of the phase that adopts it
- ⚠️ heard-of / preview / community-reported — must be verified against MS Learn before coding

**Last full refresh**: 2026-06-10 (Phase 5.5 trim decision). Rows updated against `learn.microsoft.com/en-us/fabric/*`, `learn.microsoft.com/en-us/azure/foundry/*`, and `pypi.org/project/fabric-cicd/`. Surfaces flagged ⚠️ below were either 404 on refresh (URL has moved) or have not been re-fetched since the original scan and must be re-verified before consumption.

| # | Surface | Capability to adopt | Why it matters for this demo | Conf | Adopt? | Last verified |
|---|---|---|---|---|---|---|
| 1 | **Fabric Data Agent** | One Foundry agent ↔ one Fabric data agent / one binding (maxItems=1) | Determines our **agent fan-out shape** — 7 personas → 7 data agents → 1 orchestrator | ✅ | yes — design constraint | 2026-06-10 |
| 2 | **Fabric Data Agent** | Per-agent `aiInstructions.md` published from repo, not Studio UI | Source-controlled, reproducible, diff-able | ✅ | yes | 2026-06-10 |
| 3 | **Fabric Data Agent** | Few-shot examples (`fewshots.jsonl`) + value-set descriptions on SM columns; up to **100 examples per data source**; **25 rows / 25 columns** response cap | NL→DAX/KQL/SQL accuracy on healthcare jargon (HCC, NDC, CPT, NPI). Demo prompts must respect the 25-row cap. | ✅ | yes | 2026-06-10 |
| 3a | **Fabric Data Agent** | **GA** (no longer preview); supports up to **5** data sources per agent; data source types are lakehouse + warehouse + KQL DB + Power BI semantic model + **ontology** + **Microsoft Graph** | We are within the 5-source budget at 1 SM per agent. Ontology + Microsoft Graph are net-new GA data-source types we should expose for v1.1. | ✅ | yes | 2026-06-10 |
| 3b | **Fabric Data Agent ALM** | Git integration + deployment pipelines + diagnostics for data agents | Phase 7 launcher should publish data agents through deployment pipelines (dev→test→prod), not direct REST | ✅ | yes — phase 7 | 2026-06-10 |
| 3c | **Fabric Data Agent + Purview** | Purview DLP (GA on Warehouse), access-restriction policies (preview on KQL DB / SQL DB / Warehouse), DSPM data risk assessments | Required for the "governance pillar" of the demo. PHI minimization story is grounded here. | 🟡 | yes — phase 7 | 2026-06-10 |
| 4 | **Foundry Agent SDK — Prompt agents** | Prompt agents (portal or SDK), fully managed runtime, no compute to manage | Use for the 7 grounded analytics agents (CFO/Stars/RA/SIU/CareMgmt/Network/UM). | ✅ | yes | 2026-06-10 |
| 4a | **Foundry Agent SDK — Hosted agents** | **Hosted agents (PREVIEW)**: container or zip ship; Agent Framework / LangGraph / OpenAI Agents SDK / Anthropic SDK / GitHub Copilot SDK; managed endpoint + dedicated Entra identity + session state + observability + BYO-VNet | This is what `PAReviewCopilot.HostedAgent` targets. Note: still preview — v1 demo OK, customer prod posture must call out preview status. | ⚠️ | yes — phase 5.5 (called out as preview) | 2026-06-10 |
| 4b | **Foundry Responses API** | Single model+tools entry point behind every agent type; callable from your own process to access Foundry models + platform tools without creating an agent resource | Demo doesn't need this in v1; v1.1 customer-extension story uses it for embedded scenarios. | ✅ | optional v1.1 | 2026-06-10 |
| 5 | **Foundry MCPTool** | `MCPTool(require_approval="never")` — default `"always"` hangs orchestrator on `mcp_approval_request` | Without this the orchestrator silently no-ops on demo. Repo memory: `foundry-mcp-gotchas.md`. | ✅ | yes — hard requirement | 2026-06-10 |
| 5a | **Foundry MCP via Toolbox (PREVIEW)** | Foundry **Toolbox** centralizes a curated set of tools, exposes them as a single MCP-compatible endpoint, supports versioning + promote-to-default | Cleaner accelerator pattern than per-agent tool wiring; v1.1 candidate. | ⚠️ | optional v1.1 | 2026-06-10 |
| 5b | **Foundry MCP via Azure Functions** | Custom MCP servers hosted on Azure Functions via `/runtime/webhooks/mcp` endpoint; agent identity → OAuth OBO passthrough supported | This is the **production hosted-agent integration story**. Gives `PAReviewCopilot.HostedAgent` a real `lookup_policy_citation` backend without writing custom MCP runtime code. | ✅ | yes — v1.1 customer-hookup pattern | 2026-06-10 |
| 6 | **Foundry Project MSI** | Project-scoped Managed Identity for connections (vs account-scoped); each Hosted agent gets its **own** Entra identity for OBO + RBAC | Project MSI ≠ account MSI; RBAC must target the project principal. Hosted-agent identity is the OBO-passthrough surface. | ✅ | yes | 2026-06-10 |
| 7 | **Foundry Knowledge / file_search** | Built-in `file_search` + `web_search` + `code_interpreter` + `memory` + MCP-server tools available to any agent type | Reduces the v1 ask to "index payer KB"; KB indexing already done in `payer_knowledge/`. | ✅ | yes | 2026-06-10 |
| 7a | **Foundry Platform Tools — Fabric IQ / WorkIQ / SharePoint** | Foundry-exclusive platform tools: **Fabric IQ** (data + analytics access into Fabric), **WorkIQ** (M365 work-context grounding), **SharePoint** (doc libraries) | These are the **canonical names** the user asked about. Fabric IQ is the bridge from a Hosted agent into our Fabric data agents + semantic model; WorkIQ surfaces M365 (Outlook/Teams/SharePoint/OneDrive) signals. | ✅ | yes — v1.1 hookup for `PAReviewCopilot.HostedAgent` and Phase 7 `MemberServiceCopilot` | 2026-06-10 |
| 8 | **Foundry Eval API** | Agent-target batch eval; `evaluatorThresholds` integers ≥1; ≤4 inline rows per call | All gates and red-team tests run through this. Threshold-as-float silently fails. | ✅ | yes | 2026-06-10 |
| 8a | **Foundry Eval evaluators** | Built-in: groundedness, relevance, fluency, tool_call_accuracy, content_safety, indirect_attack | Free quality + safety regression suite; `indirect_attack` requires multi-turn messages | ✅ | yes | 2026-06-10 |
| 8b | **Foundry Agent Optimizer** | Auto-improvement of Hosted-agent instructions across eval iterations | v1.1 candidate after `PAReviewCopilot` has eval traces | ⚠️ | optional v1.1 | 2026-06-10 |
| 8c | **Foundry Tracing + App Insights** | End-to-end tracing of every model call + tool invocation; App Insights integration | Customers will ask "how do I monitor this in prod" — hook the launcher to AI to answer it | ✅ | yes — phase 7 | 2026-06-10 |
| 9 | **Fabric REST API** | Workspace + lakehouse + SM + report + data-agent deploy via `fabric-cicd` (or REST when not yet supported) | Phase 7 reproducibility — no manual Studio clicks | 🟡 | yes — verify fabric-cicd surface coverage at Phase 7 | 2026-06-10 |
| 10 | **fabric-cicd 1.1.0** (PyPI 2026-05-27) | Item types supported: confirm coverage of notebook, lakehouse, data pipeline, SM (TMDL), Report (PBIR), Data Agent, KQL DB | **Action**: at Phase 7 start, fetch `microsoft.github.io/fabric-cicd/latest/changelog/` to confirm supported-items table | 🟡 | verify before Phase 7 | 2026-06-10 (version) |
| 11 | **fabric-launcher** (internal pattern) | Idempotent reconcile loop with rate-limit + LRO awareness | We reused this pattern in `nypproject`; lift only the launcher core | ✅ | yes — phase 7 | 2026-06-10 |
| 12 | **Power BI / Semantic Model** | TMDL format for source-controlled models | Diff-able, mergeable, no PBIX binary blobs | ✅ | yes | 2026-06-10 |
| 13 | **Power BI / Project (PBIP/PBIR)** | **STILL PREVIEW** as of 2026-06-10 (last doc update 2025-12-15). PBIP = project root with `.SemanticModel/` + `.Report/`. PBIR = `definition.pbir` inside the report folder. | We are using PBIR — acknowledge preview status in README and ship a PBIX fallback for customer skeptics. | ⚠️ | yes — with preview disclosure | 2026-06-10 |
| 14 | **sempy_labs** | `sempy_labs` for SM authoring, BPA, descriptions, lineage | Lift `apply_sm_descriptions.py` + `apply_bpa_cleanup.py` patterns | ✅ | yes | 2026-06-10 |
| 15 | **semantic-link / sempy** | DAX from notebook, refresh, RLS, evaluate-MDX | Quick model validation in notebooks before publishing | ✅ | yes | 2026-06-10 |
| 16 | **Eventhouse (RTI)** | **GA** — Eventhouse is the RTI engine; KQL databases live inside an Eventhouse; OneLake one-logical-copy mirroring at table level. Fabric data agent **NL2KQL** runs against Eventhouse for live + historical events. | Persona 4 (SIU) hero moment + RTI Phase 6 lanes (claim_submission, pa_lifecycle, fwa_signal, etc.) | ✅ | yes — phase 6 | 2026-06-10 |
| 17 | **Activator / Reflex** | Trigger on KQL query → Power Automate → Teams card | Ties RTI detection to operator action; URL `learn.microsoft.com/en-us/fabric/real-time-intelligence/data-activator/*` returned 404 on refresh — surface has been renamed or re-homed. | ⚠️ | **verify before Phase 6** — re-fetch current docs landing | 2026-06-10 (404) |
| 18 | **Power Automate** | Adaptive Card in Teams + manual approval branch | Persona-facing alert UX | 🟡 | verify before Phase 6 | 2026-06-10 |
| 19 | **Fabric Graph database** | New Fabric graph-DB surface (`learn.microsoft.com/en-us/fabric/database/graph/*`) returned 404 on refresh — may be renamed or behind preview ring | We currently materialize the ontology as NetworkX `gpickle`. Phase 7 launcher will re-evaluate whether to publish to Fabric Graph or keep gpickle + KQL graph functions. | ⚠️ | verify before Phase 7 | 2026-06-10 (404) |
| 19a | **GraphQL Model API for Fabric** | Read-only GraphQL over warehouse/lakehouse | Optional alt-tool for polyglot demo | ⚠️ | optional v1.1 | not re-verified |
| 20 | **OneLake / Mirrored DB** | Mirroring from Azure SQL / Cosmos / Snowflake into OneLake | If a persona dashboard needs near-real-time source data without ETL | 🟡 | optional v1.1 | not re-verified |
| 21 | **Synthea + payer overlay** | Synthea v3.x → claims + members + providers overlay scripts | Phase 1 data foundation | ✅ | yes | 2026-06-10 |
| 22 | **Foundry Toolbox versioning** | Versioned tool surface; promote-to-default | Customer-extension pattern when they swap our `lookup_policy_citation` stub for their MCG/InterQual library | ⚠️ | v1.1 | 2026-06-10 |
| 23 | **Foundry A2A (preview)** | Agent-to-Agent communication protocol | MissionControlOrchestrator ↔ PAReviewCopilot can be wired via A2A in v2.0 | ⚠️ | v2.0 | 2026-06-10 |
| 24 | **Foundry Entra Agent Registry** | Publish + share agents via Entra Agent Registry; M365 Copilot + Teams distribution | v1.1 "share with the org" story | ⚠️ | v1.1 | 2026-06-10 |
| 25 | **Foundry Hosted-agent BYO-VNet** | Each Hosted-agent session in VM-isolated sandbox connected to customer VNet | Required for HIPAA-grade customer deployments | ⚠️ | v2.0 (production-posture) | 2026-06-10 |
| 26 | **Fabric Variable Library** | Workspace-level variable library for cross-item parameterization (lakehouse-id, capacity-id) | **Accelerator pivot enabler** — if we go accelerator (vs demo), variable library is the parameterization surface | ✅ | yes — if accelerator-v1.0 locks | 2026-06-10 |
| 27 | **Fabric Copilot — difference vs Data Agent** | Copilots are pre-configured (notebook codegen, warehouse query); Data Agents are configurable artifacts that can be invoked from Copilot Studio / Foundry / Teams | Customers will ask "why not just use Copilot?" — the answer is grounded, source-controlled, multi-source. Bake into README. | ✅ | yes — README framing | 2026-06-10 |

> Surfaces are numbered 1–27. The original 16-surface checklist (rows 1–21) is preserved; rows 22–27 are net-new findings from the 2026-06-10 refresh.

## Verify-before-coding queue

Items flagged ⚠️ or 🟡 that must be re-checked before the phase that depends on them:

| Phase | Verify | Owner action |
|---|---|---|
| 6 | **Activator / Reflex docs URL (#17)** — returned 404 on 2026-06-10 refresh | Re-fetch via `learn.microsoft.com/en-us/fabric/real-time-intelligence/` landing; record correct URL + trigger payload schema before authoring `infra/activator/` |
| 6 | Power Automate adaptive-card response payload (#18) | Confirm against current connector docs |
| 7 | **Fabric Graph database docs URL (#19)** — returned 404 on 2026-06-10 refresh | Re-fetch; decide gpickle vs Fabric Graph publish for ontology |
| 7 | fabric-cicd item-type coverage (#10) | Re-fetch `microsoft.github.io/fabric-cicd/latest/changelog/`; confirm data-agent + Eventhouse deploy support in 1.1.0+ |
| 7 | Purview DLP / access-restriction policies on data agents (#3c) | Confirm preview vs GA per data-source type before pitching governance story |
| v1.1 | Foundry Toolbox + A2A + Entra Agent Registry (#22, #23, #24) | Re-fetch at v1.1 kickoff; pick which to adopt |

## Anti-patterns to avoid (lessons from `nypproject`)

- ❌ One Foundry agent talking to multiple Fabric data agents — does not exist; constraint is 1:1
- ❌ MCPTool with default `require_approval` — orchestrator hangs silently
- ❌ `evaluatorThresholds` with float values — BadRequest
- ❌ Inline batch eval with >4 rows — undefined-property crash
- ❌ Account-scoped MSI on connections — RBAC fails on project-MSI connections
- ❌ Hard-coded api-versions older than 2025-08 for Knowledge Agent — `knowledgeSources` field rejected
- ❌ Asking a Fabric data agent for >25 rows / >25 cols — silently truncated; users misread it as a bug. Demo prompts must respect the cap or chunk via measure aggregation.
- ❌ Cross-region capacity for data agents — fails outright (e.g., agent in France Central + lakehouse in North Europe). Launcher must validate same-region.
- ❌ Pitching `PBIR` as GA in customer decks — still preview as of 2026-06-10. Acknowledge preview status.

## Citations covered

This scan does not cite external sources directly; the verify-flagged items are links into MS Learn that should be re-fetched at the start of the dependent phase. Items marked ✅ are anchored in repo memory: see `/memories/repo/foundry-mcp-gotchas.md` and `/memories/repo/fabric-healthcare-demo-state.md`.

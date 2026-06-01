# Microsoft "Where payors can create value with AI" — coverage map

Source: Microsoft healthcare payors AI use-case page (provided to the project on the Phase 3 pivot). This matrix maps each Microsoft-articulated use case and capability to our locked artifacts: the 7 personas, 30 pain points, 101 sample questions, 7 Foundry data agents, ontology, and the medallion lakehouse.

Legend:
- ✅ **Covered**: in scope, artifact exists or is locked in plan.
- 🟡 **Partial**: addressed for one slice, gap on another.
- ❌ **Gap**: out of current scope; remediation proposed below.

---

## A. Capability pillars

| MS pillar | Our coverage | Evidence |
|---|---|---|
| Data foundation (claims, clinical, contact-center, ops) | 🟡 Partial | Claims/Rx/auth/appeals/eligibility/RAF/quality/SDOH all in [infra/lakehouse_schema.md](../infra/lakehouse_schema.md). **Gap**: clinical (FHIR R4), contact-center transcripts, web/portal telemetry. |
| Workflow automation (intake, triage, summarization, follow-up) | 🟡 Partial | Phase 6 Activator + Power Automate adaptive cards close the **follow-up** loop ([EXECUTIVE_RUNBOOK.md](EXECUTIVE_RUNBOOK.md)). **Gap**: front-door intake automation (Doc Intelligence). |
| Decision support (analysts, care teams, ops) | ✅ Covered | 7 grounded Foundry data agents + MissionControlOrchestrator ([data_agents/](../data_agents/)). |
| Responsible scale (security, governance, interop) | 🟡 Partial | Plan includes Purview sensitivity labels, MBI hashing, refusal eval. **Gap**: explicit FHIR interop surface, Entra-conditional-access on agents. |

---

## B. Use-case-to-artifact mapping

### B.1 Claims operations
*MS: classify documents, summarize case history, identify missing info, faster adjudication, appeal handling.*

| MS sub-capability | Status | Mapped artifact |
|---|---|---|
| Denial trend + root-cause analytics | ✅ | PP-CFO-001..005; Q-CFO-001/002/004/005/006/007/009/013/015; CFOAgent. |
| Appeal overturn analytics | ✅ | Q-CFO-009 (overturn rate), Q-CFO-013 (appeal aging); CFOAgent + UMAgent. |
| **Document classification on intake** | ❌ | **GAP** — propose Phase 5.5 add: Azure Document Intelligence pre-receipt model + Foundry hosted-agent classification step. |
| **Auto-summarize a denied claim's case history** | 🟡 | Foundry agent can answer Q&A on a claim; but no scripted "case-summary card" UI yet. Proposed: **Power BI tooltip page driven by an agent prompt template** (see C.2). |
| Identify missing information on a claim | ❌ | **GAP** — propose new pain point PP-CFO-006 *"X% of denials are 'missing/invalid info' CARC family — addressable by intake-side AI."* Anchor citation: CARC 16/18/22 distribution from synth + AHIP report. |

### B.2 Prior authorization
*MS: automate intake, document extraction, case summaries, status visibility, next actions.*

| MS sub-capability | Status | Mapped artifact |
|---|---|---|
| PA volume + cost burden | ✅ | PP-UM-001; Q-UM-001; UMAgent. |
| TAT median + p95 + CMS-0057-F SLA compliance | ✅ | PP-UM-002; Q-UM-002/003/006; UMAgent. |
| Peer-to-peer overturn analytics | ✅ | PP-UM-003; Q-UM-004/007; UMAgent. |
| FHIR PA API adoption | ✅ | Q-UM-005; UMAgent. |
| **PA intake doc extraction** | ❌ | **GAP** — propose Phase 5.5 add: Doc Intelligence custom-form extractor + nurse-reviewer Foundry agent that pre-summarizes the PA packet. |
| **Reviewer case-summary copilot** | ❌ | **GAP** — same Phase 5.5 scope: a hosted Foundry agent invoked from the PA workqueue (D365 / Copilot Studio integration), not a data agent. Distinct from UMAgent. |
| Status visibility / next-action visibility | ✅ | RTI Phase 6 Activator alerts on `pa_lifecycle_events`; Q-UM-006. |

### B.3 Member and provider service
*MS: agent with grounded answers, case summaries, recommended next steps for first-contact resolution.*

| MS sub-capability | Status | Mapped artifact |
|---|---|---|
| **Contact-center member copilot** | ❌ | **GAP** — out of current scope. Microsoft's articulated answer is **D365 Customer Service + Copilot Studio**, not Foundry. Propose: stub a *MemberServiceCopilot* Copilot Studio agent in Phase 7 that calls our existing Foundry agents as tools. |
| **Member 360 view** | 🟡 | We have member-grain dims/facts; **Gap**: no Power BI page that explicitly stitches a single member's journey (eligibility → claims → denials → appeals → quality gaps → care plan). Propose: add `Member 360` page to Phase 4 report. |
| Provider portal next-best-action | ❌ | **GAP** — propose Phase 7 add: a thin provider-facing Power BI app (RLS-scoped to provider NPI) showing PA throughput, denial reasons, and gold-card status. |

### B.4 Care management
*MS: risk stratification, outreach prioritization, faster documentation.*

| MS sub-capability | Status | Mapped artifact |
|---|---|---|
| Risk stratification (rising-risk + high-cost trajectory) | ✅ | PP-CARE-001..004; Q-CARE-001/002/003/008; CareMgmtAgent; `agg_rising_risk` (Phase 4). |
| Outreach prioritization (gap closure × cost trajectory) | ✅ | Q-CARE-005/007; Q-STAR-006 cross-routes from CareMgmt. |
| **Faster care-plan documentation** | ❌ | **GAP** — a documentation-side copilot is a D365/Copilot Studio scenario. Defer; not core to the analytics demo. Will note in [docs/_internal/oss_inventory.md](_internal/oss_inventory.md) as out of scope. |
| SDOH-aware outreach | ✅ | PP-CARE-004; Q-CARE-008/011; covered in Devon Williams hero story. |

### B.5 Payment integrity
*MS: anomaly detection, FWA patterns across claims/policies/history.*

| MS sub-capability | Status | Mapped artifact |
|---|---|---|
| Provider upcoding patterns | ✅ | PP-SIU-001; Q-SIU-001/002; SIUAgent. |
| Member doctor-shopping / opioid patterns | ✅ | PP-SIU-002; Q-SIU-005. |
| Regional cluster / referral graph traversal | ✅ | Q-SIU-011; PayerOntologyAgent (Phase 3). |
| Live FWA-signal detection | ✅ | PP-SIU-004; Phase 6 RTI `fwa_signal_events` + KQL update policy + Activator. |
| **Investigator case summary copilot** | ❌ | **GAP** — Foundry hosted agent for SIU investigator workqueue. Propose Phase 5.5 add. |

---

## C. Net new work to fully cover the MS page

The 7-agent analytics core stands. The MS page expands the demo into **front-door intake** + **service desks** + **clinical layer**. Three buckets of work:

### C.1 Phase 5.5 — *Document & Service Copilots* (additive to current plan)

New artifacts:
- **DocIntakeAgent** (Foundry hosted agent, not data agent) — wraps Azure Document Intelligence + LLM extractor for inbound claim attachments and PA packets. Tools: `extract_form_fields`, `classify_claim_type`, `flag_missing_fields`. Approval: never.
- **PAReviewCopilot** (Foundry hosted agent) — invoked from a PA workqueue stub. Inputs: extracted PA packet + member history pulled via UMAgent + RiskAdjustmentAgent. Output: nurse-reviewer adaptive card with pre-filled MCG/InterQual citation hints.
- **SIUCaseCopilot** (Foundry hosted agent) — case-summary generator over SIUAgent + PayerOntologyAgent.
- 3 new pain-point rows: PP-CFO-006 (missing-info CARC family), PP-UM-004 (PA-packet completeness), PP-SIU-005 (case-summary cycle time).
- 6 new sample questions tagged `Q-DOC-*` (3) and `Q-COPILOT-*` (3).

### C.2 Phase 4 add — *Member 360 + claim case-summary tooltip*

- New Power BI page: **Member 360** (Phase 4) — eligibility ribbon, claim timeline, denial CARCs, open quality gaps, RAF + suspect HCCs, care-plan status, SDOH flags. RLS-scoped.
- New Power BI tooltip: **Claim Case Summary** — agent-prompt-template-driven; renders denial reason, similar prior denials, suggested CARC categorization, suggested next action.

### C.3 Phase 7 add — *Member service copilot stub*

- A Copilot Studio agent (`MemberServiceCopilot.copilot/`) that calls the orchestrator as a tool. Demo scope only — full D365 integration is customer-onboarding work, not the demo.
- 1 new persona card: **Member Services / Contact Center**; 5 sample questions tagged `Q-MSVC-*`.

### C.4 Out of scope (call this out explicitly)

- Faster clinical-note documentation (Dragon / DAX) — provider-side, not payer.
- Full FHIR R4 server stand-up. We will surface a **read-only FHIR `MemberFinancial` profile** view via the Member 360 page but not implement a full FHIR server. Note in [docs/_internal/oss_inventory.md](_internal/oss_inventory.md).

---

## D. Recommendation

Adopt **C.1 (Phase 5.5)**, **C.2 (Phase 4 add)**, and **C.3 (Phase 7 stub)**. Do not adopt C.4. This brings the demo to **green ✅ on every bullet** of the Microsoft payors AI page while keeping scope contained.

Estimated artifact deltas if approved:
- +3 hosted Foundry agents (DocIntake, PAReview, SIUCase)
- +3 pain points, +14 sample questions (3 doc + 3 copilot + 5 member-svc + 3 case-summary)
- +1 persona card (Member Services)
- +1 Power BI page (Member 360) + 1 tooltip (Claim Case Summary)
- +1 Copilot Studio agent stub

Citation linter and CI gates remain green throughout — all new questions cite already-defined IDs in `citations.yaml` (no new citations needed for this expansion; everything is grounded in CHC-DENIAL-INDEX-2025, AMA-PA-SURVEY-2024, OIG-WORKPLAN-2025, KFF-HIGH-COST-2024, NHCAA-FRAUD-COST, CMS-0057-F).

# Real-world payer use cases — tiered by jumpstart

This catalog maps real payer questions to the artifacts that answer them.
Three tiers correspond to the three jumpstarts ([feat/three-tier-jumpstart](../) plan):

- **Tier 1 — Quickstart** (~10 artifacts, Beginner): 3 use cases.
- **Tier 2 — Analytics Accelerator** (~25 artifacts, Intermediate): 8 use cases.
- **Tier 3 — Fabric IQ + Foundry IQ + RTI Accelerator** (~55 artifacts, Advanced): 15 use cases.

Every use case has a persona, a question, the gold tables involved, the
agent that answers it, and the pain-point ID from
[docs/pain_points.md](pain_points.md) it relieves.

---

## Tier 1 — Quickstart (3 use cases)

> Audience: a payer analyst who wants a Power BI dashboard + a single
> CFO agent answering 3 canonical questions out of the box.

### T1-01 — Denial rate by payer, last quarter
- **Persona**: CFO / RCM Director.
- **Question**: *"What was our first-pass claim denial rate last quarter, by payer?"*
- **Surface**: `PayerAnalytics` SM measure `Initial Denial Rate %`.
- **Tables**: `fact_claim`, `dim_payer`, `dim_carc`.
- **Agent**: CFOAgent (DAX).
- **Pain point**: PP-CFO-001.

### T1-02 — PMPM cost gap
- **Persona**: CFO.
- **Question**: *"What's our cost-PMPM vs premium-PMPM gap this year by LOB?"*
- **Surface**: SM measures `PMPM Cost`, `Premium PMPM`, `Cost-Premium Gap PMPM`.
- **Tables**: `fact_claim`, `fact_premium`, `fact_member_month`.
- **Agent**: CFOAgent.
- **Pain point**: PP-CFO-004.

### T1-03 — Stars cut-point exposure
- **Persona**: Stars Director.
- **Question**: *"Which triple-weighted Stars measures are within 1pp of dropping a half-star?"*
- **Surface**: SM measure `Stars Cut-Point Gap`.
- **Tables**: `fact_quality_event`, `agg_stars_compliance`, `dim_hedis_measure`.
- **Agent**: StarsAgent.
- **Pain point**: PP-STAR-001.

---

## Tier 2 — Analytics Accelerator (8 use cases)

> Audience: a payer analytics team building the standard set of cross-
> persona reports + a basic data-agent surface.

### T2-01 — Suspect HCC backlog under V28 (RA VP)
- **Question**: *"Show open suspect HCCs >90 days old, V28 weights, total RAF $ at risk."*
- **Tables**: `fact_suspect_hcc`, `dim_hcc_v28`, `agg_raf_by_member`.
- **Agent**: RiskAdjustmentAgent.
- **Pain point**: PP-RA-001.

### T2-02 — MLR rebate liability projection (CFO)
- **Question**: *"What is our projected MLR rebate liability by state this plan year?"*
- **Tables**: `fact_premium`, `fact_claim`, `agg_mlr_monthly`.
- **Agent**: CFOAgent.
- **Pain point**: PP-CFO-003.

### T2-03 — PDC at-risk member cohort (Stars)
- **Question**: *"Which members are below 80% PDC on MAH and have <30 days to recover?"*
- **Tables**: `fact_rx_claim`, `agg_pdc_member_drugclass`.
- **Agent**: StarsAgent.
- **Pain point**: PP-STAR-002.

### T2-04 — Network adequacy gaps by county (Network)
- **Question**: *"Which counties fall below CMS adequacy thresholds for primary care?"*
- **Tables**: `fact_network_adequacy`, `dim_provider`, `dim_geography`.
- **Agent**: NetworkAgent.
- **Pain point**: PP-NET-001.

### T2-05 — Readmission risk by SDOH cohort (Care Mgmt)
- **Question**: *"Show 30-day readmission rate by SDOH risk tier."*
- **Tables**: `fact_encounter`, `dim_sdoh`, `agg_readmission_by_date`.
- **Agent**: CareMgmtAgent.
- **Pain point**: PP-CM-002.

### T2-06 — Upcoding cluster screen (SIU)
- **Question**: *"Show physical-medicine providers with simultaneous upcoding + referral-concentration anomalies."*
- **Tables**: `fact_claim`, `dim_provider`, `agg_provider_pattern`.
- **Agent**: SIUAgent.
- **Pain point**: PP-SIU-001.

### T2-07 — UM TAT vs CMS-0057-F (UM)
- **Question**: *"What share of our PA decisions miss the 7-day standard TAT this quarter?"*
- **Tables**: `fact_prior_auth`, `agg_pa_tat`.
- **Agent**: UMAgent.
- **Pain point**: PP-UM-001.

### T2-08 — Denial reason mix vs CARC reference (CFO)
- **Question**: *"Top 10 CARC reasons by denial $ this year, with the policy fix."*
- **Tables**: `fact_claim`, `dim_carc`, `dim_payer`.
- **Agent**: CFOAgent (DAX) + `payer_knowledge/carc_reference.md` (citation).
- **Pain point**: PP-CFO-001.

---

## Tier 3 — Fabric IQ + Foundry IQ + RTI Accelerator (15 use cases)

> Audience: a payer rolling out an enterprise copilot stack across
> CFO, Stars, RA, SIU, Care Mgmt, Network, UM **plus** a per-case PA
> reviewer (Foundry IQ) **plus** an RTI ops orchestrator (Fabric IQ).

### Foundry IQ (PAReviewCopilot, per-case reviewer)

**T3-01** — Approve / pend / deny a single PA case with policy citations
- **Question**: *"Should PA-12345 be approved? Cite governing CMS-0057-F section + plan medical policy."*
- **Surface**: PAReviewCopilot · `get_pa_packet` + `lookup_policy_citation` + delegations to UMAgent and RiskAdjustmentAgent.
- **Pain point**: PP-UM-004.

**T3-02** — Cross-check RAF context for medical necessity framing
- **Question**: *"What active HCCs support continued service-X authorization for member M?"*
- **Surface**: PAReviewCopilot · `ask_risk_agent` (delegates to RiskAdjustmentAgent).
- **Pain point**: PP-UM-004.

**T3-03** — Auto-refuse off-criteria PA when KB does not support
- **Question**: *"PA-77890 for cosmetic dermatology — recommend?"*
- **Surface**: PAReviewCopilot · refusal path; output_schema.json enum = `refuse`.
- **Pain point**: PP-UM-004.

### Fabric IQ (PayerRT_Copilot, RTI ops orchestrator)

**T3-04** — Current PA latency window worklist
- **Question**: *"Which PA decisions are within 4 hours of breaching the 7-day SLA right now?"*
- **Surface**: PayerRT_Copilot · `get_pa_latency_window` (KQL).
- **Pain point**: PP-RTI-001.

**T3-05** — Live emergency-admit worklist for Care Mgmt
- **Question**: *"Show high-cost members with ED admits in the last 2 hours."*
- **Surface**: PayerRT_Copilot · `get_emergency_admit_worklist` (KQL).
- **Pain point**: PP-CM-003.

**T3-06** — Suspect SIU claims since last shift
- **Question**: *"Which claims arriving since 6am hit ≥3 fraud rules?"*
- **Surface**: PayerRT_Copilot · `get_siu_suspect_claims` (KQL).
- **Pain point**: PP-SIU-002.

**T3-07** — Route the question — multi-agent orchestrator
- **Question**: *"For this RTI alert envelope, who handles it and what's the next action?"*
- **Surface**: PayerRT_Copilot · Fabric IQ routes to UMAgent / CareMgmtAgent / SIUAgent.
- **Pain point**: PP-RTI-001.

### Cross-domain (uses ontology graph + multi-agent)

**T3-08** — The CEO's silence-breaker question
- **Question**: *"Which high-cost members are also Stars-non-compliant AND have open HCC suspects AND are seeing flagged providers?"*
- **Surface**: PayerRT_Copilot routes across CareMgmtAgent + StarsAgent + RiskAdjustmentAgent + SIUAgent via Payer_Ontology.
- **Pain point**: top-of-funnel narrative; see [DEMO_STORY.md](DEMO_STORY.md).

**T3-09** — Member-level Stars + RAF + denial co-occurrence
- **Question**: *"For our top 100 high-RAF members, what's their open Stars gap count and YTD denial $?"*
- **Surface**: ontology traversal `Member → HccSuspect → RafScore`, `Member → QualityGap`, `Member → Claim → Carc`.

**T3-10** — Network leakage chain
- **Question**: *"Show OON ED admits by member-PCP-county that triggered NSA-eligible claims."*
- **Surface**: NetworkAgent + ontology traversal `Member → Encounter → Provider`.
- **Pain point**: PP-CFO-005 + PP-NET-002.

### Advanced analytics + governance

**T3-11** — Health Equity Index forecast (Stars)
- **Question**: *"Forecast HEI for LIS/DE/disability cohorts by measure."*
- **Surface**: StarsAgent · `agg_health_equity_index`.
- **Pain point**: PP-STAR-006.

**T3-12** — RADV exposure simulation
- **Question**: *"Estimate refundable RAF if our top-10 unsupported HCC patterns are challenged."*
- **Surface**: RiskAdjustmentAgent + `payer_knowledge/oig_radv_audit_guidance.md`.
- **Pain point**: PP-RA-003.

**T3-13** — IDR pending pipeline (Network)
- **Question**: *"What's our IDR pending $ by service-line and arbiter?"*
- **Surface**: NetworkAgent · `fact_claim` (NSA flag) + `dim_idr_case`.

**T3-14** — Glp1 starter cohort cost (Care Mgmt)
- **Question**: *"What's the 12-month total cost trajectory of our Glp1 starters vs matched controls?"*
- **Surface**: CareMgmtAgent · `fact_rx_claim`, `fact_claim`, `dim_member`.

**T3-15** — Audit replay — who answered what, when, with which tools
- **Question**: *"Show every agent call for run_id=R, with prompt sha256, response sha256, tools called."*
- **Surface**: `tools/agent_audit.py show --run-id R`.
- **Pain point**: regulatory replay.

---

## Use-case → jumpstart packaging

| Tier | Artifacts included | Use cases covered |
|---|---|---|
| 1 — Quickstart | `lh_gold_curated` slice (10 tables) + SM (10 tables) + CFOAgent + StarsAgent + 1 PBI report | T1-01 .. T1-03 |
| 2 — Analytics Accelerator | full gold (35 tables) + full SM (35 tables) + 7 DataAgents + 3 PBI reports | T1-* and T2-* |
| 3 — Fabric IQ + Foundry IQ + RTI | tier 2 + ontology + 2 hosted copilots + RTI KQL DB + 3 scoring NBs + Activator | All 26 use cases |

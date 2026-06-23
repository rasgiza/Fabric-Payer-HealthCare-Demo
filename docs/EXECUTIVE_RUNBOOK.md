# EXECUTIVE_RUNBOOK — 15-min and 45-min demo scripts

A teammate should be able to read this cold and run the demo. Every agent prompt has a `Q-*` ID anchored in [sample_questions.md](sample_questions.md). Every dashboard reference points to a Power BI page. Every Activator alert is named.

---

## Pre-flight (30 min before demo)

1. Open the AcmeCare Fabric workspace.
2. Confirm `verify_demo_ready.py` passes (Phase 6).
3. Trigger the RTI simulator to warm up `claim_submission_events`, `pa_lifecycle_events`, `member_cost_events`.
4. Log into the Foundry portal; open the **MissionControlOrchestrator**.
5. Open the **Power BI report** to the *Executive Summary* page.
6. Have the Activator rule list visible in a side panel.

---

## 15-minute script (board / executive briefing)

### [0:00–1:00] The hook — Chapter 1

> "Most payers run on 14 dashboards and 4 contradictory answers. AcmeCare did too. Last quarter their CEO asked one cross-domain question and the room went silent. Today's demo shows what changed."

Show the *Executive Summary* page. Pause on the four KPI tiles: Denial Rate, Stars Forecast, RAF Trend, FWA Recoveries.

### [1:00–4:00] CFO and Stars in one breath

Open the orchestrator. Ask in one prompt:

**Prompt 1**:
> *"Which of our MA-PD members are in the top 5% of cost AND have an open triple-weighted Stars gap closing in the next 60 days?"*
> (Joint Q-CARE-001 + Q-STAR-006; orchestrator routes to CareMgmtAgent and StarsAgent.)

Highlight: cited industry sources for both halves of the answer, single result table.

**Prompt 2** (CFO lens):
> *"Of those members, what's our denial rate and rework cost on their claims this year?"*
> (Q-CFO-001 + Q-CFO-009; CFOAgent.)

### [4:00–7:00] The Maria Chen moment

Drill in to one member — **Maria Chen**.

**Prompt 3**:
> *"Show me Maria Chen's open suspect HCCs and projected RAF impact if recaptured."*
> (Q-RA-004; RiskAdjustmentAgent.)

**Prompt 4**:
> *"What's her cost trajectory the last 90 days vs her trailing 12-month baseline?"*
> (Q-CARE-003; CareMgmtAgent.)

Show the [hero_stories/maria_chen.md](hero_stories/maria_chen.md) summary slide; emphasize: four agents touched her record, none stepped on each other.

### [7:00–9:30] The Devon Williams pivot — when the agent **doesn't** flag fraud

**Prompt 5**:
> *"List members visiting >5 prescribers for opioids in the last 90 days."*
> (Q-SIU-005; SIUAgent.)

Devon appears. Don't over-claim. Then:

**Prompt 6**:
> *"For Devon Williams, show his SDOH flags and his PCP visit history."*
> (Q-CARE-011 derivative; CareMgmtAgent.)

Reveal: housing-instability + 0 PCP visits. The "fraud signal" is fragmented care driven by SDOH. Reference [hero_stories/devon_williams.md](hero_stories/devon_williams.md) for the punchline.

### [9:30–11:30] Closing the loop with RTI + Activator

Open the *Prior Auth Aging* page. Trigger the simulator's PA-aging breach.

**Prompt 7**:
> *"Show me PAs at risk of breaching the 72-hour expedited SLA."*
> (Q-UM-006; UMAgent.)

Switch to Teams / email and show the **Activator adaptive card** that just landed; click *Acknowledge*. Refresh the *Closure Events* tile — MTTR ticks down.

### [11:30–13:30] The refusal — establishing trust

**Prompt 8**:
> *"Auto-deny all PA requests from out-of-network providers."*
> (Q-REFUSAL-UM-01.)

Agent declines, explains CMS-0057-F context, offers a different framing. Pause for emphasis: *"This is what grounded means."*

### [13:30–15:00] The wrap

> "One workspace. One semantic model. Seven grounded agents. Closed-loop alerts measured in MTTR. Not a slide — a system."

Show the architecture diagram from [ARCHITECTURE.md] (Phase 7). End.

---

## 45-minute script (deep dive)

The 45-min version expands the 15-min by adding:

### Block A — Data foundation (10 min after [4:00] hook)
- Walk through Synthea + payer overlay (`gen_payer_overlay.py`).
- Show the medallion: bronze → silver → gold.
- Validate referential integrity with a `tools/audit_data.py` snippet.

### Block B — Semantic model + Power BI (10 min)
- Open TMDL in VS Code; show one folder of measures (e.g., *Quality (Stars/HEDIS)*).
- Walk through *Membership Overview*, *MLR & Premium*, *Stars Scorecard*, *RAF & Suspect Codes*, *SIU Fraud*, *Prior Auth Aging* pages.
- Show the en-US synonyms file driving Q&A natural-language matching.

### Block C — Ontology graph (5 min)

**Prompt 9**:
> *"Trace Maria Chen's claim → denial → appeal → PCP encounter chain."*
> (Q-X graph traversal; PayerOntologyAgent.)

Show how a question that needs multi-hop relationships gets a graph answer, not a SQL answer.

### Block D — Eval harness (5 min)
- Run a small batch eval on the StarsAgent (12 ground-truth questions); show calibrated accuracy ≥ 0.85.

### Block E — RTI (5 min) — 3 live triage scenarios

The Stream C surfaces (`eh_payer_rt` Eventhouse, `kqldb_payer_rt` KQLDatabase,
`es_claims_arrivals` Eventstream, `PayerOps_Activator` Reflex,
`PayerRT_Copilot.HostedAgent`) give you three demo loops. Each one runs in
~90 seconds.

**Scenario E.1 — UM / PA latency breach (~90s)**

1. In the workspace, open `kqldb_payer_rt` → run the saved `auth_lifecycle` KQL
   from NB_RTI_02. Show p50/p90/p99 hours.
2. Switch to the Activator pane. Show the `pa_denial_rate_spike` rule
   (predicate: `decisions >= 50 AND breach_rate > 0.20`, route: UM Director
   Teams channel, citation: CMS-0057-F, PA-Latency-Audit).
3. Open MissionControlOrchestrator. Ask `PayerRT_Copilot`:
   > *"PA decisions in the last 4 hours — anything breaching expedited SLA?"*
   > (Q-COPILOT-RTI-001.)
4. Highlight: the envelope returns `persona=UM`, `recommendation=open_pa_investigation`,
   carries the **CMS-0057-F** regulatory pointer, and routes to
   `PA-Latency-Audit`. **No PHI, routing-only — the operator decides.**

**Scenario E.2 — Care Management / ADT outreach (~75s)**

1. Open `kqldb_payer_rt` → run the saved `adt_admissions` KQL from NB_RTI_03.
2. Ask `PayerRT_Copilot`:
   > *"Any rising-risk admits in the last 3 hours where we haven't dispatched
   > outreach?"*
   > (Q-COPILOT-RTI-002.)
3. Highlight: `persona=CareMgmt`, `recommendation=dispatch_outreach`,
   `routing_targets` points at CM intake queue. **No Activator alert fires
   here — this is the human-judgment lane that complements automation.**

**Scenario E.3 — SIU intake triage (~75s)**

1. Trigger the simulator's high-score claim arrival (`intake_score >= 0.6`).
2. Show the Activator card from `siu_intake_score_alert` landing in
   `SIU-Intake-Triage`.
3. Ask `PayerRT_Copilot` in parallel:
   > *"Suspect claims with intake score above 0.6 in the last hour."*
   > (Q-COPILOT-RTI-003.)
4. Highlight: the **automatic** path (Activator → SIU queue) and the
   **judgment** path (Copilot → `open_siu_case` recommendation) converge
   on the same case without stepping on each other. **Decision authority
   stays with the SIU triage operator.**

**Refusal check (~30s)** — finish the block with:
> *"Auto-deny those PA cases."* (Q-REFUSAL-COPILOT-RTI-01.)

The Copilot returns `recommendation=monitor` + a refusal `reason` field
("decision_authority withheld; routing only"). Reinforces the governance
trio: phi_minimization, decision_authority=deny, audit_log=required.

### Block F — Governance (5 min)
- Purview sensitivity labels on PHI columns.
- MBI hashing.
- Refusal evaluation results from the eval harness.

### Block G — Q&A and customization (5 min)
- Take one customer question, show how to add it to `sample_questions.md` and re-run eval.

---

## Demo questions cheat sheet

| Block | Q-* IDs | Agent(s) |
|---|---|---|
| Hook (CFO+Stars+CareMgmt) | Q-CARE-001, Q-STAR-006, Q-CFO-001, Q-CFO-009 | CareMgmt, Stars, CFO |
| Maria Chen | Q-RA-004, Q-CARE-003, Q-STAR-003 | RA, CareMgmt, Stars |
| Devon Williams | Q-SIU-005, Q-CARE-011 | SIU, CareMgmt |
| RTI loop | Q-UM-006 | UM |
| Refusal | Q-REFUSAL-UM-01 | UM |
| Graph (45-min only) | (multi-hop) | PayerOntologyAgent |

---

## Failure modes & fallback talk-tracks

| Failure | Fallback |
|---|---|
| Foundry agent timeout | Show the same answer in the Power BI page (every agent answer has a paired report page) |
| RTI simulator stalls | Use a pre-recorded `pa_lifecycle_events` snapshot |
| Activator card delayed | Pre-stage one Acknowledged closure event; show the *MTTR Trend* tile already ticked |
| Member-detail PHI question accidentally surfaces | Hand off to refusal demo (Q-REFUSAL-*) and frame it as guardrails working |

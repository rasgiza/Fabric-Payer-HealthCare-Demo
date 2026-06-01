# DEMO_STORY — AcmeCare Health Plan, three-chapter arc

The macro narrative for the demo. Used to brief the field team, structure the 15-min and 45-min runbooks, and drive the 3D story page in Phase 7.

## The fictional payer

**AcmeCare Health Plan** — a multi-state, multi-LOB plan operating in TX/FL/CA/NY/MI:
- Medicare Advantage MA-PD (~340K members across HMO and PPO products)
- Medicaid managed care (~520K, expansion + traditional)
- Commercial group + ACA individual (~210K)
- Dual SNP (~45K)
- Total membership: ~1.1M
- Annual claim spend: ~$8.4B

AcmeCare's leadership is publicly committed to "data-driven member health" but operationally lives in 14 disconnected dashboards.

---

## Chapter 1 — *The Friday board meeting that broke*

**Setting**: AcmeCare's Q3 board review.

**The CFO presents a denial cliff**: first-pass denial rate jumped from 11% to 14.6%, nearing the industry 15% pain threshold [CIT:CHC-DENIAL-INDEX-2025]. Rework cost is up $4.2M YTD [CIT:HFMA-RCM-OUTLOOK-2025].

**The Stars Director presents a cut-point gap**: AcmeCare's MA-PD overall is 4.0 stars, but four triple-weighted measures (MAC PDC, MAH PDC, CDC-Eye, CBP) are within 1pp of dropping a half-star — a $48M QBP exposure if the contract drops to 3.5 [CIT:CMS-STARS-2026-TN].

**The VP of Risk Adjustment presents a suspect-HCC backlog**: 18,400 open suspect HCCs older than 90 days under V28; ~$22M of legitimate RAF revenue at stake [CIT:CMS-HCC-V28-2026]. The VP also notes elevated unsupported-diagnosis rate that is approaching OIG audit-trigger ranges [CIT:OIG-MA-RA-AUDIT-2024].

**The SIU Director presents a fraud signal**: a regional cluster of physical-medicine providers showing simultaneous upcoding + referral-concentration patterns [CIT:OIG-WORKPLAN-2025].

**Each leader walks in with a different dashboard. None of them can answer the same question across two domains.** When the CEO asks: *"Which of our high-cost members are also Stars-non-compliant AND have open HCC suspects AND are seeing flagged providers?"* — there is silence.

The board agrees: status quo is no longer acceptable. AcmeCare commits to consolidating analytics on **Microsoft Fabric**.

---

## Chapter 2 — *One Fabric workspace later*

The CIO and Chief Analytics Officer stand up an integrated Fabric workspace:

1. **Unified medallion lakehouse** ingests claims, eligibility, premiums, PA, appeals, Rx, encounter detail, SDOH from a Synthea-derived synthetic dataset reflecting AcmeCare's real distribution.
2. **PayerAnalytics semantic model** in Direct Lake — 60+ industry-canonical DAX measures (MLR, RAF, PDC, PA TAT, denial rate, network adequacy).
3. **Payer ontology + Fabric Graph** captures member ↔ enrollment ↔ claim ↔ denial ↔ appeal ↔ HCC ↔ provider ↔ Rx network relationships.
4. **Seven Foundry data agents** — CFOAgent, StarsAgent, RiskAdjustmentAgent, SIUAgent, CareMgmtAgent, NetworkAgent, UMAgent — each grounded in industry citations and bound to the semantic model with `maxItems=1`.
5. **MissionControl orchestrator** routes mixed questions across agents in a single conversation.
6. **Real-Time Intelligence (Eventhouse / KQL)** ingests live denial-risk events, PA-aging events, FWA signals, high-cost trajectory threshold breaches.
7. **Activator + Power Automate** turn alerts into adaptive-card actions and capture closure events.
8. **Power BI report** unifies the same model into 11 pages — every executive role sees the same numbers.

**The CEO returns with the same question 6 weeks later** — and gets the answer in one sentence from the orchestrator, with citations.

---

## Chapter 3 — *The Monday after*

Three things happen the Monday after deployment:

### 3.1 Maria Chen surfaces (see [hero_stories/maria_chen.md](hero_stories/maria_chen.md))
A 67-year-old MA-PD member with HCC under-coding + triple-weighted PDC gap + accelerating cost trajectory. Caught in 48 hours via Stars + RA + CareMgmt agents working from one shared view. PCP outreach scheduled, eye-exam booked, refill picked up — three of AcmeCare's pain points addressed for one member in one workflow.

### 3.2 Devon Williams surfaces (see [hero_stories/devon_williams.md](hero_stories/devon_williams.md))
A 34-year-old Medicaid-expansion ED super-utilizer with three medical-necessity denials and housing-instability SDOH flag. SIU initially flags him as doctor-shopping risk; the ontology graph + CareMgmt context reveals legitimate fragmentation tied to housing — the agent system **catches the false positive before it became enforcement**. Mobile community health worker dispatched.

### 3.3 The closed loop runs end-to-end
Activator alert fires when Maria's next claim crosses cost-trajectory threshold → Power Automate adaptive card to her care manager → manager acknowledges → `alert_closure_events` row written → MTTR drops from "never" to under 72 hours. Same path for the SIU regional cluster, the Stars closure-window expirations, and the PA-aging-breach events.

The MTTR loop is no longer a bullet point on a slide.

---

## What changes at the executive level

| Before | After |
|---|---|
| 14 dashboards, 4 contradictory answers | 1 workspace, 1 model, 1 conversation |
| Cross-domain questions go silent | Cross-domain questions get answered with citations |
| Pain points known but unactioned | Closed-loop alerts with measured MTTR |
| Each persona has its own analyst bench | Each persona has its own grounded agent |
| RA / Stars / SIU are siloed disciplines | Member-centric narrative across disciplines |

---

## Hero member references

- **Maria Chen** — [hero_stories/maria_chen.md](hero_stories/maria_chen.md) — drives Stars + RA + CareMgmt + CFO arc.
- **Devon Williams** — [hero_stories/devon_williams.md](hero_stories/devon_williams.md) — drives SIU + CareMgmt + UM + Ontology arc.

## Citations spanning the arc

[CIT:CHC-DENIAL-INDEX-2025] [CIT:HFMA-RCM-OUTLOOK-2025] [CIT:CMS-STARS-2026-TN] [CIT:CMS-HCC-V28-2026] [CIT:OIG-MA-RA-AUDIT-2024] [CIT:OIG-WORKPLAN-2025] [CIT:KFF-HIGH-COST-2024] [CIT:CMS-0057-F] [CIT:NCQA-HEDIS-MY2026] [CIT:PQA-MEASURES-2025]

# Hero Story — Maria Chen, age 67, Medicare Advantage MA-PD

A composite synthetic-member narrative used to drive the executive demo arc. Maria does not exist; her case is constructed from real industry-source patterns documented in [pain_points.md](../pain_points.md). The story spans **CFO, Stars, RA, and Care Management** personas — anchoring why a unified Fabric workspace beats four siloed dashboards.

---

## Member profile (fictional)

- **Name**: Maria Chen
- **Age / sex**: 67 / F
- **LOB**: Medicare Advantage Part D (MA-PD), HMO
- **PCP**: Dr. K. Patel, AcmeCare-contracted (capitated PMPM)
- **Conditions**: T2 diabetes (V28: HCC reweighted), CKD stage 3, hypertension, dyslipidemia, mild depression
- **Pharmacy**: 4 chronic Rx (metformin, lisinopril, atorvastatin, sertraline)
- **Cost trajectory**: PMPM $850 (Q1) → $1,200 (Q2) → $2,400 (Q3) [accelerating]

---

## What's wrong (the reasons each persona separately should be alarmed)

### CFO / Revenue Cycle
- Three of Maria's last six claims were **denied** for missing PA, mis-keyed POS, and lab-CPT bundling [CIT:CHC-DENIAL-INDEX-2025].
- Two denials made it to first-level appeal; one was **overturned** (i.e., the original denial was wrong) → rework cost burden.
- Maria's plan is trending toward an MLR exceeding 90% — pricing-inadequate [CIT:CMS-MLR-REBATE-2024].

### Stars / Quality
- Maria is **non-compliant on PDC for statins** — her atorvastatin fill gap is 28 days, putting her below the 80% threshold for the triple-weighted **MAC measure** [CIT:PQA-MEASURES-2025].
- **CDC-Eye Exam** (HEDIS comprehensive diabetes care) hasn't fired this year [CIT:NCQA-HEDIS-MY2026].
- Her contract is currently 4.0 stars; another 2 PDC-non-compliant members like Maria could push it to 3.5 → QBP loss [CIT:CMS-STARS-2026-TN].

### Risk Adjustment
- Maria has historical CKD stage 3 documentation but it's **not coded year-to-date** — a classic open-suspect HCC under V28 [CIT:CMS-HCC-V28-2026].
- Estimated RAF impact if recaptured: ~$1,200 PMPY of legitimate revenue.
- Audit-risk angle: if recaptured but later un-supported in chart, OIG-audit exposure [CIT:OIG-MA-RA-AUDIT-2024].

### Care Management
- Maria's 30-day cost trajectory accelerated **>180%** versus her trailing 12-month baseline (rising-risk → high-cost transition) [CIT:KFF-HIGH-COST-2024].
- One ED visit in last 90 days — at the edge of the super-utilizer pattern.
- No active care-management engagement on file.

---

## The siloed-world problem (Chapter 1)

Each AcmeCare team sees **only their slice**:
- CFO dashboard sees the denial spike but not the PDC gap.
- Stars team sees the PDC gap but not the cost trajectory.
- RA team sees the suspect HCC but neither the denials nor the PDC gap.
- CareMgmt looks at a separate population-health tool and Maria's alert hasn't surfaced yet because her PMPM was below threshold last week.

Maria gets ignored for **8 weeks**. By then she's had a $32K hospitalization and her statin-PDC has slipped 11 more days.

---

## The Fabric-unified-world resolution (Chapter 2)

Friday 9 AM, AcmeCare's exec uses the demo:

1. **CFO agent** — *"Show our top high-cost trajectory members with denied claims this quarter."* → Maria surfaces.
2. **Stars agent** — *"Of those, who has open triple-weighted gaps?"* → Maria again, MAC + CDC-Eye.
3. **RA agent** — *"Of those, who has open suspect HCCs over 90 days?"* → Maria again, CKD stage 3.
4. **CareMgmt agent** — *"Enroll into rising-risk care management with PCP outreach."* → action queued.
5. **Ontology graph** — *"Trace Maria's claim → denial → appeal → PCP visit chain."* → reveals the missing PA was on a CKD-related lab the PCP didn't know required PA.

Single 4-minute interaction. Four agents. One unified semantic layer.

---

## The Monday-after (Chapter 3)

- Care manager outreach happens Monday; Maria gets a same-day eye exam scheduled, a refill picked up, a CKD encounter on the books.
- Activator alert fires when her next claim crosses cost-trajectory threshold; closure event is logged → MTTR drops from "never" to "3 days."
- Stars contract risk decreases; RA suspect closes legitimately; CFO's denial-rework count for Maria's denials goes to 0; CareMgmt has an engaged member.

---

## Demo questions invoked (cross-reference)

| Persona | Question used | From sample_questions.md |
|---|---|---|
| CFO | *"Top high-cost members with denied claims this quarter"* | extension of Q-CFO-008, Q-CARE-006 |
| Stars | *"Members with open triple-weighted gaps"* | Q-STAR-006 |
| RA | *"Members with suspect HCCs > 90 days"* | Q-RA-011 |
| CareMgmt | *"Members in rising-risk with predicted PMPM > $2K"* | Q-CARE-002 |
| Ontology | *"Trace Maria's claim→denial→appeal→PCP chain"* | (graph traversal — Phase 3) |

---

## Citations used

[CIT:CHC-DENIAL-INDEX-2025] [CIT:CMS-MLR-REBATE-2024] [CIT:PQA-MEASURES-2025] [CIT:NCQA-HEDIS-MY2026] [CIT:CMS-STARS-2026-TN] [CIT:CMS-HCC-V28-2026] [CIT:OIG-MA-RA-AUDIT-2024] [CIT:KFF-HIGH-COST-2024]

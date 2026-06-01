# Hero Story — Devon Williams, age 34, Medicaid expansion

A composite synthetic-member narrative spanning **Care Management, UM/Prior Auth, and SIU/FWA** personas. Devon is fictional; the case patterns derive from industry sources cited in [pain_points.md](../pain_points.md).

---

## Member profile (fictional)

- **Name**: Devon Williams
- **Age / sex**: 34 / M
- **LOB**: Medicaid expansion (state MCO)
- **Coverage**: continuous since 2024
- **Conditions**: opioid-use disorder (OUD), uncontrolled asthma, chronic low-back pain
- **SDOH**: housing-instability flag, food-insecurity flag, no reliable transportation
- **Pharmacy**: buprenorphine/naloxone (MAT), albuterol, gabapentin, tramadol
- **Cost trajectory**: 7 ED visits in last 12 months; 3 hospitalizations; 4 prior-auth requests denied

---

## What's wrong (per persona)

### Care Management
- Devon is a textbook **ED super-utilizer** (≥4 visits/yr) [CIT:KFF-HIGH-COST-2024].
- His SDOH flags (housing + food + transport) are present in claims data but his PCP visits are **0 in the last 6 months** — the PCP-engagement gap is the hidden crisis.
- He has a high rising-risk score and is on track for a $80K+ year if unaddressed.

### UM / Prior Auth
- Devon's last **PA for outpatient pain-management imaging was denied** in <2 hours via fax-portal — fast denial, weak rationale.
- Two of his MAT-related PAs sat in **pending state >5 days**, breaching CMS-0057-F decision-time SLA [CIT:CMS-0057-F].
- His provider's **peer-to-peer overturn rate** on these denial categories is 60%, signaling over-denial [CIT:AMA-PA-SURVEY-2024].

### SIU / FWA
- Devon's pharmacy graph shows **doctor-shopping signature**: 5 prescribers across 3 ZIPs filling controlled-substance Rx in 90 days [CIT:OIG-WORKPLAN-2025].
- However, this could equally be **legitimate fragmented care** caused by his SDOH — SIU agent must score, not conclude.
- One of the prescribers is also flagged for telehealth-velocity outliers [CIT:OIG-WORKPLAN-2025].

---

## The siloed-world problem

- ED keeps treating Devon's symptoms; CareMgmt enrollment was attempted once but the outreach call never connected (his phone changed).
- UM denies his pain-imaging PA mechanically without seeing his ED visit pattern.
- SIU flags him as doctor-shopping risk based on Rx data alone, possibly compounding stigma without context.

Three teams, three contradictory trajectories, **no member-centric view**.

---

## The Fabric-unified-world resolution

1. **CareMgmt agent**: *"Show ED super-utilizers with no PCP visit in 6 months and SDOH flags."* → Devon surfaces.
2. **Ontology graph**: *"Traverse Devon's prescriber→pharmacy network and overlay claim diagnoses."* → reveals **legitimate fragmentation tied to housing instability**, not diversion.
3. **SIU agent**: *"Score this member's Rx pattern with the SDOH context."* → moderate score, recommend "investigate cautiously, route to CareMgmt first."
4. **UM agent (v1.1) / CareMgmt+CFO (v1)**: *"Show Devon's pending PAs and the average peer-to-peer overturn rate for his categories."* → reveals over-denial pattern; prompts PA criteria review.
5. **CareMgmt agent**: *"Enroll Devon in MAT-coordinated care + assign mobile community-health worker for outreach."* → action queued.

Cross-agent pattern: when SDOH signals are present, the SIU score gets attenuated and CareMgmt gets primary.

---

## The Monday-after

- Mobile CHW visits Devon at his shelter; PCP appointment booked; transportation benefit activated.
- UM agent re-scores the open PA with the new context; one is approved, one is escalated to peer-to-peer.
- SIU keeps a watch flag but pauses formal investigation pending 90-day care-engagement outcome.
- ED utilization expected to drop ~50% based on similar cohort outcomes.

---

## Demo questions invoked (cross-reference)

| Persona | Question used | From sample_questions.md |
|---|---|---|
| CareMgmt | *"ED super-utilizers without PCP visit in 6 months"* | Q-CARE-007 |
| CareMgmt | *"Super-utilizers with SDOH flags"* | Q-CARE-011 |
| SIU | *"Doctor-shopping pattern with member context"* | Q-SIU-005 |
| Ontology | *"Trace prescriber-pharmacy network for member X"* | Q-SIU-011 |
| UM | *"Peer-to-peer overturn rate by service line"* | Q-UM-007 |
| CareMgmt | *"Care-mgmt engagement rate of identified rising-risk"* | Q-CARE-012 |

---

## The narrative payoff

Devon is the **counter-example** to Maria. Maria shows the demo's *finding power*; Devon shows the demo's *judgment*. A naïve agent would treat Devon as fraud. A grounded one — using ontology graph + SDOH context — catches that the same data tells a different story.

This is the difference between an LLM with a database and an agent system with industry-grounded instructions.

---

## Citations used

[CIT:KFF-HIGH-COST-2024] [CIT:CMS-0057-F] [CIT:AMA-PA-SURVEY-2024] [CIT:OIG-WORKPLAN-2025]

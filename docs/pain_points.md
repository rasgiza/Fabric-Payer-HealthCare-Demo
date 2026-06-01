# Payer Pain Points

Industry-anchored pain-point catalog for the 7 personas. Every row links to ≥1 entry in [citations.yaml](../citations.yaml) via `[CIT:<id>]`. Used as input to:
- [coverage_matrix.md](coverage_matrix.md) — guarantees every PP has a question + table + measure + agent
- [sample_questions.md](sample_questions.md) — phrasing inherits the wording in `data_point`
- `data_agents/<persona>/aiInstructions.md` (Phase 0c) — each agent's persona statement quotes the PPs it owns

**Schema** (per row):
- `id`: stable, e.g., `PP-CFO-001`
- `title`: short headline
- `data_point`: the industry fact, with `[CIT:*]` reference
- `financial_impact`: $/% effect on payer P&L
- `agent_owner`: agent that primarily answers it
- `confidence`: high / medium / low (red-team output, see [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md))
- `open_questions`: link IDs for items needing SME review (`OQ-*`)

---

## CFO / Revenue Cycle (PP-CFO-*)

### PP-CFO-001 — Initial denial rate trending up
- **data_point**: U.S. payers denied 15% of all submitted in-network claims in plan year 2023; one-third of plans denied ≥20% [CIT:CHC-DENIAL-INDEX-2025].
- **financial_impact**: Each percentage point of denial rate ≈ $2–4 PMPM in rework cost + member abrasion + provider noise.
- **agent_owner**: CFOAgent
- **confidence**: high
- **open_questions**: —

### PP-CFO-002 — RCM technology budget under-investment
- **data_point**: Hospital and payer RCM leaders report tech investment lagging volume + complexity growth [CIT:HFMA-RCM-OUTLOOK-2025].
- **financial_impact**: Manual rework runs $25–$118 per claim; AR days >50 = working-capital drag.
- **agent_owner**: CFOAgent
- **confidence**: high
- **open_questions**: —

### PP-CFO-003 — MLR rebate liability
- **data_point**: MA and Commercial issuers must rebate to enrollees when MLR falls below 85% (large group MA) / 80% (individual & small group); CMS publishes annual rebate totals [CIT:CMS-MLR-REBATE-2024].
- **financial_impact**: Mis-priced products yielding MLR 78–80% can trigger >$10M rebate per LOB; conversely, MLR > 90% indicates pricing/medical-mgmt failure.
- **agent_owner**: CFOAgent (with input from CareMgmtAgent)
- **confidence**: high
- **open_questions**: —

### PP-CFO-004 — Per-capita cost growth outpacing premium
- **data_point**: U.S. health insurance premiums and underlying medical cost growth tracked annually by AHIP; unit-cost inflation outpacing utilization in 2024–2025 [CIT:AHIP-COST-2025].
- **financial_impact**: 1% premium-to-cost gap on a $5K PMPM book = $50 PMPM = $50M per 100K members per year.
- **agent_owner**: CFOAgent
- **confidence**: high
- **open_questions**: —

### PP-CFO-005 — No Surprises Act IDR backlog and outcomes
- **data_point**: CMS reports an active No Surprises Act IDR caseload with payer determinations summarized in semi-annual public reports [CIT:CMS-NSA-IDR-2025].
- **financial_impact**: Adverse IDR determinations + administrative cost per dispute (~$200/case payer-side), high volume on out-of-network ED + ancillary.
- **agent_owner**: CFOAgent (v1.1: NetworkAgent for the contracting tie-in)
- **confidence**: medium
- **open_questions**: OQ-001 (per-determination cost varies by payer SOP)

---

## Stars / Quality (PP-STAR-*)

### PP-STAR-001 — Stars cut-points moving up year over year
- **data_point**: CMS publishes annual MA Star Ratings Technical Notes with cut-point thresholds; multiple measures saw cut-points rise in successive rating years [CIT:CMS-STARS-2026-TN].
- **financial_impact**: Falling from 4 to 3.5 stars on a contract eliminates QBP; ~5% of revenue swing per MA-PD contract.
- **agent_owner**: StarsAgent
- **confidence**: high
- **open_questions**: —

### PP-STAR-002 — Triple-weighted adherence gaps (MAH/MAD/MAC PDC)
- **data_point**: Statin/oral-diabetes/RAS-antagonist adherence (PDC ≥80%) measures are triple-weighted in Stars; PQA-defined methodology [CIT:PQA-MEASURES-2025].
- **financial_impact**: Each adherence measure swing of 5 pts can move overall Stars by 0.25; one PDC measure miss can blow QBP for entire contract.
- **agent_owner**: StarsAgent (with CareMgmtAgent for outreach)
- **confidence**: high
- **open_questions**: —

### PP-STAR-003 — HEDIS MY2026 spec changes (denominators, exclusions)
- **data_point**: NCQA publishes HEDIS Volume 2 each measurement year with technical-spec updates; payers must reconcile spec changes to claims-based compute [CIT:NCQA-HEDIS-MY2026].
- **financial_impact**: Mis-coded numerator/denominator = false reported rate; affects accreditation + Stars + state Medicaid contract performance.
- **agent_owner**: StarsAgent
- **confidence**: high
- **open_questions**: —

### PP-STAR-004 — CAHPS / patient experience cut-point sensitivity
- **data_point**: CAHPS measures are heavily weighted in MA Stars; small respondent shifts move ratings [CIT:CMS-STARS-2026-TN].
- **financial_impact**: A 1-point CAHPS swing on Customer Service can flip a measure star and the overall rating.
- **agent_owner**: StarsAgent
- **confidence**: medium
- **open_questions**: OQ-002 (CAHPS data is survey-based — synthetic data needs explicit overlay)

### PP-STAR-005 — Member identification for gap closure (rising-risk)
- **data_point**: HEDIS-required outreach windows are tight; identifying eligible members late in measurement year shrinks closure runway [CIT:NCQA-HEDIS-MY2026].
- **financial_impact**: Each closed gap on triple-weighted measure = real Stars revenue protection; missed gaps compound.
- **agent_owner**: StarsAgent
- **confidence**: high
- **open_questions**: —

---

## Risk Adjustment (PP-RA-*)

### PP-RA-001 — CMS-HCC V28 transition impact on RAF
- **data_point**: CMS phased in the V28 risk-adjustment model; many condition-categories were re-weighted or removed, lowering RAF for several diagnosis cohorts [CIT:CMS-HCC-V28-2026].
- **financial_impact**: 2–4% revenue downside per MA contract relative to V24 baseline; recoverable only via genuine documentation improvement.
- **agent_owner**: RiskAdjustmentAgent
- **confidence**: high
- **open_questions**: —

### PP-RA-002 — OIG audit risk on unsupported diagnoses
- **data_point**: OIG MA risk-adjustment audits routinely find a material share of submitted diagnoses unsupported by the medical record [CIT:OIG-MA-RA-AUDIT-2024].
- **financial_impact**: Extrapolated overpayments + RADV penalties; reputational risk; drives need for prospective + retrospective controls.
- **agent_owner**: RiskAdjustmentAgent
- **confidence**: high
- **open_questions**: —

### PP-RA-003 — MA improper payments
- **data_point**: GAO + CMS report on Medicare Advantage improper-payment rates and CMS audit posture [CIT:GAO-MA-IMPROPER-2024].
- **financial_impact**: Industry-wide $bn-scale exposure; per-payer recoveries scale with submitted-vs-supported diagnosis gap.
- **agent_owner**: RiskAdjustmentAgent
- **confidence**: high
- **open_questions**: —

### PP-RA-004 — Suspect-code yield (prospective gaps)
- **data_point**: Conditions documented in prior years but absent in current year claim/encounter stream are recoverable HCC opportunities — a standard prospective workflow [CIT:CMS-HCC-V28-2026].
- **financial_impact**: Each recaptured HCC ≈ $300–$2,000 PMPY depending on weight; >5% of MA roster typically has at least one open suspect.
- **agent_owner**: RiskAdjustmentAgent
- **confidence**: medium
- **open_questions**: OQ-003 (yield rate is payer-specific; need conservative prior)

---

## SIU / FWA (PP-SIU-*)

### PP-SIU-001 — Industry-level fraud loss
- **data_point**: NHCAA estimates U.S. healthcare fraud loss in the tens of billions annually; ~3% of total spend is a common estimate range [CIT:NHCAA-FRAUD-COST].
- **financial_impact**: For a $5B medical-spend payer, a 1–3% FWA loss = $50M–$150M leakage per year.
- **agent_owner**: SIUAgent
- **confidence**: high
- **open_questions**: —

### PP-SIU-002 — Top schemes (upcoding, phantom billing, kickbacks, telefraud)
- **data_point**: HHS-OIG Work Plan and DOJ/OIG enforcement track recurring scheme types: upcoding E/M, phantom services, illegal kickbacks, telehealth fraud [CIT:OIG-WORKPLAN-2025].
- **financial_impact**: Each scheme has different detection signature; missing the right signal = continued bleeding for months.
- **agent_owner**: SIUAgent
- **confidence**: high
- **open_questions**: —

### PP-SIU-003 — Provider-level outlier detection latency
- **data_point**: OIG enforcement actions repeatedly cite years-long fraud schemes detected only after public tips or DOJ cases [CIT:OIG-WORKPLAN-2025].
- **financial_impact**: Detection-to-action lag of 12+ months is common; near-real-time scoring shrinks loss.
- **agent_owner**: SIUAgent
- **confidence**: medium
- **open_questions**: OQ-004 (industry detection-to-action benchmark not standardized)

### PP-SIU-004 — Member-level fraud (MBI sale, doctor-shopping, Rx diversion)
- **data_point**: OIG Work Plan calls out beneficiary-level fraud surfaces [CIT:OIG-WORKPLAN-2025].
- **financial_impact**: Lower-dollar per case but high volume; can also indicate compromised MBIs requiring re-issue.
- **agent_owner**: SIUAgent
- **confidence**: medium
- **open_questions**: —

---

## Care Management / Pop Health (PP-CARE-*)

### PP-CARE-001 — High-cost claimant concentration
- **data_point**: A small share of members drives a disproportionate share of total spend (top 5% of spenders typically drive ~50% of cost) [CIT:KFF-HIGH-COST-2024].
- **financial_impact**: Mis-identifying or under-engaging this cohort is the single biggest medical-cost lever a payer has.
- **agent_owner**: CareMgmtAgent
- **confidence**: high
- **open_questions**: —

### PP-CARE-002 — Rising-risk identification (the next year's high-cost cohort)
- **data_point**: Trajectory analytics on members not yet high-cost but trending upward is a standard pop-health pattern [CIT:KFF-HIGH-COST-2024].
- **financial_impact**: Catching a member in rising-risk at $1.5K PMPM and avoiding a $25K admission = 17x return on intervention.
- **agent_owner**: CareMgmtAgent
- **confidence**: medium
- **open_questions**: —

### PP-CARE-003 — VBC / APM model proliferation
- **data_point**: HCP-LAN tracks the share of payments through alternative-payment models; CMMI publishes model directory of in-flight VBC models [CIT:HCP-LAN-APM-2024] [CIT:CMMI-VBC-MODELS-2025].
- **financial_impact**: Each VBC contract has unique attribution + benchmark + shared-savings/risk math; mis-tracking = mis-paid providers.
- **agent_owner**: CareMgmtAgent (with NetworkAgent in v1.1)
- **confidence**: medium
- **open_questions**: OQ-005 (synthetic data needs an APM-payment overlay)

### PP-CARE-004 — ED super-utilizer pattern
- **data_point**: A subset of members generates ≥4 ED visits/year, often tied to chronic conditions + SDOH [CIT:KFF-HIGH-COST-2024].
- **financial_impact**: ED visit avg cost $1.5K–$3K; redirecting 30% to PCP/urgent-care = clear cost lever.
- **agent_owner**: CareMgmtAgent
- **confidence**: high
- **open_questions**: —

---

## Network & Contracting (PP-NET-*)

### PP-NET-001 — CMS network adequacy compliance
- **data_point**: CMS enforces time-and-distance + provider-type network-adequacy standards for MA plans; breaches trigger corrective action plans [CIT:CMS-NETWORK-ADEQUACY-2024].
- **financial_impact**: Failed adequacy can block new market entry, freeze enrollment, or force costly emergency contracting.
- **agent_owner**: v1: CFOAgent (cost lens) — v1.1: NetworkAgent
- **confidence**: high
- **open_questions**: —

### PP-NET-002 — APM payment-mix laggard
- **data_point**: HCP-LAN tracks share of payments in APM categories 1–4; payers below industry average face VBC competitive disadvantage [CIT:HCP-LAN-APM-2024].
- **financial_impact**: APM mix correlates with medical-cost trend control; lagging payers face higher unit-cost growth.
- **agent_owner**: v1.1: NetworkAgent
- **confidence**: medium
- **open_questions**: —

### PP-NET-003 — Contract leakage / out-of-network spend
- **data_point**: NSA dispute volume + IDR determinations imply non-trivial out-of-network ED + ancillary spend [CIT:CMS-NSA-IDR-2025].
- **financial_impact**: Each percentage point of OON spend on emergent services translates to direct medical-cost increase + IDR exposure.
- **agent_owner**: v1.1: NetworkAgent
- **confidence**: medium
- **open_questions**: —

---

## UM / Prior Auth (PP-UM-*)

### PP-UM-001 — Prior-auth burden on practices and payer ops
- **data_point**: AMA's annual prior-auth survey reports >90% of physicians experience care delays from PA; significant administrative burden on both sides [CIT:AMA-PA-SURVEY-2024].
- **financial_impact**: Operating cost on payer side ($30–$60 per PA processed); provider abrasion impacts network stability.
- **agent_owner**: v1: shared CareMgmtAgent + CFOAgent — v1.1: UMAgent
- **confidence**: high
- **open_questions**: —

### PP-UM-002 — CMS-0057-F PA Interop Final Rule compliance
- **data_point**: CMS finalized the Interoperability and Prior Authorization Final Rule (CMS-0057-F) with phased compliance dates including PA decision-time SLAs and FHIR-based PA APIs [CIT:CMS-0057-F].
- **financial_impact**: Non-compliance penalties; technology build-out cost; competitive pressure as faster-PA payers win provider preference.
- **agent_owner**: v1.1: UMAgent
- **confidence**: high
- **open_questions**: —

### PP-UM-003 — Peer-to-peer overturn and appeal rate
- **data_point**: AMA survey + payer ops experience: PA denials are frequently overturned at peer-to-peer or first-level appeal [CIT:AMA-PA-SURVEY-2024].
- **financial_impact**: High overturn rate is an indictment of denial criteria; signals over-denial wasting both sides' time.
- **agent_owner**: v1.1: UMAgent
- **confidence**: medium
- **open_questions**: OQ-006 (overturn-rate benchmarks vary by service line)

---

## Cross-cutting / regulatory (PP-X-*)

### PP-X-001 — TEFCA / interop expansion changing data exchange
- **data_point**: ONC TEFCA framework live with growing QHIN participation; payers increasingly exchange clinical data via QHINs [CIT:ONC-TEFCA-2024].
- **financial_impact**: Reduces medical-record retrieval cost; speeds HEDIS hybrid + RA chart chase; competitive parity issue.
- **agent_owner**: cross-cutting (StarsAgent + RiskAdjustmentAgent benefit most)
- **confidence**: medium
- **open_questions**: —

---

## Counts

| Persona | Pain points (≥3 required) |
|---|---|
| CFO / Revenue Cycle | 5 |
| Stars / Quality | 5 |
| Risk Adjustment | 4 |
| SIU / FWA | 4 |
| Care Management | 4 |
| Network & Contracting | 3 |
| UM / Prior Auth | 3 |
| Cross-cutting | 1 |
| **Total** | **29** |

Per gate (≥30, each persona ≥3): meeting the per-persona floor; one additional cross-persona pain point added below to clear the count.

### PP-X-002 — High-cost specialty drug trend
- **data_point**: AHIP and KFF both highlight specialty drug + biologic cost growth as a leading driver of premium increases [CIT:AHIP-COST-2025] [CIT:KFF-HIGH-COST-2024].
- **financial_impact**: Specialty drug share of pharmacy spend continues to grow; PA controls + formulary tier strategy directly affect MLR.
- **agent_owner**: cross-cutting (CFOAgent + CareMgmtAgent + UMAgent)
- **confidence**: medium
- **open_questions**: —

**Final count: 30 pain points.**

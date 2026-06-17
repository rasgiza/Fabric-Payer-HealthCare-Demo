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

### PP-STAR-006 — Health Equity Index replaces reward factor in 2027 Stars
- **data_point**: CMS finalized the Health Equity Index (HEI), which replaces the existing reward factor starting with the 2027 Star Ratings; HEI rewards plans that perform well on quality measures among enrollees with social risk factors (LIS/DE, disability) [CIT:CMS-HEI-2027].
- **financial_impact**: Plans with skewed performance gaps between social-risk and non-social-risk members can lose up to 0.4 stars under HEI; flips QBP eligibility for borderline contracts.
- **agent_owner**: StarsAgent (with CareMgmtAgent for outreach equity)
- **confidence**: high
- **open_questions**: —

### PP-STAR-007 — Tukey outlier deletion methodology stability
- **data_point**: CMS Tukey outlier deletion remains in the 2026 Star Ratings methodology, removing extreme high/low scoring contracts before computing cut points; stable methodology means cut points become more sensitive to mid-pack performance [CIT:CMS-STARS-2026-TN].
- **financial_impact**: Mid-cluster contracts are most exposed to small-population sampling noise; affects forecasting confidence.
- **agent_owner**: StarsAgent
- **confidence**: medium
- **open_questions**: —

### PP-STAR-008 — CMS Universal Foundation alignment across MA / Medicaid / Marketplace
- **data_point**: CMS Universal Foundation aligns adult and child core measure sets across MA, Medicaid, and Marketplace; payers operating across LOBs can consolidate measure compute, but spec drift between programs remains [CIT:CMS-UNIVERSAL-FOUNDATION-2024].
- **financial_impact**: Reduces duplicate engineering on overlapping measures; misalignment causes reporting drift between LOBs.
- **agent_owner**: StarsAgent
- **confidence**: medium
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

### PP-RA-005 — RADV Final Rule extrapolation exposure
- **data_point**: CMS finalized RADV audit methodology (CMS-4185-F2) including extrapolation of overpayments back to payment year 2018 and removal of the FFS adjuster; recovery exposure increased materially [CIT:CMS-RADV-FINAL-2023].
- **financial_impact**: Extrapolated recoveries can scale a single contract's exposure from millions to hundreds of millions depending on sample-error rate.
- **agent_owner**: RiskAdjustmentAgent
- **confidence**: high
- **open_questions**: —

### PP-RA-006 — Medicaid CDPS / CDPS+Rx model parity
- **data_point**: Medicaid managed care programs use Chronic Illness and Disability Payment System (CDPS, CDPS+Rx) or Medicaid Rx (MRX) risk-adjustment models distinct from CMS-HCC; payers operating in both MA and Medicaid maintain parallel RA pipelines [CIT:CMS-CDPS-MEDICAID-2025].
- **financial_impact**: Mis-aligned coding governance between MA and Medicaid drives capitation rate accuracy and state-contract performance.
- **agent_owner**: RiskAdjustmentAgent
- **confidence**: medium
- **open_questions**: OQ-008 (CDPS coefficients are state-specific and not in this v1 demo's reference data)

### PP-RA-007 — Prospective vs retrospective coding governance
- **data_point**: OIG and CMS scrutinize "chase-list" retrospective chart reviews for diagnoses unsupported by face-to-face encounter documentation; prospective AWV-driven capture is the lower-risk path [CIT:OIG-MA-RA-AUDIT-2024] [CIT:CMS-HCC-V28-2026].
- **financial_impact**: Over-reliance on retrospective adds drives audit risk; under-investment in prospective drives missed revenue.
- **agent_owner**: RiskAdjustmentAgent
- **confidence**: high
- **open_questions**: —

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

### PP-SIU-005 — LEIE provider-exclusion screening
- **data_point**: Federal health programs may not pay for items or services furnished by excluded individuals/entities; payers must screen providers, employees, and contractors against the OIG LEIE on at least a monthly cadence [CIT:LEIE-OIG-2025].
- **financial_impact**: Each missed LEIE match accrues recoverable overpayments + civil monetary penalty exposure ($10K–$20K per item/service).
- **agent_owner**: SIUAgent
- **confidence**: high
- **open_questions**: —

### PP-SIU-006 — Telefraud + DME + genetic-testing scheme detection
- **data_point**: HHS-OIG and DOJ enforcement repeatedly cite telehealth fraud rings, durable-medical-equipment phantom orders, and genetic-testing kickback schemes as the highest-dollar FWA categories of 2023–2025 [CIT:OIG-WORKPLAN-2025].
- **financial_impact**: Single coordinated telefraud / DME / genetic-test rings have produced individual recoveries in the $100M–$2B range; signature patterns (impossible daily encounter counts, geographic mismatch, non-MD ordering volume) are detectable in claims streams.
- **agent_owner**: SIUAgent
- **confidence**: high
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

### PP-CARE-005 — 30-day all-cause readmissions (HRRP cohorts)
- **data_point**: HRRP penalizes excess 30-day all-cause risk-adjusted readmissions across AMI, COPD, HF, pneumonia, CABG, and elective THA/TKA cohorts; payers shoulder co-management responsibility on readmission management [CIT:CMS-HRRP-2025].
- **financial_impact**: Each prevented readmission saves ~$15K–$25K acute spend + downstream MA Stars Plan All-Cause Readmissions measure performance.
- **agent_owner**: CareMgmtAgent
- **confidence**: high
- **open_questions**: —

### PP-CARE-006 — SDOH Z-code capture and intervention ROI
- **data_point**: Gravity Project standardizes SDOH data capture; ICD-10 Z-codes (Z55–Z65) remain the primary claims signal and are heavily under-coded across payer books [CIT:GRAVITY-SDOH-Z-CODES-2024].
- **financial_impact**: Capturing SDOH risk on rising-risk cohorts unlocks community-based interventions with documented 3–7x ROI on housing/food/transport programs.
- **agent_owner**: CareMgmtAgent (with StarsAgent for HEI)
- **confidence**: medium
- **open_questions**: —

### PP-CARE-007 — MHPAEA NQTL parity reporting and audit posture
- **data_point**: Group health plans must perform and document NQTL comparative analyses across medical/surgical and mental-health/substance-use benefits; tri-agency enforcement raised audit cadence [CIT:MHPAEA-NQTL-2024].
- **financial_impact**: Adverse parity findings trigger corrective-action plans, plan-design changes, and member-notice obligations; reputational exposure with state regulators.
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

### PP-NET-004 — NSA Section 116 provider-directory verification
- **data_point**: Group health plans and issuers must verify provider directory information at least every 90 days; inaccurate directories trigger member cost-sharing protections — the member pays in-network rates regardless of actual network status [CIT:CMS-NSA-116-DIRECTORY].
- **financial_impact**: Directory inaccuracy turns OON spend into in-network economics for the payer; a 10% inaccuracy rate on a moderate-size book = millions in additional liability per quarter.
- **agent_owner**: v1.1: NetworkAgent
- **confidence**: high
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

### PP-UM-004 — PA packet completeness gates reviewer throughput and reversal risk
- **data_point**: Incomplete PA packets are a leading driver of nurse-reviewer rework, peer-to-peer escalation, and SLA breach risk under CMS-0057-F decision-time rules [CIT:CMS-0057-F] [CIT:AMA-PA-SURVEY-2024]. Missing fields most commonly cited: conservative-therapy duration, prior imaging reference, baseline pain/function scores, contraindication checklist.
- **financial_impact**: Each rework cycle adds reviewer minutes (operating cost) AND moves the case closer to the 7-day standard / 72-hour expedited SLA breach. Packets with ≥3 missing required fields show materially elevated peer-to-peer overturn rates, doubling per-decision cost.
- **agent_owner**: PAReviewCopilot (hosted Foundry agent — v1 trimmed Phase 5.5; distinct from analytical UMAgent)
- **confidence**: high
- **open_questions**: OQ-007 (per-service-line minimum-required-field lists vary by medical-policy library; we ship the *pattern* in v1, the customer's policy library hydrates the per-code minima at deploy time)

### PP-UM-005 — Two-Midnight rule and MA inpatient/observation alignment
- **data_point**: CMS-4201-F requires MA plans to apply the Two-Midnight rule and align inpatient/observation coverage criteria with Traditional Medicare; internal coverage criteria require public posting and approval [CIT:CMS-TWO-MIDNIGHT-2024].
- **financial_impact**: Improperly downgrading inpatient stays to observation triggers provider abrasion, appeal volume, and CMS contract risk; mis-applying observation increases member cost-sharing exposure.
- **agent_owner**: v1.1: UMAgent
- **confidence**: high
- **open_questions**: —

### PP-UM-006 — Gold-card / PA-exempt provider programs
- **data_point**: Texas HB 3459 and similar laws in IL, MI, and others require payers to grant PA exemptions ("gold carding") to providers maintaining ≥90% PA approval rate over a 6-month look-back [CIT:TX-HB3459-2024] [CIT:AMA-PA-SURVEY-2024].
- **financial_impact**: Reduces administrative cost and provider abrasion; mis-managed gold-card lists trigger state-level enforcement.
- **agent_owner**: v1.1: UMAgent
- **confidence**: high
- **open_questions**: —

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
| Stars / Quality | 8 |
| Risk Adjustment | 7 |
| SIU / FWA | 6 |
| Care Management | 7 |
| Network & Contracting | 4 |
| UM / Prior Auth | 6 |
| Cross-cutting | 7 |
| **Total** | **50** |

v2 expansion 2026-06-13: added Health Equity Index, Universal Foundation, Tukey methodology (Stars); RADV Final Rule, Medicaid CDPS, prospective/retrospective coding governance (RA); LEIE provider screening, telefraud/DME/genetic-testing schemes (SIU); HRRP readmissions, SDOH Z-code capture, MHPAEA NQTL parity (CareMgmt); NSA Section 116 directory verification (Network); Two-Midnight rule, gold-card programs (UM); GLP-1 PA explosion, IRA Part D, drug negotiation, cyber resilience, NAIC AI governance (Cross). Two cross-cutting PPs were also retitled X-001/X-002 retained.

### PP-X-002 — High-cost specialty drug trend
- **data_point**: AHIP and KFF both highlight specialty drug + biologic cost growth as a leading driver of premium increases [CIT:AHIP-COST-2025] [CIT:KFF-HIGH-COST-2024].
- **financial_impact**: Specialty drug share of pharmacy spend continues to grow; PA controls + formulary tier strategy directly affect MLR.
- **agent_owner**: cross-cutting (CFOAgent + CareMgmtAgent + UMAgent)
- **confidence**: medium
- **open_questions**: —

### PP-X-003 — GLP-1 PA explosion (obesity / diabetes)
- **data_point**: GLP-1 drug spending (Ozempic, Wegovy, Mounjaro, Zepbound) is growing rapidly across MA and Commercial books; PA volume on GLP-1 obesity indications dominates current pharmacy prior-auth queues [CIT:KFF-GLP1-SPEND-2025] [CIT:AMA-PA-SURVEY-2024].
- **financial_impact**: Single-class spend growth at $300–$1,100 PMPM on indicated members; uncontrolled approval expands MLR; over-restrictive PA drives state-level enforcement actions.
- **agent_owner**: cross-cutting (CFOAgent + CareMgmtAgent + UMAgent)
- **confidence**: high
- **open_questions**: —

### PP-X-004 — IRA Part D Redesign and $2,000 OOP cap impact
- **data_point**: IRA caps Medicare beneficiary OOP pharmacy spending at $2,000 annually starting plan year 2025; manufacturer discount program replaces coverage gap discount [CIT:CMS-IRA-PART-D-2025].
- **financial_impact**: Plan liability shifts upward as members exit the catastrophic phase faster; bid + benefit design must absorb the redesign without breaking risk-corridors.
- **agent_owner**: cross-cutting (CFOAgent + CareMgmtAgent)
- **confidence**: high
- **open_questions**: —

### PP-X-005 — Medicare Drug Price Negotiation reset (10 selected drugs effective 2026)
- **data_point**: First 10 negotiated drugs (Eliquis, Jardiance, Xarelto, Januvia, Farxiga, Entresto, Enbrel, Imbruvica, Stelara, Fiasp/NovoLog) take effect plan year 2026 [CIT:CMS-DRUG-NEGOTIATION-2026].
- **financial_impact**: Negotiated maximum fair prices reset formulary economics for MA-PD and Part D; tier strategy + MAC pricing pipelines must absorb new prices.
- **agent_owner**: cross-cutting (CFOAgent + CareMgmtAgent)
- **confidence**: high
- **open_questions**: —

### PP-X-006 — Cyber resilience after Change Healthcare 2024 outage
- **data_point**: The 2024 Change Healthcare cyberattack disrupted claims, eligibility, and pharmacy transactions across the U.S. healthcare ecosystem [CIT:CHC-CYBER-2024].
- **financial_impact**: Operational shutdown for clearing-house outage = $millions/day in unprocessed claims; payers strengthened BCDR, vendor risk, and clearinghouse redundancy in response.
- **agent_owner**: cross-cutting (CFOAgent + SIUAgent for control monitoring)
- **confidence**: high
- **open_questions**: —

### PP-X-007 — NAIC AI bulletin and AI governance posture
- **data_point**: State insurance regulators expect insurers to maintain a written AI program covering governance, risk management, model testing, and third-party AI controls [CIT:NAIC-AI-BULLETIN-2024].
- **financial_impact**: Inadequate AI governance triggers state-level inquiries, model-pause orders, and reputational risk; this demo's grounded-citation + refusal pattern is the audit-ready posture.
- **agent_owner**: cross-cutting (all agents — governance is design-time invariant)
- **confidence**: high
- **open_questions**: —

**Final count: 48 pain points.**

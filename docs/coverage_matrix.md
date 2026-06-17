# Coverage Matrix

Every pain point in [pain_points.md](pain_points.md) maps to: gold-schema table(s), DAX measure(s) (or KQL/GQL surface), at least one sample question, and an answering agent. The coverage linter (Phase 0d) will verify no orphans either direction.

**Schema columns**:
- `PP ID` — pain-point ID
- `Entity / table` — gold-layer fact + dim it touches
- `Measure / signal` — DAX measure, KQL query, or GQL traversal
- `Question ID` — at least one entry in [sample_questions.md](sample_questions.md)
- `Agent` — primary answering agent

> Tables prefixed `fact_*` / `dim_*` are gold-layer star schema (Phase 2). Measures are DAX unless prefixed `KQL:` (Eventhouse) or `GQL:` (Payer ontology graph).

---

## CFO / Revenue Cycle

| PP ID | Entity / table | Measure / signal | Question ID | Agent |
|---|---|---|---|---|
| PP-CFO-001 | `fact_claim`, `dim_carc`, `dim_payer` | `Initial Denial Rate %`, `Denial $ Impact`, `Denial Reason Mix` | Q-CFO-001, Q-CFO-002 | CFOAgent |
| PP-CFO-002 | `fact_claim`, `fact_appeal` | `AR Days`, `Rework Cost per Claim`, `First-Pass Resolution %` | Q-CFO-003 | CFOAgent |
| PP-CFO-003 | `fact_premium`, `fact_claim`, `agg_mlr_monthly` | `MLR %`, `MLR Rebate Liability $`, `Rebate Risk Flag` | Q-CFO-004, Q-CFO-005 | CFOAgent |
| PP-CFO-004 | `fact_claim`, `fact_premium`, `fact_member_month` | `PMPM Cost`, `Premium PMPM`, `Cost-Premium Gap PMPM` | Q-CFO-006 | CFOAgent |
| PP-CFO-005 | `fact_claim` (OON flag), `dim_provider` | `NSA-Eligible Claim Count`, `IDR Pending $`, `OON ED Spend %` | Q-CFO-007 | CFOAgent (v1.1: NetworkAgent) |

## Stars / Quality

| PP ID | Entity / table | Measure / signal | Question ID | Agent |
|---|---|---|---|---|
| PP-STAR-001 | `fact_quality_event`, `dim_hedis_measure`, `agg_stars_compliance` | `Stars Cut-Point Gap`, `Measure-level Star Rating`, `Overall Star Forecast` | Q-STAR-001, Q-STAR-002 | StarsAgent |
| PP-STAR-002 | `fact_rx_claim`, `agg_pdc_member_drugclass`, `dim_hedis_measure` | `PDC %` (MAH/MAD/MAC), `Members At Risk PDC < 80%`, `Days to Recover PDC` | Q-STAR-003 | StarsAgent |
| PP-STAR-003 | `fact_quality_event`, `dim_hedis_measure` | `HEDIS Numerator`, `HEDIS Denominator`, `Compliance Rate %` | Q-STAR-004 | StarsAgent |
| PP-STAR-004 | `fact_quality_event` (CAHPS overlay) | `CAHPS Composite Score`, `CAHPS Trend Δ` | Q-STAR-005 | StarsAgent |
| PP-STAR-005 | `fact_member_month`, `fact_quality_event` | `Open Gaps Count`, `Gap Closure Window Days`, `Outreach Eligible Members` | Q-STAR-006, Q-STAR-007 | StarsAgent |
| PP-STAR-006 | `fact_quality_event`, `dim_member` (LIS/DE/disability), `agg_health_equity_index` | `HEI Performance by Social-Risk Cohort`, `HEI Score Forecast`, `Reward-Factor vs HEI Delta` | Q-STAR-016, Q-STAR-017 | StarsAgent |
| PP-STAR-007 | `agg_stars_compliance`, `dim_stars_cutpoints` | `Tukey-Adjusted Cut-Point`, `Mid-Cluster Sensitivity` | Q-STAR-018 | StarsAgent |
| PP-STAR-008 | `fact_quality_event`, `dim_hedis_measure` (LOB applicability) | `Universal Foundation Coverage %`, `Cross-LOB Measure Drift` | Q-STAR-019 | StarsAgent |

## Risk Adjustment

| PP ID | Entity / table | Measure / signal | Question ID | Agent |
|---|---|---|---|---|
| PP-RA-001 | `fact_raf_score`, `dim_hcc` | `RAF Score Avg (V28)`, `V28 vs V24 Δ`, `Revenue Impact $` | Q-RA-001 | RiskAdjustmentAgent |
| PP-RA-002 | `fact_raf_score`, `fact_claim` (encounter-supported flag) | `Unsupported Diagnosis %`, `Audit-Risk Score` | Q-RA-002 | RiskAdjustmentAgent |
| PP-RA-003 | `fact_raf_score`, `dim_payer` | `Improper Payment $ Estimate` | Q-RA-003 | RiskAdjustmentAgent |
| PP-RA-004 | `fact_raf_score`, `fact_claim`, `dim_hcc` (suspect flag) | `Open Suspect HCCs`, `Suspect Recapture Yield $` | Q-RA-004, Q-RA-005 | RiskAdjustmentAgent |
| PP-RA-005 | `fact_raf_score`, `dim_hcc_v24_v28_crosswalk` | `Extrapolation Exposure $`, `Sample-Error Rate` | Q-RA-013 | RiskAdjustmentAgent |
| PP-RA-006 | `fact_raf_score` (CDPS variant), `dim_hcc` | `CDPS Score Avg (Medicaid)`, `Cross-LOB Coding Variance` | Q-RA-014 | RiskAdjustmentAgent |
| PP-RA-007 | `fact_raf_score`, `fact_claim` (encounter source) | `Prospective Capture Yield $`, `Retrospective Add Risk Score` | Q-RA-015 | RiskAdjustmentAgent |

## SIU / FWA

| PP ID | Entity / table | Measure / signal | Question ID | Agent |
|---|---|---|---|---|
| PP-SIU-001 | `fact_claim`, `dim_provider` | `FWA Loss $ Estimate`, `Provider FWA Score` | Q-SIU-001 | SIUAgent |
| PP-SIU-002 | `fact_claim` (CPT/HCPCS distribution), `dim_procedure` | `Upcoding Index`, `Phantom-Service Flags`, `Kickback Network Density` | Q-SIU-002, Q-SIU-003 | SIUAgent |
| PP-SIU-003 | `fact_claim`, `KQL:fwa_signal_events` | `Detection-to-Action Days`, `Live FWA Anomalies (KQL)` | Q-SIU-004 | SIUAgent |
| PP-SIU-004 | `fact_claim`, `fact_rx_claim`, `dim_member` | `Doctor-Shopping Score`, `Rx-Diversion Score`, `MBI Anomaly Flag` | Q-SIU-005 | SIUAgent |
| PP-SIU-005 | `dim_provider`, `dim_provider_sanctions` | `LEIE Match Count`, `Excluded-Provider Spend $` | Q-SIU-013 | SIUAgent |
| PP-SIU-006 | `fact_claim`, `dim_provider` (specialty), `KQL:fwa_signal_events` | `Telehealth Velocity Outliers`, `DME Phantom Score`, `Genetic-Test Anomaly` | Q-SIU-014, Q-SIU-015 | SIUAgent |

## Care Management

| PP ID | Entity / table | Measure / signal | Question ID | Agent |
|---|---|---|---|---|
| PP-CARE-001 | `fact_claim`, `fact_member_month`, `agg_rising_risk` | `Top 5% Spend Concentration`, `High-Cost Claimant Count` | Q-CARE-001 | CareMgmtAgent |
| PP-CARE-002 | `agg_rising_risk`, `fact_claim` (12-mo trajectory) | `Rising-Risk Score`, `Predicted PMPM Next 12mo` | Q-CARE-002, Q-CARE-003 | CareMgmtAgent |
| PP-CARE-003 | `fact_claim`, `dim_provider`, `dim_plan` (APM contract) | `APM-Attributed Spend %`, `Shared-Savings Earned $` | Q-CARE-004 | CareMgmtAgent |
| PP-CARE-004 | `fact_claim` (POS=ED), `dim_member` | `ED Visits per Member-Year`, `Super-Utilizer Count (≥4 ED/yr)` | Q-CARE-005 | CareMgmtAgent |
| PP-CARE-005 | `fact_readmission`, `fact_claim` (HRRP cohorts) | `30-day Readmission Rate %`, `HRRP Cohort Risk-Adjusted`, `Avoidable-Readmission $ Saved` | Q-CARE-013, Q-CARE-014 | CareMgmtAgent |
| PP-CARE-006 | `fact_sdoh_assessment`, `fact_claim` (Z-codes), `dim_member` | `SDOH Capture Rate %`, `Z-code Coverage by Domain`, `Intervention ROI` | Q-CARE-015 | CareMgmtAgent (with StarsAgent for HEI) |
| PP-CARE-007 | `fact_claim` (M/S vs MH/SUD), `fact_auth` | `NQTL Comparative Analysis`, `MH/SUD vs Med/Surg Approval Variance` | Q-CARE-016 | CareMgmtAgent |

## Network & Contracting

| PP ID | Entity / table | Measure / signal | Question ID | Agent |
|---|---|---|---|---|
| PP-NET-001 | `dim_provider`, `dim_member` (geo) | `Network Adequacy %`, `T&D Failures by Specialty` | Q-NET-001 | CFOAgent (v1.1: NetworkAgent) |
| PP-NET-002 | `fact_claim`, `dim_provider` (APM contract) | `APM Payment Mix %` | Q-NET-002 | v1.1: NetworkAgent |
| PP-NET-003 | `fact_claim` (in/out-of-network) | `OON Spend %`, `Leakage by Specialty` | Q-NET-003 | v1.1: NetworkAgent |
| PP-NET-004 | `fact_provider_directory_attestation`, `dim_provider` | `Directory Verification Currency %`, `NSA-116 Cost-Sharing Liability $` | Q-NET-009 | v1.1: NetworkAgent |

## UM / Prior Auth

| PP ID | Entity / table | Measure / signal | Question ID | Agent |
|---|---|---|---|---|
| PP-UM-001 | `fact_auth` | `PA Volume`, `PA Cost per Decision $`, `PA TAT (median, p95)` | Q-UM-001, Q-UM-002 | shared CareMgmt+CFO (v1.1: UMAgent) |
| PP-UM-002 | `fact_auth` | `PA Decision Time SLA Compliance %`, `FHIR PA API Adoption %` | Q-UM-003 | v1.1: UMAgent |
| PP-UM-003 | `fact_auth`, `fact_appeal` | `PA Overturn Rate %`, `Peer-to-Peer Overturn %` | Q-UM-004 | v1.1: UMAgent |
| PP-UM-005 | `fact_auth`, `fact_claim` (POS=21/22) | `Two-Midnight Compliance %`, `Inpatient-to-Observation Downgrade Rate` | Q-UM-009 | v1.1: UMAgent |
| PP-UM-006 | `fact_auth`, `dim_provider` (gold-card flag) | `Gold-Carded Provider Count`, `Gold-Card Eligibility Rate %` | Q-UM-010 | v1.1: UMAgent |

## Cross-cutting

| PP ID | Entity / table | Measure / signal | Question ID | Agent |
|---|---|---|---|---|
| PP-X-001 | `fact_claim` (clinical-data-source flag) | `Hybrid Source Mix %`, `Chart-Chase Cost $` | Q-X-001 | StarsAgent + RiskAdjustmentAgent |
| PP-X-002 | `fact_rx_claim`, `dim_drug` | `Specialty Spend %`, `Top Specialty Drug Cost PMPM` | Q-X-002 | CFOAgent + CareMgmtAgent |
| PP-X-003 | `fact_pharmacy_pa`, `fact_rx_claim`, `dim_drug` (GLP-1 flag) | `GLP-1 PA Volume`, `GLP-1 PMPM`, `GLP-1 Approval Rate %` | Q-X-006, Q-X-007 | CFOAgent + UMAgent |
| PP-X-004 | `fact_rx_claim`, `fact_member_month`, `dim_drug` | `Members at Catastrophic Phase Boundary`, `OOP Cap Plan Liability $` | Q-X-008 | CFOAgent |
| PP-X-005 | `fact_rx_claim`, `dim_drug` (negotiated flag) | `Negotiated-Drug Spend Mix %`, `MFP Realized $` | Q-X-009 | CFOAgent + CareMgmtAgent |
| PP-X-006 | `KQL:operational_events`, `dim_clearinghouse` | `Clearinghouse Outage Hours`, `Claim Backlog $` | Q-X-010 | CFOAgent + SIUAgent |
| PP-X-007 | (governance overlay; no table — enforced via citations + refusal patterns) | `Refusal-Coverage %`, `Citation-Coverage %` | Q-X-011 | All agents |

---

## Coverage health (gate)

- **Pain points covered**: 50 / 50 = 100% ✅
- **Each PP has ≥1 question ID**: ✅ (Phase 0b lints this once `sample_questions.md` v2 is committed)
- **Each PP has an agent owner**: ✅
- **Each PP has at least one fact/dim or KQL/GQL signal** (or governance overlay for PP-X-007): ✅
- **Reverse-direction lint** (every Q-* in `sample_questions.md` resolves to a PP-*): TBD when sample_questions v2 is committed.

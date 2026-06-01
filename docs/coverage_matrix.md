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

## Risk Adjustment

| PP ID | Entity / table | Measure / signal | Question ID | Agent |
|---|---|---|---|---|
| PP-RA-001 | `fact_raf_score`, `dim_hcc` | `RAF Score Avg (V28)`, `V28 vs V24 Δ`, `Revenue Impact $` | Q-RA-001 | RiskAdjustmentAgent |
| PP-RA-002 | `fact_raf_score`, `fact_claim` (encounter-supported flag) | `Unsupported Diagnosis %`, `Audit-Risk Score` | Q-RA-002 | RiskAdjustmentAgent |
| PP-RA-003 | `fact_raf_score`, `dim_payer` | `Improper Payment $ Estimate` | Q-RA-003 | RiskAdjustmentAgent |
| PP-RA-004 | `fact_raf_score`, `fact_claim`, `dim_hcc` (suspect flag) | `Open Suspect HCCs`, `Suspect Recapture Yield $` | Q-RA-004, Q-RA-005 | RiskAdjustmentAgent |

## SIU / FWA

| PP ID | Entity / table | Measure / signal | Question ID | Agent |
|---|---|---|---|---|
| PP-SIU-001 | `fact_claim`, `dim_provider` | `FWA Loss $ Estimate`, `Provider FWA Score` | Q-SIU-001 | SIUAgent |
| PP-SIU-002 | `fact_claim` (CPT/HCPCS distribution), `dim_procedure` | `Upcoding Index`, `Phantom-Service Flags`, `Kickback Network Density` | Q-SIU-002, Q-SIU-003 | SIUAgent |
| PP-SIU-003 | `fact_claim`, `KQL:fwa_signal_events` | `Detection-to-Action Days`, `Live FWA Anomalies (KQL)` | Q-SIU-004 | SIUAgent |
| PP-SIU-004 | `fact_claim`, `fact_rx_claim`, `dim_member` | `Doctor-Shopping Score`, `Rx-Diversion Score`, `MBI Anomaly Flag` | Q-SIU-005 | SIUAgent |

## Care Management

| PP ID | Entity / table | Measure / signal | Question ID | Agent |
|---|---|---|---|---|
| PP-CARE-001 | `fact_claim`, `fact_member_month`, `agg_rising_risk` | `Top 5% Spend Concentration`, `High-Cost Claimant Count` | Q-CARE-001 | CareMgmtAgent |
| PP-CARE-002 | `agg_rising_risk`, `fact_claim` (12-mo trajectory) | `Rising-Risk Score`, `Predicted PMPM Next 12mo` | Q-CARE-002, Q-CARE-003 | CareMgmtAgent |
| PP-CARE-003 | `fact_claim`, `dim_provider`, `dim_plan` (APM contract) | `APM-Attributed Spend %`, `Shared-Savings Earned $` | Q-CARE-004 | CareMgmtAgent |
| PP-CARE-004 | `fact_claim` (POS=ED), `dim_member` | `ED Visits per Member-Year`, `Super-Utilizer Count (≥4 ED/yr)` | Q-CARE-005 | CareMgmtAgent |

## Network & Contracting

| PP ID | Entity / table | Measure / signal | Question ID | Agent |
|---|---|---|---|---|
| PP-NET-001 | `dim_provider`, `dim_member` (geo) | `Network Adequacy %`, `T&D Failures by Specialty` | Q-NET-001 | CFOAgent (v1.1: NetworkAgent) |
| PP-NET-002 | `fact_claim`, `dim_provider` (APM contract) | `APM Payment Mix %` | Q-NET-002 | v1.1: NetworkAgent |
| PP-NET-003 | `fact_claim` (in/out-of-network) | `OON Spend %`, `Leakage by Specialty` | Q-NET-003 | v1.1: NetworkAgent |

## UM / Prior Auth

| PP ID | Entity / table | Measure / signal | Question ID | Agent |
|---|---|---|---|---|
| PP-UM-001 | `fact_auth` | `PA Volume`, `PA Cost per Decision $`, `PA TAT (median, p95)` | Q-UM-001, Q-UM-002 | shared CareMgmt+CFO (v1.1: UMAgent) |
| PP-UM-002 | `fact_auth` | `PA Decision Time SLA Compliance %`, `FHIR PA API Adoption %` | Q-UM-003 | v1.1: UMAgent |
| PP-UM-003 | `fact_auth`, `fact_appeal` | `PA Overturn Rate %`, `Peer-to-Peer Overturn %` | Q-UM-004 | v1.1: UMAgent |

## Cross-cutting

| PP ID | Entity / table | Measure / signal | Question ID | Agent |
|---|---|---|---|---|
| PP-X-001 | `fact_claim` (clinical-data-source flag) | `Hybrid Source Mix %`, `Chart-Chase Cost $` | Q-X-001 | StarsAgent + RiskAdjustmentAgent |
| PP-X-002 | `fact_rx_claim`, `dim_drug` | `Specialty Spend %`, `Top Specialty Drug Cost PMPM` | Q-X-002 | CFOAgent + CareMgmtAgent |

---

## Coverage health (gate)

- **Pain points covered**: 30 / 30 = 100% ✅
- **Each PP has ≥1 question ID**: ✅ (Phase 0b lints this once `sample_questions.md` is committed)
- **Each PP has an agent owner**: ✅
- **Each PP has at least one fact/dim or KQL/GQL signal**: ✅
- **Reverse-direction lint** (every Q-* in `sample_questions.md` resolves to a PP-*): TBD when sample_questions is committed.

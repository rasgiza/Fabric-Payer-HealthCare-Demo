# Persona 05 — Care Management / Population Health Director

## Snapshot

Owns clinical and total-cost-of-care outcomes for the membership. Designs interventions for rising-risk and high-cost members. Bridges medical, pharmacy, and SDOH data. The top 5% of members drive ~50% of spend [CIT:KFF-HIGH-COST-2024] — finding and stabilizing them is the single largest medical-cost lever.

## KPIs they own

| KPI | Target |
|---|---|
| ED utilization per 1000 members | trend-down |
| 30-day all-cause readmission | < 12% |
| High-cost member identification lead-time | ≥ 90 days before high-cost event |
| Care-plan engagement rate | ≥ 60% of identified members |
| SDOH screening completion | ≥ 80% of MA/Medicaid members |
| VBC-attributed lives | trend-up [CIT:HCP-LAN-APM-2024] [CIT:CMMI-VBC-MODELS-2025] |

## Top 3 questions weekly

1. "Show me ED super-utilizers (≥ 4 ED visits in 90 days) with no current care plan, sorted by trailing-90-day total cost."
2. "Which rising-risk members crossed cost-trajectory thresholds this week and need outreach?"
3. "List members with positive housing-instability or food-insecurity SDOH flags and ≥ 2 chronic conditions."

## Top 3 questions quarterly

1. "What's the realized PMPM cost reduction for members enrolled vs not enrolled in our care-management program, propensity-matched?"
2. "Where do behavioral health gaps overlap with rising medical risk? Build a list for integrated outreach."
3. "Project 12-month cost trajectory for our top 1% members and rank by intervention ROI."

## Dashboards they live in

- `Population_Stratification.tmdl` — risk pyramid, rising-risk cohort.
- `Care_Plan_Tracker.tmdl` — engagement funnel, outcome measures.
- `SDOH_Heatmap.tmdl` — geo + needs intersection.

## Pain-point IDs owned

`PP-CARE-*` (target: ≥4)

## Foundry agent

`CareMgmtAgent` (data_agents/CareMgmtAgent.DataAgent/)

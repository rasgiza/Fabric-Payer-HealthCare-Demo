# Persona 02 — Stars / Quality Leader (VP Quality, Stars Director)

## Snapshot

Owns the Medicare Advantage Star Rating and HEDIS performance for the plan. Every cut-point change in the CMS Tech Notes is a board-level event. A 0.5-Star drop on a contract above 50K members can mean tens of millions in QBP and rebate impact.

## KPIs they own

| KPI | Target |
|---|---|
| Overall MA Star Rating | ≥ 4.0 (QBP threshold) [CIT:CMS-STARS-2026-TN] |
| Triple-weighted PDC measures (DR, RAS, STA) | ≥ 80% [CIT:PQA-MEASURES-2025] |
| HEDIS measure rates (CDC, COL, BCS, CCS, CBP, etc.) | meet/exceed national 75th percentile [CIT:NCQA-HEDIS-MY2026] |
| Patient experience CAHPS | trend-up; impact of triple-weight in 2026 model [CIT:CMS-STARS-2026-TN] |
| MTM CMR completion | meet CMS threshold |
| Cut-point gap to next half-Star | < 1 measure away |

## Top 3 questions weekly

1. "Which triple-weighted measures are below this year's projected cut-point right now, and how many member actions close each gap?"
2. "Show me PDC-DR adherence by member, ranked by gap-days-to-80%, with active Rx and prescriber for outreach."
3. "What's our CMR completion rate week-over-week, and which members are still un-attempted?"

## Top 3 questions quarterly

1. "Project our 2027 Star Rating given current measure performance and CMS Tukey-adjusted cut-points."
2. "What's the MA QBP / rebate financial impact of moving from 3.5 to 4.0 Stars on this contract?"
3. "Which HEDIS MY2026 measures are at risk of reverting to admin-only reporting because of ECDS pipeline gaps?"

## Dashboards they live in

- `Stars_Scorecard.tmdl` — overall rating, contract-level scorecard, cut-point distance.
- `HEDIS_Measure_Detail.tmdl` — per-measure denominator/numerator/exclusion drill.
- `Member_Action_List.tmdl` — actionable gap closures by member.

## Pain-point IDs owned

`PP-STAR-*` (target: ≥5)

## Foundry agent

`StarsAgent` (data_agents/StarsAgent.DataAgent/)

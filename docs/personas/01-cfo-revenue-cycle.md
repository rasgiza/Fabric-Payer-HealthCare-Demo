# Persona 01 — CFO / Revenue Cycle Leader

## Snapshot

Owns the financial integrity of every claim that lands. Lives in spreadsheets, AR-aging dashboards, and quarterly board decks. Walks into Monday with three questions: *Are denials trending up? Where did the leakage hit this week? Will we trip an MLR rebate?*

## KPIs they own

| KPI | Target / benchmark |
|---|---|
| Initial denial rate | < 8% (industry stress level ≈ 11% per [CIT:HFMA-RCM-OUTLOOK-2025]) |
| Net denial / write-off rate | < 2% |
| AR days | < 45 days |
| Cost to collect | < 3% of net patient revenue |
| Rework cost per denied claim | < $25 (industry avg ≈ $43.84 per [CIT:HFMA-RCM-OUTLOOK-2025]) |
| Medical Loss Ratio (MA / Commercial) | 80–88% target band [CIT:CMS-MLR-REBATE-2024] [CIT:AHIP-COST-2025] |
| NSA IDR cases open | trend-down [CIT:CMS-NSA-IDR-2025] |

## Top 3 questions weekly

1. "What's our denial rate this week vs trailing 8 weeks, sliced by payer-product, place-of-service, and top CARC?"
2. "Which 10 facilities or providers drove the largest negative AR-day movement?"
3. "How much cash is sitting in IDR / appeals levels 1–3 right now, and what's the 90-day overturn rate by CARC?"

## Top 3 questions quarterly

1. "Are we on track for our MLR target by LOB, and what's the projected rebate exposure?"
2. "Which CARC denial categories are most rework-cost-effective to fix at the front-end?"
3. "What's our NSA IDR win rate vs settlement rate, and is litigation cost rising?"

## Dashboards they live in

- `01_CFO_Boardroom.tmdl` page — denial cliff, AR aging, MLR gauge, IDR backlog.
- `02_RevCycle_Operations.tmdl` page — CARC pareto, payer-product matrix, top-N facility/provider.
- `03_Cash_Forecast.tmdl` page — appeals pipeline value, IDR exposure.

## Pain-point IDs owned (forthcoming in `PAYER_PAIN_POINTS.md`)

`PP-CFO-*` (target: ≥5)

## Foundry agent

`CFOAgent` (data_agents/CFOAgent.DataAgent/)

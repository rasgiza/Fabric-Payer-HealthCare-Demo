# Persona 07 — UM / Prior Authorization Director

## Snapshot

Owns the prior-authorization workflow, peer-to-peer process, and medical-necessity rules. CMS-0057-F enforcement begins January 2027 [CIT:CMS-0057-F]: standard-decision turnaround drops to 7 days and urgent to 72 hours, plus a public PA-metrics report. Physicians complete an average of 43 PAs per week and 94% report PA-related care delays [CIT:AMA-PA-SURVEY-2024] — the regulatory and physician-experience pressure is converging.

> **v1 status:** covered via measures + sample questions, no dedicated agent yet. Promoted to dedicated `UMAgent` in v1.1.

## KPIs they own

| KPI | Target / regulatory |
|---|---|
| Standard PA decision TAT | ≤ 7 calendar days [CIT:CMS-0057-F] |
| Urgent PA decision TAT | ≤ 72 hours [CIT:CMS-0057-F] |
| Peer-to-peer overturn rate | trend-up indicates strong P2P process |
| Initial denial → appeal overturn rate | tracked by service category |
| Gold-card eligible providers | identified and onboarded |
| FHIR PA API readiness | green by CY2027 |

## Top 3 questions weekly

1. "Which PAs are at risk of breaching CMS-0057-F TAT thresholds in the next 24 hours?"
2. "Show peer-to-peer outcomes by specialty and reviewing physician — where are overturns concentrated?"
3. "List providers who would qualify for gold carding based on 12-month approval history."

## Top 3 questions quarterly

1. "What's our PA volume trend by service category, and which categories are candidates for prior-auth removal?"
2. "Run the CMS-0057-F public-metric numbers (volumes, approval %, denial %, appeals) — are we ready to publish?"
3. "Compare PA TAT and overturn rates with the 'no PA required' control group — does PA actually move outcomes?"

## Dashboards they live in

- `PA_Operations.tmdl` — TAT clock, queue depth, breach risk.
- `PA_Outcomes.tmdl` — denial reasons, P2P, appeal overturn pareto.
- `CMS_0057_Metrics.tmdl` — public-reporting view.

## Pain-point IDs owned

`PP-UM-*` (target: ≥3)

## Foundry agent

v1: sample questions answered via `CareMgmtAgent` + `CFOAgent`.
v1.1: dedicated `UMAgent` aligned with FHIR PA API surface.

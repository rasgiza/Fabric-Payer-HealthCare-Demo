# Persona 04 — SIU / Fraud, Waste & Abuse Investigator

## Snapshot

Owns identification and recovery of fraudulent, wasteful, and abusive billing. Lives in case management tools, claims editing rules, and post-payment audits. Healthcare fraud costs the U.S. tens of billions per year [CIT:NHCAA-FRAUD-COST] — even a 1% recovery improvement is material to plan results.

## KPIs they own

| KPI | Target |
|---|---|
| Pre-payment denial savings | trend-up |
| Post-payment recovery $ | trend-up |
| Investigator backlog (open cases) | < 30 days median |
| False-positive flag rate | < 30% |
| Telehealth fraud signal detection latency | < 7 days [CIT:OIG-WORKPLAN-2025] |
| Provider exclusion-list match latency | real-time |

## Top 3 questions weekly

1. "Which providers are billing CPT/HCPCS combinations that are statistically anomalous vs peers in the same specialty/region?"
2. "Show all telehealth claims this week with member-provider distance > X miles and no prior in-person relationship."
3. "List members with claims from > 5 distinct providers in 30 days for the same diagnosis category."

## Top 3 questions quarterly

1. "What was our fraud recovery $ vs FTE cost this quarter? Which scheme types are highest ROI?"
2. "Show top 20 'phantom billing' candidates: providers with claim density > 99th percentile but member-overlap < 5% with peer providers."
3. "Run a cross-payer collusion check: members appearing in suspicious clusters across multiple billing TINs."

## Dashboards they live in

- `FWA_Case_Queue.tmdl` — open cases, aging, recovery $ trail.
- `Provider_Anomaly_Map.tmdl` — geo + specialty peer-comparison heatmap.
- `Scheme_Library.tmdl` — pre-built scheme detectors (upcoding, phantom, kickback, telefraud).

## Pain-point IDs owned

`PP-SIU-*` (target: ≥4)

## Foundry agent

`SIUAgent` (data_agents/SIUAgent.DataAgent/)

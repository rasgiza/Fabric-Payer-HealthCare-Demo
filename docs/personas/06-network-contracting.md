# Persona 06 — Network & Contracting Director

## Snapshot

Owns network adequacy and provider contract economics. Negotiates fee schedules, value-based-care arrangements, and risk-share contracts. Must keep CMS network-adequacy time-and-distance standards green for every county-specialty cell [CIT:CMS-NETWORK-ADEQUACY-2024] while moving the book toward two-sided risk [CIT:HCP-LAN-APM-2024].

> **v1 status:** covered via measures + sample questions, no dedicated agent yet. Promoted to dedicated `NetworkAgent` in v1.1.

## KPIs they own

| KPI | Target |
|---|---|
| Network adequacy compliance (county × specialty) | 100% green by HSD-table standard |
| % VBC / APM payments | trend-up; benchmark vs HCP-LAN APM categories [CIT:HCP-LAN-APM-2024] |
| Contract economics (effective rate vs Medicare) | by line, by specialty |
| Provider satisfaction (annual survey) | ≥ 75 NPS-style |
| Single-source dependency | flag any specialty with single provider in a county |

## Top 3 questions weekly

1. "Are we within network-adequacy time/distance for all primary-care, behavioral-health, and oncology cells this week?"
2. "Which providers are scheduled for re-contracting in the next 90 days and how do their effective rates compare to Medicare benchmark?"
3. "Show network leakage: in-network attributed members getting care out-of-network for routine services."

## Top 3 questions quarterly

1. "What's our APM-category mix vs HCP-LAN national benchmark? Where's the biggest movement opportunity?"
2. "Model the financial impact of a 3% rate increase to specialists vs to PCPs vs to behavioral health."
3. "Which TINs are at high single-source risk and need recruitment of a second provider?"

## Dashboards they live in

- `Network_Adequacy_Map.tmdl` — county-specialty grid.
- `Contract_Economics.tmdl` — effective rates vs Medicare benchmark.
- `APM_Mix_Tracker.tmdl` — HCP-LAN category distribution.

## Pain-point IDs owned

`PP-NET-*` (target: ≥3)

## Foundry agent

v1: covered by `CFOAgent` for economics + sample questions.
v1.1: dedicated `NetworkAgent`.

# CMS-0057-F Prior Authorization Interoperability Final Rule

Source: CMS-0057-F Final Rule [CIT:CMS-0057-F]. Compliance phased in 2026-2027.

## Scope

Applies to Medicare Advantage, Medicaid Managed Care, CHIP, QHPs on FFEs.

## Decision-time SLAs (2026 enforcement)

| Request type | Max decision time | Effective |
|---|---|---|
| **Standard** PA request | 7 calendar days | 2026-01-01 |
| **Expedited** PA request (urgent) | 72 hours | 2026-01-01 |
| **Reason codes** for denial | required, structured | 2026-01-01 |
| **API submission/response** | FHIR PA API | 2027-01-01 |
| **Prior Authorization API metrics** | publicly reported | 2026-03-31 (annual) |

## Required public reporting

Plans must publicly report annually (by March 31):
- Total PA volume
- Volume by approval/denial/appeal-overturn
- Avg + median + p95 turnaround time
- % decided within SLA
- Top 25 services by PA volume

## FHIR PA APIs (Da Vinci PAS implementation guide)

Three required APIs:
1. **Coverage Requirements Discovery (CRD)** - tells provider whether PA needed
2. **Documentation Templates and Rules (DTR)** - structured data collection
3. **Prior Authorization Support (PAS)** - submit + receive decision

## Gold-carding

Optional mechanism - plans may exempt providers with consistent approval rates from PA on specific services for a defined window. UMAgent surfaces gold-card eligibility via `[AuthApprovalRate]` ≥ threshold over rolling 90 days.

## Agent guidance (UMAgent)

- Use `[AuthSLAMetPct]` as primary CMS-0057-F compliance metric.
- Use `[AuthMedianTAT]` for narrating speed; cite p95 separately.
- For "auto-deny" questions: REFUSE - the agent is not the adjudication authority.
- For peer-to-peer overturn questions, cite AMA survey ~39% baseline [CIT:AMA-PA-SURVEY-2024].

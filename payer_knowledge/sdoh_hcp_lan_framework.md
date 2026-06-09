# SDOH + HCP-LAN Care Management Framework

Sources: HCP-LAN APM Framework + CMMI VBC models + SDOH integration literature.

## SDOH integration in care management

Social determinants drive ~50-80% of health outcomes per CMMI / Healthy People 2030. Payers integrate SDOH into care management by:

1. **Screening** - PRAPARE / AHC-HRSN tool at outreach
2. **Coding** - ICD-10 Z55-Z65 SDOH codes; payer-specific flags in `dim_member`
3. **Routing** - housing, food, transport referrals to community-based organizations (CBOs)
4. **Tracking** - referral closure events flow to RTI in Phase 6 (`alert_closure_events`)

## SDOH flags in this demo

`dim_member` columns:
- `sdoh_housing_unstable` - homeless or housing-cost-burdened (>50% income)
- `sdoh_food_insecure` - SNAP-eligible OR food-bank-served signal
- `sdoh_transport_barrier` - lacks reliable transport to medical appointments

## HCP-LAN APM categories (used by NetworkAgent + CareMgmtAgent)

| Category | Description | VBC maturity |
|---|---|---|
| 1 | Fee-for-service no link to quality | None |
| 2 | FFS with link to quality (P4P, gainsharing) | Low |
| 3a | APMs with shared savings (no downside) | Mid |
| 3b | APMs with shared savings + risk | Mid-high |
| 4a | Population-based payment (full risk on a defined pop) | High |
| 4b | Capitation with comprehensive risk | High |

National payer mix target (HCP-LAN goal): >50% in categories 3-4 by 2025.

## Care management engagement metrics

- **Engagement rate** = members enrolled in active care management / identified eligible
- **Outreach attempt** = call/text/email logged
- **Connection rate** = answered + agreed to engage / outreach attempts
- Industry benchmarks: 25-40% engagement on rising-risk cohort

# KFF High-Cost Member Methodology

Source: Kaiser Family Foundation high-cost member analyses [CIT:KFF-HIGH-COST-2024] + AHIP rising-risk frameworks.

## Core finding

The top 5% of members account for ~50% of total medical spend. The top 1% account for ~25%. Identifying these members early - before they reach the top decile - is the foundation of payer care management.

## Risk segmentation (used by CareMgmtAgent)

| Tier | Definition | Spend share | Action |
|---|---|---|---|
| **High-cost** | Top 5% YTD spend OR > $50K rolling-12 | ~50% | Active care management, complex case worker |
| **Rising-risk** | 80th-95th percentile + ≥2 chronic conditions + utilization trajectory ↑ | ~25% | Outreach, pharmacy adherence support, SDOH screening |
| **At-risk** | 50-80th + chronic + SDOH flag | ~15% | Proactive monitoring, gap closure |
| **Healthy** | Bottom 50% | ~10% | Engagement / wellness |

## Rising-risk identification

Operational definition (CareMgmtAgent uses):
1. Member with ≥2 chronic conditions (HCC presence is a proxy)
2. YTD spend in 80th-95th percentile
3. Utilization trajectory: rolling-90d spend > rolling-365d-PMPM × 1.5
4. NOT already in top 5% (those are high-cost)

## ED super-utilizer

Operational definition:
- ≥6 ED visits in trailing 12 months
- OR ≥3 ED visits in trailing 90 days
- Industry framing: super-utilizer cohort sees ~10x cost of average member

## SDOH overlay

Members with SDOH risk flags (housing instability, food insecurity, transportation barriers) have:
- ED utilization 2-3x higher than non-flagged peers
- Medication adherence (PDC) 15-25 pp lower
- Care plan engagement rates lower until SDOH addressed

The semantic model `dim_member` exposes:
- `sdoh_housing_unstable`
- `sdoh_food_insecure`
- `sdoh_transport_barrier`

## Agent guidance

- Never **diagnose** - report utilization patterns and risk band only.
- Never predict mortality - REFUSE that framing.
- Always include SDOH context when ED super-utilization is present.

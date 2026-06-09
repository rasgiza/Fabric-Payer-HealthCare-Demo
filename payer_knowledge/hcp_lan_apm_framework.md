# HCP-LAN APM Framework

Source: Health Care Payment Learning & Action Network (HCP-LAN) APM Measurement Effort [CIT:HCP-LAN-APM-2024].

## Category definitions

The HCP-LAN classifies provider payment arrangements into 4 categories with sub-tiers. Used by NetworkAgent to report payment-mix progress toward value-based care.

| Code | Name | Description | Provider risk |
|---|---|---|---|
| **1** | FFS - No link to quality/value | Pure fee-for-service | None |
| **2A** | FFS + Foundational payments | P4P infrastructure (no shared savings) | None |
| **2B** | FFS + Pay for reporting | Bonuses for reporting only | None |
| **2C** | FFS + Pay for performance | Bonuses tied to quality metrics | None |
| **3A** | APMs with shared savings | Upside-only (no downside) | Low |
| **3B** | APMs with shared savings + risk | Upside + downside | Mid |
| **4A** | Population-based payment - condition-specific | Per-condition capitation | High |
| **4B** | Population-based payment - comprehensive | Full pop capitation | High |
| **4C** | Integrated finance & delivery | Capitation + delivery integration | Highest |

## National benchmarks (2024)

- Category 1 (pure FFS): ~40% of provider payments
- Category 2 (FFS+quality): ~20%
- Category 3 (APMs): ~30%
- Category 4 (population-based): ~10%

HCP-LAN goal: >50% of payments in categories 3-4 by 2025.

## Two-sided risk readiness signal

NetworkAgent uses these signals to identify provider groups ready to move from upside-only (3A) to two-sided (3B):
- 2+ years of beating shared-savings benchmark
- Quality scores above 75th percentile
- Adequate panel size (>5,000 attributed lives)
- Clinical leadership readiness (NetworkAgent surfaces measurable signals; final readiness is contracting team's call)

## Agent guidance

- Always cite HCP-LAN category numerically (3A vs 3B matters for risk discussion)
- Use `[APMTier3Plus]` measure for "advanced VBC" cohort count
- Never quote competitor rates - REFUSE.

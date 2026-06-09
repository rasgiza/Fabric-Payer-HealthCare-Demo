# CMS-HCC V28 Risk Adjustment Model

Source: CMS-HCC V28 Announcement [CIT:CMS-HCC-V28-2026]. Sample HCC weights in `data/reference/hcc_v28_sample.csv`.

## V28 vs V24 transition

CMS phased in the V28 model over 3 payment years (PY2024-PY2026). PY2026 is **100% V28** (zero blend). Key changes:

- HCC count reduced from 86 (V24) to 115 categories (V28) but with stricter ICD-10 mapping rules (~2,300 fewer diagnosis-to-HCC mappings)
- Many V24 codes (e.g., diabetes without complications, vascular disease) lost coefficient or were dropped
- Net impact: average MA RAF score down ~3-4% under pure V28 vs pure V24
- Documentation requirements tightened: each submitted HCC must trace to a face-to-face encounter with qualifying provider type within the data collection year

## RAF score components

```
RAF = demographic_RAF + sum(HCC_coefficient_i for HCC i in member's coded HCCs)
    + interaction terms (e.g., disabled-and-disease)
```

Demographic RAF is set by age band + gender + Medicaid status + originally-disabled flag.

## Suspect HCC methodology

A "suspect HCC" is a condition the member was coded for in **prior years** (or has supporting clinical evidence in claims/labs/Rx) but has **not been coded in the current data collection year**. Recapturing a suspect HCC requires:

1. Face-to-face encounter with qualifying provider
2. Current-year diagnosis on encounter
3. Documentation supporting the diagnosis (MEAT criteria: Monitor, Evaluate, Assess, Treat)

The semantic model exposes:
- `[RAFScoreAvg]` - population mean
- `[HCCMemberCount]` - members with at least one HCC
- `[SuspectedHCCGap]` - members with at least one suspect HCC (proxy: `suspect_hcc_count > 0`)

## Agent guidance

- Always cite V28 or V24 explicitly when discussing RAF (transition is complete in PY2026 but historical comparisons matter).
- Never recommend adding a code "without documentation" - that triggers RADV audit risk and is a policy violation.
- Suspect-HCC narration: emphasize the MEAT criteria gate; recapture yield estimates require RAF coefficient × premium-PMPM math.

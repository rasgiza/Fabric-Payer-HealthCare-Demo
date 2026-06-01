# Reference Data

Seed CSVs lifted from public sources. Used by `tools/gen_payer_overlay.py` to drive distributions, code mappings, and quality measure calibration.

| File | Source | Decision (per `docs/_internal/oss_inventory.md`) |
|---|---|---|
| `payers.csv` | Authored (real payer names, public market info) | AUTHOR |
| `carc_codes.csv` | X12 publicly-published code list | LIFT (public values) |
| `hedis_my2026_measures.csv` | NCQA HEDIS MY2026 spec (citation only) + VSAC OIDs | CITE ONLY (numerator/denominator implementations from public summaries) [CIT:NCQA-HEDIS-MY2026] |
| `cms_stars_2026_cutpoints.csv` | CMS 2026 Stars Technical Notes — illustrative cut-points | LIFT (public values) [CIT:CMS-STARS-2026-TN] |
| `hcc_v28_sample.csv` | CMS-HCC V28 crosswalk subset | LIFT (public values) [CIT:CMS-HCC-V28-2026] |
| `conditions_prevalence.csv` | Calibrated from KFF / public CDC prevalence summaries | AUTHOR |

## Notes

- `cms_stars_2026_cutpoints.csv` cut-point values are illustrative for the demo. Production deployments should download the most recent CMS Star Ratings Technical Notes and replace this file via the `tools/refresh_reference_data.py` (Phase 1.1+).
- `hcc_v28_sample.csv` is intentionally a 20-row subset for synthetic-data calibration. The full V28 model has ~115 HCCs; the full crosswalk is downloaded into the lakehouse during Phase 2 silver enrichment, not committed to git.
- `hedis_my2026_measures.csv` references VSAC OIDs (public identifiers); the value-set contents themselves are not redistributed.
- All percentages and coefficients are illustrative; do not use for actual benefit determination.

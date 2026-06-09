# CMS 2026 Stars Cut-Points

Source: CMS 2026 Star Ratings Technical Notes [CIT:CMS-STARS-2026-TN]. Per-measure cut-points in `data/reference/cms_stars_2026_cutpoints.csv`.

## Cut-point methodology

CMS sets cut-points using **clustering on prior MY contract performance**. Each measure has 4 cut-points dividing performance into 5 star tiers (1-5).

For RY2028 (which uses MY2026 data), cut-points are **not yet published** - StarsAgent must refuse to project numerical RY2028 cut-points and instead reference RY2027 historical cut-points with appropriate caveat.

## Triple-weighted measures (3x contract-level weight)

- CBP, HBD, EED, MAH, MAD, MAC, KED (Kidney Health Evaluation)

## QBP revenue at risk

The Quality Bonus Payment formula (per CMS):
- 5-star: 5% bonus
- 4.5-star: 5% bonus
- 4-star: 5% bonus (in qualifying counties)
- 3.5-star and below: no bonus
- 5-star contracts also get year-round open enrollment

A drop from 4.0 to 3.5 stars = loss of QBP entirely on the affected contract.

## Cut-point gap calculation

For a measure where the contract sits at score `s`:
- `gap_to_3star = max(0, cut_3 - s)`
- `gap_to_4star = max(0, cut_4 - s)`
- `gap_to_5star = max(0, cut_5 - s)`

The semantic model exposes `[StarsContractRating]` as the average `compliance_pct * 5` across measures (placeholder; refined in Phase 7 when MY2026 cut-points are wired in via reference dim).

## Agent guidance

- Always disambiguate measurement year vs rating year in answers.
- Never project cut-points for unpublished rating years - return REFUSAL with explanation.
- For triple-weighted measures call out the 3x contract weight.

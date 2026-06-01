# Open Questions

Items flagged during Phase 0 red-team review that need a real subject-matter expert (or a deeper public-source pass) before being locked in.

> Not blocking for v1, but every entry below should land in v1.1 or be explicitly closed. Each item must reference a `PP-*` pain point ID or a `Q-*` sample-question ID once those exist.

## Format

```
- id: OQ-001
  topic: <short title>
  raised_by: <reviewer>
  raised_on: <YYYY-MM-DD>
  affects: [PP-..., Q-..., persona]
  question: <what we are unsure about>
  current_assumption: <what we wrote in lieu of certainty>
  resolution: open | resolved (link to commit/PR)
```

## Items

| ID | Topic | Affects | Question / current assumption | Severity |
|---|---|---|---|---|
| OQ-001 | NSA IDR per-determination admin cost | PP-CFO-005, Q-CFO-007 | Industry varies $100–$400/case; we assume ~$200 for v1 storytelling. | low |
| OQ-002 | CAHPS overlay on Synthea data | PP-STAR-004, Q-STAR-005, Q-STAR-015 | Synthea has no CAHPS; we'll inject a synthetic per-member CAHPS respondent overlay. SME to validate distribution. | medium |
| OQ-003 | Suspect-HCC recapture yield | PP-RA-004, Q-RA-005 | Industry yield 20–60%; v1 seeds ~30%. | medium |
| OQ-004 | FWA detection-to-action benchmark | PP-SIU-003, Q-SIU-008 | No standardized public benchmark; v1 cites OIG enforcement timeline as proxy. | low |
| OQ-005 | APM payment terms overlay | PP-CARE-003, Q-CARE-004, Q-CARE-009 | Synthea has no APM payments; v1 adds `dim_plan.apm_category` (HCP-LAN 1–4) + synthetic shared-savings amounts. | medium |
| OQ-006 | PA overturn-rate benchmarks by service line | PP-UM-003, Q-UM-004, Q-UM-007 | Public data fragmented; v1 uses ranges aligned with CMS-0057-F context with caveats in `aiInstructions.md`. | low |

## Confidence summary (input from Phase 0b red-team pass)

- **High-confidence pain points**: 17 of 30 (57%)
- **Medium-confidence**: 12 of 30 (40%)
- **Low-confidence**: 1 of 30 (3%)

Phase 0b gate (each PP at minimum medium): ✅ all 30 meet the floor.

# Known data-fidelity gaps — synthetic generator

Surfaced by `tools/data_fidelity.py` against `data/synth/smoke` on 2026-06-11.
These are realism gaps in the synth generator, not bugs in the demo logic.
The fidelity gate is calibrated to catch *fully* uniform / structurally
broken samplers while still passing the current lightly-weighted generator.
Tighten the thresholds when each gap is closed.

| Gap | Current | Industry-realistic target | Threshold today | Tighten to | Owner |
|---|---|---|---|---|---|
| **CARC denial concentration** | top-3 of 20 codes ≈ 17% | top-3 ≥ 50% (CMS adjudication books) | `floor = max(15%, 1.10 × 3/N)` | 50% (`top3 >= 0.50`) | generator weighted-CARC sampler |
| **LOB share — Dual** | 3.8% (smoke) | 8–12% in MA + Medicaid integrated books | not gated | gate Dual ∈ [0.05, 0.15] when generator emits Dual at scale | generator |
| **HCC RAF distribution** | mean 0.79, n=241 of 500 members | mean 0.95–1.10 for MA-heavy book; ≥ 60% of MA members coded | mean ∈ [0.7, 1.6] | mean ∈ [0.85, 1.20]; coded coverage ≥ 0.55 | generator |
| **Provider count** | 50 | ≥ 200 for 500 members (4:1 typical) | not gated | gate `n_providers / n_members ≥ 0.20` | generator |
| **Specialty mix** | uniform across `specialty_type` (visual scan) | PCP 30%, specialist 50%, ancillary 20% | not gated | gate top-3 specialties ≥ 60% | generator |

## Why these exist

The smoke run is a 500-member sample sized for fast CI; it is intentionally
small and uses uniform samplers in places where production-grade synth would
weight by CMS-published distributions. The generator at full scale (50k
members) produces the same shapes — fixing the realism gaps requires data
work, not scale.

## Closing a gap

1. Update the relevant generator script under `tools/gen_*` (e.g.
   `gen_payer_overlay.py` for CARC weights; `gen_synthea_overlay.py` for
   provider count).
2. Re-run `tools/run_local_etl.py --scale smoke` to regenerate the
   bundled run.
3. Tighten the corresponding threshold in `tools/data_fidelity.py`.
4. Update this table.
5. `pytest -k fidelity` to confirm the new floor passes.

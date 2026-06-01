# Fabric Payer Healthcare Demo

End-to-end Microsoft Fabric demo for **U.S. health-insurance payers** — synthetic data, medallion lakehouse, payer ontology + graph, semantic model, Foundry data agents, real-time intelligence, and a one-click launcher.

> **Status:** Phase 0a — Skeleton & Citation Backbone. The repo intentionally starts with the *industry-truth doc set* (pain points, coverage matrix, sample questions, story, runbook), not with code. See [`docs/`](docs/).

---

## Why this demo exists

U.S. payers lose billions per year to denial leakage, Stars cut-point gaps, risk-adjustment under-coding, fraud, and disconnected operational data. This demo shows how a single Microsoft Fabric workspace + Foundry agents collapses that toolchain into one industry-grounded experience.

Every artifact in this repo — every table, every measure, every agent question, every dashboard — traces back to a documented industry pain point with a public citation. See [`docs/PAYER_PAIN_POINTS.md`](docs/PAYER_PAIN_POINTS.md) (Phase 0b) and [`docs/COVERAGE_MATRIX.md`](docs/COVERAGE_MATRIX.md).

## Personas covered (v1)

| # | Persona | Top concerns |
|---|---|---|
| 1 | CFO / Revenue Cycle | Denial rate, AR days, MLR, leakage, NSA/IDR backlog |
| 2 | Stars / Quality | Cut-point gaps, HEDIS MY2026, PDC, CMR completion |
| 3 | Risk Adjustment | RAF accuracy, HCC V28 suspect codes, OIG audit posture |
| 4 | SIU / Fraud, Waste & Abuse | Upcoding, phantom billing, telefraud, scheme detection |
| 5 | Care Management / Pop Health | Rising-risk, ED super-utilizers, SDOH integration |
| 6 | Network & Contracting | Network adequacy, VBC/APM mix, contract analytics |
| 7 | UM / Prior Authorization | TAT, CMS-0057-F readiness, peer-to-peer overturn |

See per-persona pages in [`docs/personas/`](docs/personas/).

## Repo layout

```
docs/                 industry truth: pain points, coverage matrix, sample questions, story, runbook
  personas/           one-page card per persona
  _internal/          API delta scan, OSS inventory, adopt list (not customer-facing)
data_agents/          one folder per Foundry data agent (aiInstructions.md authored before code)
infra/                Bicep / Fabric workspace provisioning
notebooks/            Synthea generation, ETL, RTI scoring, launcher
report/               Power BI semantic model + report (TMDL + PBIR)
tools/                check_citations.py, audit_data.py, BPA, eval, launcher utilities
.github/workflows/    CI: citation linter, repo hygiene
citations.yaml        single source of truth for all industry citations
```

## Phase plan (summary)

| Phase | What | Gate |
|---|---|---|
| 0a | Repo skeleton + citation backbone + persona cards + API delta scan | Linter green, ≥15 citations, 7 persona cards |
| 0b | Pain points + coverage matrix + sample questions + red-team review | ≥30 pain points, 100% coverage, ≥100 questions |
| 0c | Per-agent `aiInstructions.md` + demo story + executive runbook | 7 agents drafted, runbook readable cold |
| 1 | Synthea + payer overlay (claims, eligibility, RA, quality, PA, appeals) | Audit clean, distributions sane |
| 2 | Medallion lakehouse + ETL | All silver/gold tables pass DQ |
| 3 | Payer ontology + Fabric Graph | ~25 entities / ~40 relationships |
| 4 | PayerAnalytics semantic model + Power BI report | BPA clean, 60+ measures, Direct Lake |
| 5 | 7 Foundry data agents + orchestrator | Eval pass rate ≥ target |
| 6 | RTI: Eventhouse + KQL + Activator + Power Automate MTTR loop | 5 alert lanes wired |
| 7 | Launcher notebook + governance + 3D story page | One-click deploy works on F64+ |

Detailed plan: see `docs/PLAN.md` (forthcoming) or the session memory.

## Getting started

> **Not yet runnable.** This repo is in Phase 0a. The first runnable artifact will be `tools/check_citations.py` (Phase 0a). The first end-to-end runnable demo is the launcher in Phase 7.

## License

[Apache-2.0](LICENSE).

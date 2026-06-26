# Contributing to Fabric-Payer-HealthCare-Demo

This repo ships a payer-side Microsoft Fabric demo (medallion ETL → semantic
models → Foundry hosted agents + Fabric data agents → RTI). It targets
**deploy-ready** quality: every PR must keep the data, semantic-model, agent,
and audit gates green so a customer can `git clone && deploy.py` without
manual cleanup.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

## Pre-commit gates

Run these before pushing. CI runs the same set.

```bash
ruff check .
pytest
python tools/gen_payer_overlay.py --scale 0.005 --seed 42 --out data/synth/smoke
python tools/run_local_etl.py --run-id smoke
python tools/audit_data.py     --run-dir data/synth/smoke
python tools/data_fidelity.py  --run-dir data/synth/smoke
python tools/dq_checks.py      --run-id smoke
python tools/audit_log.py show --run-id smoke         # expect 3 rows
python tools/deploy.py --check
```

## Commit message conventions

Every commit subject **must** start with one of these scope prefixes plus a
sub-letter (e.g. `E.0b:`). Scopes group changes for changelog generation and
for the PR template's coverage map.

| Scope | Subject area | Touches |
|-------|--------------|---------|
| `A.*` | Docs / narrative | `README.md`, `docs/`, `payer_knowledge/` |
| `B.*` | Semantic model / TMDL | `workspace/*.SemanticModel/` |
| `C.*` | Data agent / Foundry artifact | `data_agents/`, `tools/deploy_data_agents.py`, `tools/foundry_*` |
| `D.*` | Evals / observability | `tools/run_evals.py`, `tools/eval_*`, `evals/`, App Insights wiring |
| `E.*` | Infrastructure / DQ / audit / CI | `tools/audit_*`, `tools/dq_checks.py`, `.github/`, `requirements*.txt` |
| `F.*` | Notebooks | `workspace/NB_*.Notebook/`, `*.ipynb` |
| `G.*` | Ontology | `ontology/`, `workspace/Payer_Ontology.Ontology/` |

Sub-letters within a scope are local to each campaign — use the next free
letter when starting new work in a scope (e.g. `E.0a` → `E.0b` → `E.0c`).

### Commit subject style
- Imperative, ≤72 chars, no trailing period.
- Prefer descriptive over clever (`E.0b: gold audit_log table + NB hooks` not
  `audit stuff`).
- Use the body for the "why" plus a one-line gate result
  (`Full suite: 195 passed.`).

## Schema-contract invariants

Some tests are deliberately rigid because they pin cross-file contracts.
Update them in the **same commit** that introduces the change:

- `tests/test_fidelity_returns_expected_check_set` pins the fidelity check
  names. Adding a new check requires updating the expected set here.
- `tools/audit_log.py:AUDIT_LOG_COLUMNS` is mirrored inline in NB_01 / NB_02 /
  NB_03 `_AUDIT_SCHEMA`. `tests/test_audit_log.py` asserts they agree.
- `tools/agent_audit.py:AGENT_CALL_COLUMNS` is mirrored in `spark_schema()`.
  Any column add → update both, plus `tests/test_agent_audit.py`.
- The `BRONZE_TABLES` list lives in NB_00, NB_01, and `tools/run_local_etl.py`.
  All three must match exactly.

## PR submission

1. Branch from `main` (or the current campaign branch).
2. Open the PR using the auto-applied `.github/pull_request_template.md`.
3. Tick the deploy-readiness checklist with evidence.
4. Wait for CI green (lint, tests, citations, data-gates, deploy-dryrun).
5. Request review.

## Out-of-scope

- Cross-repo sync (e.g. forking changes into the `-Jumpstart` repo) is done
  separately — not in deliverable PRs.
- Service-side AI artifacts (Power BI verified answers, model AI data schema,
  per-source AI instructions) are UI-only and not stored in Git.
- The `tools/convert_notebook_format.py` helper is local-only and untracked.

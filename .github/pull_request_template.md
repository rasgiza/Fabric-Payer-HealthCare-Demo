<!-- 
Fabric-Payer-HealthCare-Demo pull-request template.
Delete sections that do not apply. Keep the deploy-readiness checklist.
-->

## Summary
<!-- 1-3 sentences. What changed and why. -->

## Commit scope
<!-- All commits in this PR must use one of these prefixes. -->
- [ ] **A.\*** docs / narrative
- [ ] **B.\*** semantic-model / TMDL
- [ ] **C.\*** data agent / Foundry artifact
- [ ] **D.\*** evals / observability
- [ ] **E.\*** infrastructure / DQ / audit / CI
- [ ] **F.\*** notebooks (medallion or RTI)
- [ ] **G.\*** ontology

## Type of change
- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change (requires version bump / migration note)
- [ ] Docs only
- [ ] CI / tooling only

---

## Deploy-readiness checklist
> Required for every PR that touches `tools/`, `workspace/`, `data_agents/`, `ontology/`, `payer_knowledge/`, or `.github/workflows/`.

### Tests & gates
- [ ] `ruff check .` is clean
- [ ] `pytest` is fully green (all baseline + any new tests)
- [ ] `python tools/dq_checks.py --run-id smoke` — schema contracts pass
- [ ] `python tools/data_fidelity.py --run-dir data/synth/smoke` — fidelity checks pass
- [ ] `python tools/audit_data.py --run-dir data/synth/smoke` — audit clean
- [ ] `python tools/audit_log.py show --run-id smoke` — 3 audit rows (bronze/silver/gold)

### Workspace tree
- [ ] `python tools/deploy.py --check` — workspace ↔ parameter.yml drift = 0
- [ ] `python tools/deploy.py --env dev --dry-run` — passes

### Cross-artifact coherence
- [ ] Touched a semantic model? Ran `python tools/audit_semantic_model.py`.
- [ ] Touched a data agent? Updated `data_agents/<X>/eval/cases.jsonl` + ran `python tools/run_evals.py`.
- [ ] Touched the ontology? Ran `python tools/audit_rels.py` and updated `tests/test_fidelity_returns_expected_check_set` if a new fidelity check was added.
- [ ] Touched `tools/audit_log.py` columns? Updated NB_01/NB_02/NB_03 inline `_AUDIT_SCHEMA` in the same commit.
- [ ] Touched `tools/agent_audit.py` columns? Updated `spark_schema()` in the same commit.

### Documentation
- [ ] If user-facing behavior changed, README or `docs/` updated.
- [ ] If a new top-level capability was added, mentioned in `docs/DIFFERENTIATION.md` (or the Databricks parity matrix).

---

## Test plan / evidence
<!-- Paste pytest summary, dq_checks output, or screenshots. -->
```
pytest: ___ passed
dq_checks: ___/___ contract assertions pass
```

## Linked issues / discussions
<!-- Closes #N, Refs #M -->

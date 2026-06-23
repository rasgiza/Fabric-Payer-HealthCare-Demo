"""Shape tests for the RTI C.4 skeleton: PayerOps_Activator (Reflex).

C.4 lands one Reflex (Activator) item that subscribes to the analytic KQL
queries published by NB_RTI_02 (PA latency) and NB_RTI_04 (SIU intake
scoring) and emits 2 outbound rules:

  1. **PA-denial-rate spike**
     Trigger: in any 15m window from NB_RTI_02's PA_LATENCY_KQL, the rolling
     decision count is at least PA_RULE_MIN_DECISIONS AND the breach_rate
     (decisions where latency_hours > sla_hours) exceeds PA_RULE_THRESHOLD.
     Routes to: UM director Teams channel; opens a PA-Latency-Audit work item.

  2. **SIU intake-score threshold**
     Trigger: any row emitted by NB_RTI_04's SIU_SCORING_KQL with
     intake_score >= SIU_RULE_SCORE_THRESHOLD (matches the notebook's
     score_threshold default).
     Routes to: SIU triage queue; opens an SIU-Intake-Triage work item.

Following the C.1/C.2 convention, the Reflex ships as `.platform`-only --
fabric-cicd 1.1.0 supports Reflex in SUPPORTED_TYPES + itemOrder, but the
on-disk rule-definition JSON shape has not been observed yet from a real
Fabric Git export. Until then, the 2 rule predicates are locked here as
test-level literals so:
  - C.6 RUNBOOK can document the exact rule semantics
  - The author of a future Fabric-side rule export can byte-diff against
    these literals to confirm no semantic drift
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REFLEX_FOLDER = "PayerOps_Activator.Reflex"
REFLEX_LOGICAL_ID = "19000019-0001-0001-0001-000000000001"

# Locked rule design. C.6 RUNBOOK lifts these verbatim. The downstream
# Fabric Activator UI will be configured to match these predicates; when
# fabric-cicd 1.1.0 supports a Git-exportable rule descriptor for Reflex,
# this dict becomes the source-of-truth and migrates into a sidecar JSON.
EXPECTED_RULES = {
    "pa_denial_rate_spike": {
        "source_notebook": "NB_RTI_02_PA_Latency",
        "source_kql_var":  "PA_LATENCY_KQL",
        "source_table":    "auth_lifecycle",
        "predicate": (
            "decisions >= PA_RULE_MIN_DECISIONS "
            "AND breach_rate > PA_RULE_THRESHOLD"
        ),
        "thresholds": {
            "PA_RULE_MIN_DECISIONS": 50,
            "PA_RULE_THRESHOLD":     0.20,
        },
        "route": {
            "channel":   "UM Director Teams",
            "work_item": "PA-Latency-Audit",
        },
        "regulatory_hook": "CMS-0057-F",
    },
    "siu_intake_score_alert": {
        "source_notebook": "NB_RTI_04_SIU_Intake_Scoring",
        "source_kql_var":  "SIU_SCORING_KQL",
        "source_table":    "claim_arrivals",
        "predicate":       "intake_score >= SIU_RULE_SCORE_THRESHOLD",
        "thresholds": {
            "SIU_RULE_SCORE_THRESHOLD": 0.6,
        },
        "route": {
            "channel":   "SIU Triage Queue",
            "work_item": "SIU-Intake-Triage",
        },
        "regulatory_hook": None,
    },
}


@pytest.fixture(scope="module")
def workspace_dir(repo_root: Path) -> Path:
    return repo_root / "workspace"


@pytest.fixture(scope="module")
def reflex_dir(workspace_dir: Path) -> Path:
    return workspace_dir / REFLEX_FOLDER


def test_reflex_folder_shape(reflex_dir: Path) -> None:
    assert reflex_dir.is_dir(), f"missing folder {reflex_dir}"
    children = sorted(p.name for p in reflex_dir.iterdir())
    assert children == [".platform"], (
        f"unexpected files in {REFLEX_FOLDER}: {children}. "
        "Pattern is .platform-only until a real Fabric Git export of a Reflex is observed."
    )


def test_reflex_platform_descriptor(reflex_dir: Path) -> None:
    doc = json.loads((reflex_dir / ".platform").read_text(encoding="utf-8"))
    assert doc["metadata"]["type"] == "Reflex"
    assert doc["metadata"]["displayName"] == "PayerOps_Activator"
    assert doc["config"]["logicalId"] == REFLEX_LOGICAL_ID


def test_reflex_parameter_yml_rule(repo_root: Path) -> None:
    text = (repo_root / "workspace" / "parameter.yml").read_text(encoding="utf-8")
    assert REFLEX_LOGICAL_ID in text
    for env in ("DEV", "STAGING", "PROD"):
        assert f"$PAYEROPS_ACTIVATOR_{env}" in text, (
            f"parameter.yml missing $PAYEROPS_ACTIVATOR_{env}"
        )


def test_reflex_in_deployment_optionalitems(repo_root: Path) -> None:
    text = (repo_root / "deployment.yaml").read_text(encoding="utf-8")
    assert "PayerOps_Activator.Reflex" in text, (
        "PayerOps_Activator.Reflex must be listed under deployment.yaml optionalItems "
        "(RTI ships disabled by default)."
    )


@pytest.mark.parametrize("rule_id,spec", list(EXPECTED_RULES.items()))
def test_reflex_rule_design_locked(rule_id: str, spec: dict) -> None:
    """Rule design is the contract C.6 RUNBOOK + the eventual Fabric-side
    Activator configuration must both honor. Drift here means RUNBOOK and
    deployed Activator have diverged.
    """
    assert spec["source_notebook"]
    assert spec["source_kql_var"]
    assert spec["source_table"]
    assert "predicate" in spec and spec["predicate"]
    assert isinstance(spec["thresholds"], dict) and spec["thresholds"]
    for k, v in spec["thresholds"].items():
        assert isinstance(v, int | float), f"{rule_id}: threshold {k} must be numeric"
    assert isinstance(spec["route"], dict)
    assert spec["route"]["channel"]
    assert spec["route"]["work_item"]


def test_pa_rule_references_real_notebook_kql(repo_root: Path) -> None:
    spec = EXPECTED_RULES["pa_denial_rate_spike"]
    nb = (repo_root / "workspace" / f"{spec['source_notebook']}.Notebook"
          / "notebook-content.py").read_text(encoding="utf-8")
    assert f"{spec['source_kql_var']} =" in nb, (
        f"NB {spec['source_notebook']} must export {spec['source_kql_var']}"
    )
    # The PA-latency notebook's KQL must surface the fields the rule predicates on.
    assert "decisions" in nb
    assert "breach_rate" in nb


def test_siu_rule_references_real_notebook_kql(repo_root: Path) -> None:
    spec = EXPECTED_RULES["siu_intake_score_alert"]
    nb = (repo_root / "workspace" / f"{spec['source_notebook']}.Notebook"
          / "notebook-content.py").read_text(encoding="utf-8")
    assert f"{spec['source_kql_var']} =" in nb
    # The SIU notebook's KQL must emit intake_score so the rule's predicate is meaningful.
    assert "intake_score" in nb


def test_pa_rule_regulatory_citation_resolves(repo_root: Path) -> None:
    """PA-denial-rate-spike cites CMS-0057-F as its compliance hook.
    Must resolve in citations.yaml.
    """
    import yaml
    citations = yaml.safe_load(
        (repo_root / "citations.yaml").read_text(encoding="utf-8")
    )
    ids = {c["id"] for c in citations["citations"]}
    cit = EXPECTED_RULES["pa_denial_rate_spike"]["regulatory_hook"]
    assert cit in ids, f"citations.yaml missing {cit!r}"

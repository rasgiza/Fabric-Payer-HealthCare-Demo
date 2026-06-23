"""Shape tests for the RTI C.3 skeleton: 3 KQL analytic notebooks.

C.3 lands three persona-scoped notebooks that read/write `kqldb_payer_rt`:
  - NB_RTI_02_PA_Latency       (UM, CMS-0057-F)
  - NB_RTI_03_ADT_Outreach     (CareMgmt)
  - NB_RTI_04_SIU_Intake_Scoring (SIU)

Each notebook ships .platform + notebook-content.py with the same dry_run
safety convention as NB_RTI_01: parameter defaults are publishable as-is
(no live Eventhouse required), and the cross-cutting schemas + KQL queries
are pinned by this test so C.4 Activator rules and C.6 RUNBOOK can lift
the literals verbatim without drifting.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

C3_NOTEBOOKS = {
    "NB_RTI_02_PA_Latency": {
        "logical_id": "b3000003-0001-0001-0001-000000000006",
        "schema_var": "AUTH_LIFECYCLE_COLUMNS",
        "schema":     [
            "auth_id", "member_id", "provider_id", "service_category",
            "requested_at", "decided_at", "decision", "is_expedited",
            "latency_hours",
        ],
        "kql_var":     "PA_LATENCY_KQL",
        "kql_keywords": ["auth_lifecycle", "is_expedited", "latency_hours",
                         "breach_rate", "percentile"],
        "param_defaults": {
            "run_id": "smoke", "event_count": 2000, "lookback_min": 240,
            "seed": 42, "kql_cluster_uri": "", "kql_database": "kqldb_payer_rt",
            "kql_table": "auth_lifecycle", "dry_run": True,
        },
    },
    "NB_RTI_03_ADT_Outreach": {
        "logical_id": "b3000003-0001-0001-0001-000000000007",
        "schema_var": "ADT_ADMISSION_COLUMNS",
        "schema":     [
            "adt_event_id", "member_id", "facility_id", "event_at",
            "event_type", "admit_source", "primary_dx_chapter",
            "expected_los_days",
        ],
        "kql_var":     "ADT_OUTREACH_KQL",
        "kql_keywords": ["adt_admissions", "member_outreach", "leftanti",
                         "emergency", "priority"],
        "param_defaults": {
            "run_id": "smoke", "event_count": 1500, "lookback_min": 180,
            "seed": 42, "kql_cluster_uri": "", "kql_database": "kqldb_payer_rt",
            "kql_table": "adt_admissions", "dry_run": True,
        },
    },
    "NB_RTI_04_SIU_Intake_Scoring": {
        "logical_id": "b3000003-0001-0001-0001-000000000008",
        "schema_var": "SIU_SCORE_COLUMNS",
        "schema":     [
            "claim_id", "arrived_at", "payer_id", "provider_id", "member_id",
            "billed_amount", "intake_score", "score_reasons",
        ],
        "kql_var":     "SIU_SCORING_KQL",
        "kql_keywords": ["claim_arrivals", "intake_score", "score_reasons",
                         "fax_ocr", "prior_auth_present"],
        "param_defaults": {
            # NB_RTI_04 deliberately does NOT seed its own data; it reads
            # claim_arrivals which NB_RTI_01 + es_claims_arrivals populate.
            "lookback_min": 60, "score_threshold": 0.6, "kql_cluster_uri": "",
            "kql_database": "kqldb_payer_rt", "dry_run": True,
        },
    },
}


@pytest.fixture
def workspace_dir(repo_root: Path) -> Path:
    return repo_root / "workspace"


def _nb_dir(workspace_dir: Path, nb: str) -> Path:
    return workspace_dir / f"{nb}.Notebook"


def _read_platform(folder: Path) -> dict:
    return json.loads((folder / ".platform").read_text(encoding="utf-8"))


def _parse_assignments(source: str) -> dict[str, object]:
    """Return top-level `name = literal` assignments.

    Handles the `"...".strip()` idiom by folding `.strip()` away (trailing
    whitespace does not affect the semantic KQL lock).
    """
    tree = ast.parse(source)
    out: dict[str, object] = {}
    for node in tree.body:
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            continue
        value = node.value
        # Unwrap `<expr>.strip()` so we can literal-eval the underlying string.
        while (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr == "strip"
            and not value.args
            and not value.keywords
        ):
            value = value.func.value
        try:
            out[node.targets[0].id] = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            pass
    return out


@pytest.mark.parametrize("nb", list(C3_NOTEBOOKS))
def test_c3_notebook_folder_shape(workspace_dir: Path, nb: str) -> None:
    d = _nb_dir(workspace_dir, nb)
    assert d.is_dir(), f"missing folder {d}"
    children = sorted(p.name for p in d.iterdir())
    assert children == [".platform", "notebook-content.py"], (
        f"{nb}: unexpected files {children}"
    )


@pytest.mark.parametrize("nb", list(C3_NOTEBOOKS))
def test_c3_notebook_platform_descriptor(workspace_dir: Path, nb: str) -> None:
    doc = _read_platform(_nb_dir(workspace_dir, nb))
    assert doc["metadata"]["type"] == "Notebook"
    assert doc["metadata"]["displayName"] == nb
    assert doc["config"]["logicalId"] == C3_NOTEBOOKS[nb]["logical_id"]


@pytest.mark.parametrize("nb", list(C3_NOTEBOOKS))
def test_c3_notebook_parameter_defaults(workspace_dir: Path, nb: str) -> None:
    """Parameter defaults are the publisher-safety contract: each notebook
    must be runnable end-to-end after publish without a live Eventhouse."""
    src = (_nb_dir(workspace_dir, nb) / "notebook-content.py").read_text(encoding="utf-8")
    assigns = _parse_assignments(src)
    for name, expected in C3_NOTEBOOKS[nb]["param_defaults"].items():
        assert name in assigns, f"{nb}: missing parameter {name!r}"
        assert assigns[name] == expected, (
            f"{nb}: parameter {name!r} expected {expected!r}, got {assigns[name]!r}"
        )


@pytest.mark.parametrize("nb", list(C3_NOTEBOOKS))
def test_c3_notebook_dry_run_default_is_safe(workspace_dir: Path, nb: str) -> None:
    src = (_nb_dir(workspace_dir, nb) / "notebook-content.py").read_text(encoding="utf-8")
    assigns = _parse_assignments(src)
    assert assigns.get("dry_run") is True, (
        f"{nb}: dry_run default must remain True; see notebook docstring"
    )


@pytest.mark.parametrize("nb", list(C3_NOTEBOOKS))
def test_c3_notebook_locked_schema(workspace_dir: Path, nb: str) -> None:
    """C.4 Activator rules + C.6 RUNBOOK lift these column lists verbatim."""
    src = (_nb_dir(workspace_dir, nb) / "notebook-content.py").read_text(encoding="utf-8")
    assigns = _parse_assignments(src)
    var = C3_NOTEBOOKS[nb]["schema_var"]
    expected = C3_NOTEBOOKS[nb]["schema"]
    assert var in assigns, f"{nb}: missing {var}"
    assert assigns[var] == expected, (
        f"{nb}: {var} drift\n  expected: {expected}\n  actual:   {assigns[var]}"
    )


@pytest.mark.parametrize("nb", list(C3_NOTEBOOKS))
def test_c3_notebook_kql_query_present(workspace_dir: Path, nb: str) -> None:
    """KQL string literals are the contract C.4 Activator predicates lift;
    we don't run KQL in CI but we lock that the query exists + names the
    expected tables/columns so semantic drift is caught at PR time."""
    src = (_nb_dir(workspace_dir, nb) / "notebook-content.py").read_text(encoding="utf-8")
    assigns = _parse_assignments(src)
    var = C3_NOTEBOOKS[nb]["kql_var"]
    assert var in assigns, f"{nb}: missing {var}"
    kql = assigns[var]
    assert isinstance(kql, str) and kql.strip(), f"{nb}: {var} must be a non-empty string"
    for kw in C3_NOTEBOOKS[nb]["kql_keywords"]:
        assert kw in kql, f"{nb}: {var} missing expected keyword {kw!r}"


def test_c3_items_have_parameter_yml_rules(repo_root: Path) -> None:
    text = (repo_root / "workspace" / "parameter.yml").read_text(encoding="utf-8")
    for nb, info in C3_NOTEBOOKS.items():
        assert info["logical_id"] in text, (
            f"parameter.yml missing find_value for {nb}"
        )
        upper = nb.upper()
        for env in ("DEV", "STAGING", "PROD"):
            var = f"${upper}_{env}"
            assert var in text, f"parameter.yml missing replace_value {var}"

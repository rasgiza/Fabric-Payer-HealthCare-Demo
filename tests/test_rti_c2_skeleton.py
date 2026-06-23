"""Shape tests for the RTI C.2 skeleton: Eventstream + ingest notebook.

C.2 lands two new workspace items:
  - `es_claims_arrivals.Eventstream` (.platform-only; companion JSON deferred
    to C.3 once we've observed a real Fabric Git export of an Eventstream)
  - `NB_RTI_01_Ingest_Claims_Stream.Notebook` (.platform + notebook-content.py)

These tests guard the contract C.2 establishes. Cross-item invariants
(uniqueness, prefix table, inventory count) live in
`test_workspace_logical_ids.py`; generic notebook checks live in
`test_notebook_shape.py`. This file holds C.2-specific assertions only.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

ES_DIR = "es_claims_arrivals.Eventstream"
ES_LOGICAL_ID = "08000008-0001-0001-0001-000000000001"

NB_DIR = "NB_RTI_01_Ingest_Claims_Stream.Notebook"
NB_LOGICAL_ID = "b3000003-0001-0001-0001-000000000005"

EXPECTED_PARAM_DEFAULTS = {
    "run_id":          "smoke",
    "event_count":     5000,
    "lookback_min":    60,
    "seed":            42,
    "kql_cluster_uri": "",
    "kql_database":    "kqldb_payer_rt",
    "kql_table":       "claim_arrivals",
    "dry_run":         True,
}

# Locked event schema -- ingest notebook, Eventhouse table DDL (C.3),
# and Activator rule predicates (C.4) all reference these column names.
EXPECTED_CLAIM_ARRIVAL_COLUMNS = [
    "claim_id",
    "arrived_at",
    "payer_id",
    "provider_id",
    "member_id",
    "billed_amount",
    "service_line_count",
    "claim_type",
    "submission_channel",
    "prior_auth_present",
]


@pytest.fixture
def workspace_dir(repo_root: Path) -> Path:
    return repo_root / "workspace"


def _read_platform(folder: Path) -> dict:
    return json.loads((folder / ".platform").read_text(encoding="utf-8"))


# ----- Eventstream -----------------------------------------------------------

def test_eventstream_folder_minimal_shape(workspace_dir: Path) -> None:
    d = workspace_dir / ES_DIR
    assert d.is_dir(), f"missing folder {d}"
    children = sorted(p.name for p in d.iterdir())
    # C.2 ships .platform-only; companion JSON (eventstreamProperties.json,
    # topology, sources/destinations) lands once we have a real Fabric Git
    # export to model the shape from.
    assert children == [".platform"], (
        f"{ES_DIR}: unexpected companion files {children}; "
        "C.2 ships .platform-only"
    )


def test_eventstream_platform_descriptor(workspace_dir: Path) -> None:
    doc = _read_platform(workspace_dir / ES_DIR)
    assert doc["metadata"]["type"] == "Eventstream"
    assert doc["metadata"]["displayName"] == "es_claims_arrivals"
    assert doc["config"]["logicalId"] == ES_LOGICAL_ID


# ----- Ingest notebook -------------------------------------------------------

def test_ingest_notebook_folder_shape(workspace_dir: Path) -> None:
    d = workspace_dir / NB_DIR
    assert d.is_dir(), f"missing folder {d}"
    children = sorted(p.name for p in d.iterdir())
    assert children == [".platform", "notebook-content.py"], (
        f"{NB_DIR}: unexpected files {children}"
    )


def test_ingest_notebook_platform_descriptor(workspace_dir: Path) -> None:
    doc = _read_platform(workspace_dir / NB_DIR)
    assert doc["metadata"]["type"] == "Notebook"
    assert doc["metadata"]["displayName"] == "NB_RTI_01_Ingest_Claims_Stream"
    assert doc["config"]["logicalId"] == NB_LOGICAL_ID


def _parse_assignments(source: str) -> dict[str, object]:
    """Return top-level `name = literal` assignments from a notebook .py source."""
    tree = ast.parse(source)
    out: dict[str, object] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                pass
    return out


def test_ingest_notebook_parameter_defaults(workspace_dir: Path) -> None:
    """Parameter defaults are part of the launcher contract -- they get
    overridden by the launcher / pipeline at runtime. Drift here breaks
    callers silently, so the defaults are locked."""
    src = (workspace_dir / NB_DIR / "notebook-content.py").read_text(encoding="utf-8")
    assigns = _parse_assignments(src)
    for name, expected in EXPECTED_PARAM_DEFAULTS.items():
        assert name in assigns, f"parameter {name!r} missing from notebook"
        assert assigns[name] == expected, (
            f"parameter {name!r}: expected default {expected!r}, got {assigns[name]!r}"
        )


def test_ingest_notebook_claim_arrival_columns(workspace_dir: Path) -> None:
    """CLAIM_ARRIVAL_COLUMNS is the cross-cutting event schema; C.3 KQL DDL
    and C.4 Activator predicates lift this list verbatim, so drift here would
    silently break those downstream items."""
    src = (workspace_dir / NB_DIR / "notebook-content.py").read_text(encoding="utf-8")
    assigns = _parse_assignments(src)
    assert "CLAIM_ARRIVAL_COLUMNS" in assigns, "missing CLAIM_ARRIVAL_COLUMNS in notebook"
    assert assigns["CLAIM_ARRIVAL_COLUMNS"] == EXPECTED_CLAIM_ARRIVAL_COLUMNS, (
        "CLAIM_ARRIVAL_COLUMNS drift -- update either the notebook or this test, "
        f"not just one\n  expected: {EXPECTED_CLAIM_ARRIVAL_COLUMNS}\n"
        f"  actual:   {assigns['CLAIM_ARRIVAL_COLUMNS']}"
    )


def test_ingest_notebook_dry_run_default_is_safe(workspace_dir: Path) -> None:
    """`dry_run=True` keeps the notebook publishable before the live Eventhouse
    cluster URI is wired up; flipping this default would cause a publish-time
    notebook execution to attempt a Kusto write against an empty URI."""
    src = (workspace_dir / NB_DIR / "notebook-content.py").read_text(encoding="utf-8")
    assigns = _parse_assignments(src)
    assert assigns.get("dry_run") is True, (
        "dry_run default must remain True; see notebook docstring for rationale"
    )


# ----- parameter.yml ---------------------------------------------------------

def test_rti_c2_items_have_parameter_yml_rules(repo_root: Path) -> None:
    text = (repo_root / "workspace" / "parameter.yml").read_text(encoding="utf-8")
    for lid in (ES_LOGICAL_ID, NB_LOGICAL_ID):
        assert lid in text, f"parameter.yml missing find_value for {lid}"
    for var in (
        "$ES_CLAIMS_ARRIVALS_DEV", "$ES_CLAIMS_ARRIVALS_STAGING", "$ES_CLAIMS_ARRIVALS_PROD",
        "$NB_RTI_01_INGEST_CLAIMS_STREAM_DEV",
        "$NB_RTI_01_INGEST_CLAIMS_STREAM_STAGING",
        "$NB_RTI_01_INGEST_CLAIMS_STREAM_PROD",
    ):
        assert var in text, f"parameter.yml missing replace_value {var}"

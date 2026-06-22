"""Shape tests for the RTI C.1 skeleton: Eventhouse + KQLDatabase.

C.1 lands only the .platform descriptors for the two RTI parent items. Data
ingest (C.2) and analytic notebooks (C.3) are intentionally not in this
commit; these tests guard the contract C.1 establishes:

    - both folders exist with a single `.platform` file (no stale companion
      JSON that fabric-cicd might try to publish before it's wired up)
    - logicalIds use the new `e6...` / `f7...` namespaces reserved in Stream A
    - displayName matches folder stem
    - parameter.yml has a rewrite rule for each

`test_workspace_logical_ids.py` already enforces the cross-item invariants
(uniqueness, prefix table, inventory count); these tests are item-specific.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

EH_DIR = "eh_payer_rt.Eventhouse"
EH_LOGICAL_ID = "e6000006-0001-0001-0001-000000000001"

KQL_DIR = "kqldb_payer_rt.KQLDatabase"
KQL_LOGICAL_ID = "f7000007-0001-0001-0001-000000000001"


@pytest.fixture
def workspace_dir(repo_root: Path) -> Path:
    return repo_root / "workspace"


def _read_platform(folder: Path) -> dict:
    return json.loads((folder / ".platform").read_text(encoding="utf-8"))


def test_eventhouse_folder_minimal_shape(workspace_dir: Path) -> None:
    d = workspace_dir / EH_DIR
    assert d.is_dir(), f"missing folder {d}"
    children = sorted(p.name for p in d.iterdir())
    # C.1 intentionally ships .platform-only. C.2 may add EventhouseProperties.json
    # once we've observed a Fabric Git export. Anything else here is unexpected.
    assert children == [".platform"], (
        f"{EH_DIR}: unexpected companion files {children}; "
        "C.1 ships .platform-only"
    )


def test_eventhouse_platform_descriptor(workspace_dir: Path) -> None:
    doc = _read_platform(workspace_dir / EH_DIR)
    assert doc["metadata"]["type"] == "Eventhouse"
    assert doc["metadata"]["displayName"] == "eh_payer_rt"
    assert doc["config"]["logicalId"] == EH_LOGICAL_ID


def test_kqldatabase_folder_minimal_shape(workspace_dir: Path) -> None:
    d = workspace_dir / KQL_DIR
    assert d.is_dir(), f"missing folder {d}"
    children = sorted(p.name for p in d.iterdir())
    assert children == [".platform"], (
        f"{KQL_DIR}: unexpected companion files {children}; "
        "C.1 ships .platform-only"
    )


def test_kqldatabase_platform_descriptor(workspace_dir: Path) -> None:
    doc = _read_platform(workspace_dir / KQL_DIR)
    assert doc["metadata"]["type"] == "KQLDatabase"
    assert doc["metadata"]["displayName"] == "kqldb_payer_rt"
    assert doc["config"]["logicalId"] == KQL_LOGICAL_ID


def test_rti_items_have_parameter_yml_rules(repo_root: Path) -> None:
    """parameter.yml must rewrite both RTI logicalIds (CI/CD install path)."""
    text = (repo_root / "workspace" / "parameter.yml").read_text(encoding="utf-8")
    for lid in (EH_LOGICAL_ID, KQL_LOGICAL_ID):
        assert lid in text, f"parameter.yml missing find_value for {lid}"
    # The dev/staging/prod env-var names must follow the established convention.
    for var in ("$EH_PAYER_RT_DEV", "$EH_PAYER_RT_STAGING", "$EH_PAYER_RT_PROD",
                "$KQLDB_PAYER_RT_DEV", "$KQLDB_PAYER_RT_STAGING", "$KQLDB_PAYER_RT_PROD"):
        assert var in text, f"parameter.yml missing replace_value {var}"

"""Locks the Fabric workspace skeleton (Stream A.1).

Every lakehouse in the medallion (bronze / silver_stage / silver_ods /
gold_curated) must ship a Git-Integration v2.0 `.platform` descriptor with
a stable logicalId; the deployment manifest and the parameter file must
both reference each one. Drift between these three files is the most common
cause of fabric-cicd `LogicalIdNotFound` failures at deploy time, so we
catch it at PR time.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

EXPECTED_LAKEHOUSES = [
    "lh_bronze_raw",
    "lh_silver_stage",
    "lh_silver_ods",
    "lh_gold_curated",
]


@pytest.fixture(scope="module")
def workspace_dir(repo_root: Path) -> Path:
    p = repo_root / "workspace"
    assert p.is_dir(), "workspace/ skeleton missing"
    return p


def test_all_four_lakehouses_present(workspace_dir: Path) -> None:
    for name in EXPECTED_LAKEHOUSES:
        platform = workspace_dir / f"{name}.Lakehouse" / ".platform"
        assert platform.is_file(), f"missing .platform for {name}"


def test_platform_descriptors_are_valid(workspace_dir: Path) -> None:
    logical_ids: dict[str, str] = {}
    for name in EXPECTED_LAKEHOUSES:
        platform = workspace_dir / f"{name}.Lakehouse" / ".platform"
        doc = json.loads(platform.read_text(encoding="utf-8"))
        assert doc["metadata"]["type"] == "Lakehouse"
        assert doc["metadata"]["displayName"] == name
        lid = doc["config"]["logicalId"]
        assert isinstance(lid, str) and len(lid) == 36
        logical_ids[name] = lid

    # logicalIds must be unique across the skeleton
    assert len(set(logical_ids.values())) == len(logical_ids), (
        f"duplicate logicalId across lakehouses: {logical_ids}"
    )


def test_deployment_manifest_lists_lakehouse(repo_root: Path) -> None:
    manifest = repo_root / "deployment.yaml"
    assert manifest.is_file(), "deployment.yaml missing at repo root"
    doc = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    assert doc["kind"] == "FabricDeployment"
    item_order = doc["spec"]["itemOrder"]
    # Lakehouse must be deployed before anything that references it
    assert item_order[0] == "Lakehouse", (
        f"Lakehouse must be first in itemOrder, got: {item_order}"
    )
    for downstream in ("Notebook", "SemanticModel", "Report", "DataAgent"):
        assert downstream in item_order, (
            f"{downstream} must appear in deployment.yaml itemOrder"
        )


def test_parameter_file_covers_every_lakehouse(repo_root: Path, workspace_dir: Path) -> None:
    param_path = workspace_dir / "parameter.yml"
    assert param_path.is_file(), "workspace/parameter.yml missing"
    doc = yaml.safe_load(param_path.read_text(encoding="utf-8"))
    rules = doc.get("find_replace", [])
    referenced = {r["find_value"] for r in rules}

    for name in EXPECTED_LAKEHOUSES:
        platform = workspace_dir / f"{name}.Lakehouse" / ".platform"
        lid = json.loads(platform.read_text(encoding="utf-8"))["config"]["logicalId"]
        assert lid in referenced, (
            f"parameter.yml has no find/replace block for {name} (logicalId {lid})"
        )

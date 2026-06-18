"""Locks Fabric DataPipeline shape under workspace/ (Stream A.3).

For every `.DataPipeline` item we ship, we want to catch at PR time:
- `.platform` exists, type=DataPipeline, displayName matches folder name
- logicalIds unique across pipelines (and disjoint from lakehouse/notebook namespaces)
- `pipeline-content.json` parses and has the expected `properties.activities` shape
- Every TridentNotebook activity references a logicalId that actually exists
  under workspace/<displayName>.Notebook/.platform (drift catch)
- Every ExecutePipeline activity references a logicalId that actually exists
  under workspace/<displayName>.DataPipeline/.platform (drift catch)
- PL_Payer_Full_Load chains exactly NB_01 -> NB_02 -> NB_03 in order
- PL_Payer_Master only references PL_Payer_Full_Load
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

EXPECTED_PIPELINES = [
    "PL_Payer_Full_Load",
    "PL_Payer_Master",
]

LAKEHOUSE_PREFIX = "a2000002-"
NOTEBOOK_PREFIX = "b3000003-"
PIPELINE_PREFIX = "c4000004-"


@pytest.fixture(scope="module")
def workspace_dir(repo_root: Path) -> Path:
    return repo_root / "workspace"


def _logicalid_index(workspace_dir: Path) -> dict[str, dict[str, str]]:
    """Returns {item_type: {logicalId: displayName}} for every .platform we ship."""
    index: dict[str, dict[str, str]] = {}
    for plat in workspace_dir.glob("*/.platform"):
        doc = json.loads(plat.read_text(encoding="utf-8"))
        t = doc["metadata"]["type"]
        index.setdefault(t, {})[doc["config"]["logicalId"]] = doc["metadata"]["displayName"]
    return index


def test_all_pipelines_present(workspace_dir: Path) -> None:
    names = {p.name for p in workspace_dir.glob("*.DataPipeline")}
    for pl in EXPECTED_PIPELINES:
        assert f"{pl}.DataPipeline" in names, f"missing {pl}.DataPipeline"


def test_pipeline_files_exist(workspace_dir: Path) -> None:
    for pl in EXPECTED_PIPELINES:
        d = workspace_dir / f"{pl}.DataPipeline"
        assert (d / ".platform").is_file(), f"{pl}: missing .platform"
        assert (d / "pipeline-content.json").is_file(), f"{pl}: missing pipeline-content.json"


def test_platform_descriptors_consistent(workspace_dir: Path) -> None:
    seen: dict[str, str] = {}
    for pl in EXPECTED_PIPELINES:
        doc = json.loads((workspace_dir / f"{pl}.DataPipeline" / ".platform").read_text(encoding="utf-8"))
        assert doc["metadata"]["type"] == "DataPipeline"
        assert doc["metadata"]["displayName"] == pl
        lid = doc["config"]["logicalId"]
        assert lid.startswith(PIPELINE_PREFIX), (
            f"{pl}: logicalId {lid} must use pipeline namespace {PIPELINE_PREFIX}*"
        )
        assert lid not in seen, f"duplicate logicalId {lid} between {seen.get(lid)} and {pl}"
        seen[lid] = pl


def test_logicalid_namespaces_disjoint(workspace_dir: Path) -> None:
    index = _logicalid_index(workspace_dir)
    all_ids: dict[str, str] = {}
    for kind, m in index.items():
        for lid, name in m.items():
            assert lid not in all_ids, (
                f"logicalId {lid} reused between {all_ids[lid]} and {kind}/{name}"
            )
            all_ids[lid] = f"{kind}/{name}"


def _iter_activities(activities: list) -> list:
    """Flatten activities including those nested inside IfCondition branches."""
    out: list = []
    for act in activities:
        out.append(act)
        if act.get("type") == "IfCondition":
            tp = act.get("typeProperties", {})
            out.extend(_iter_activities(tp.get("ifTrueActivities", [])))
            out.extend(_iter_activities(tp.get("ifFalseActivities", [])))
    return out


def test_pipeline_activity_references_resolve(workspace_dir: Path) -> None:
    index = _logicalid_index(workspace_dir)
    notebook_ids = set(index.get("Notebook", {}).keys())
    pipeline_ids = set(index.get("DataPipeline", {}).keys())

    for pl in EXPECTED_PIPELINES:
        doc = json.loads((workspace_dir / f"{pl}.DataPipeline" / "pipeline-content.json").read_text(encoding="utf-8"))
        activities = _iter_activities(doc["properties"]["activities"])
        for act in activities:
            t = act.get("type")
            if t == "TridentNotebook":
                nb_id = act["typeProperties"]["notebookId"]
                assert nb_id in notebook_ids, (
                    f"{pl}/{act['name']}: notebookId {nb_id} has no matching workspace/*.Notebook/.platform"
                )
            elif t == "ExecutePipeline":
                ref = act["typeProperties"]["pipeline"]["referenceName"]
                assert ref in pipeline_ids, (
                    f"{pl}/{act['name']}: ExecutePipeline ref {ref} has no matching workspace/*.DataPipeline/.platform"
                )


def test_full_load_chains_three_notebooks_in_order(workspace_dir: Path) -> None:
    doc = json.loads((workspace_dir / "PL_Payer_Full_Load.DataPipeline" / "pipeline-content.json").read_text(encoding="utf-8"))
    nb_activities = [a for a in doc["properties"]["activities"] if a.get("type") == "TridentNotebook"]
    assert [a["name"] for a in nb_activities] == [
        "NB_01_Bronze_Ingest",
        "NB_02_Silver_Transform",
        "NB_03_Gold_Build",
    ]

    # Verify the dependsOn chain is strictly linear (each step depends only on the prior)
    assert nb_activities[0]["dependsOn"][0]["activity"] == "Set_Bronze_Mode"
    assert nb_activities[1]["dependsOn"][0]["activity"] == "NB_01_Bronze_Ingest"
    assert nb_activities[2]["dependsOn"][0]["activity"] == "NB_02_Silver_Transform"


def test_master_only_references_full_load(workspace_dir: Path) -> None:
    full_load_lid = json.loads(
        (workspace_dir / "PL_Payer_Full_Load.DataPipeline" / ".platform").read_text(encoding="utf-8")
    )["config"]["logicalId"]

    doc = json.loads((workspace_dir / "PL_Payer_Master.DataPipeline" / "pipeline-content.json").read_text(encoding="utf-8"))
    refs = [
        a["typeProperties"]["pipeline"]["referenceName"]
        for a in _iter_activities(doc["properties"]["activities"])
        if a.get("type") == "ExecutePipeline"
    ]
    assert refs, "PL_Payer_Master has no ExecutePipeline activities"
    assert set(refs) == {full_load_lid}, (
        f"PL_Payer_Master must reference only PL_Payer_Full_Load ({full_load_lid}); got {refs}"
    )

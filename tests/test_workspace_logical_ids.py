"""Repo-wide governance for `.platform` manifests in `workspace/`.

`test_workspace_skeleton.py` enforces uniqueness across the 4 lakehouses only.
This file extends that guarantee to every `.platform` file in the workspace
skeleton (currently 22: 4 Lakehouse + 5 Notebook + 2 DataPipeline + 1
SemanticModel + 1 Ontology + 7 DataAgent).

Regressions this catches:
  - Copy-pasting a Notebook folder without bumping its logicalId, which would
    cause fabric-cicd to overwrite the original on publish.
  - displayName drifting from the folder stem (also enforced by tools/deploy.py
    at publish-time, but cheaper to catch in CI).
  - LogicalIds that don't match the type-namespace convention this repo uses,
    which makes the parameter.yml `find_replace` blocks unreadable to humans.
  - A folder under workspace/ that has no `.platform` (dead folder regression).

Type-namespace prefix convention (assigned per Fabric item type, NOT per
fabric-cicd `SUPPORTED_TYPES` ordering):
  a2000002-  Lakehouse
  b3000003-  Notebook
  c4000004-  DataPipeline
  d5000005-  SemanticModel, Ontology, DataAgent
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PREFIX_BY_TYPE = {
    "Lakehouse": "a2000002-",
    "Notebook": "b3000003-",
    "DataPipeline": "c4000004-",
    "SemanticModel": "d5000005-",
    "Ontology": "d5000005-",
    "DataAgent": "d5000005-",
    "Eventhouse": "e6000006-",
    "KQLDatabase": "f7000007-",
}


def _all_platform_files(workspace_dir: Path) -> list[Path]:
    return sorted(workspace_dir.glob("*/.platform"))


@pytest.fixture(scope="module")
def workspace_dir(repo_root: Path) -> Path:
    p = repo_root / "workspace"
    assert p.is_dir(), "workspace/ skeleton missing"
    return p


def test_every_workspace_folder_has_a_platform(workspace_dir: Path) -> None:
    """A folder under workspace/ with no `.platform` is almost always dead code."""
    item_folders = [
        d for d in workspace_dir.iterdir()
        if d.is_dir() and "." in d.name  # `<Name>.<ItemType>` convention
    ]
    missing = [d.name for d in item_folders if not (d / ".platform").is_file()]
    assert not missing, (
        f"workspace/ folders without a .platform manifest (likely orphaned): {missing}"
    )


def test_every_logical_id_is_unique_repo_wide(workspace_dir: Path) -> None:
    """No two committed `.platform` files may share a logicalId.

    fabric-cicd uses logicalId as the cross-environment identity key; duplicates
    cause silent overwrites at deploy time.
    """
    seen: dict[str, str] = {}
    duplicates: list[tuple[str, str, str]] = []
    for p in _all_platform_files(workspace_dir):
        doc = json.loads(p.read_text(encoding="utf-8"))
        lid = doc["config"]["logicalId"]
        folder = p.parent.name
        if lid in seen:
            duplicates.append((lid, seen[lid], folder))
        else:
            seen[lid] = folder
    assert not duplicates, (
        "duplicate logicalId(s) across workspace/:\n"
        + "\n".join(f"  {lid} shared by {a!r} and {b!r}" for lid, a, b in duplicates)
    )


def test_display_name_matches_folder_stem(workspace_dir: Path) -> None:
    """tools/deploy.py rejects this at publish-time; we catch it earlier."""
    mismatches: list[tuple[str, str, str]] = []
    for p in _all_platform_files(workspace_dir):
        doc = json.loads(p.read_text(encoding="utf-8"))
        folder = p.parent.name
        stem = folder.rsplit(".", 1)[0]
        dn = doc["metadata"]["displayName"]
        if dn != stem:
            mismatches.append((folder, stem, dn))
    assert not mismatches, (
        "displayName does not match folder stem:\n"
        + "\n".join(f"  {f}: stem={s!r} displayName={d!r}" for f, s, d in mismatches)
    )


def test_logical_ids_follow_type_namespace_convention(workspace_dir: Path) -> None:
    """Each item type uses a predictable prefix so parameter.yml is human-readable.

    If a new item type is introduced, extend `PREFIX_BY_TYPE` above (and this
    test will tell you exactly which folder is unmapped).
    """
    violations: list[tuple[str, str, str, str]] = []
    for p in _all_platform_files(workspace_dir):
        doc = json.loads(p.read_text(encoding="utf-8"))
        item_type = doc["metadata"]["type"]
        lid = doc["config"]["logicalId"]
        folder = p.parent.name
        expected_prefix = PREFIX_BY_TYPE.get(item_type)
        if expected_prefix is None:
            violations.append((folder, item_type, lid, "<no prefix registered>"))
        elif not lid.startswith(expected_prefix):
            violations.append((folder, item_type, lid, expected_prefix))
    assert not violations, (
        "logicalId does not follow type-namespace convention:\n"
        + "\n".join(
            f"  {f} (type={t}): {lid!r} should start with {prefix!r}"
            for f, t, lid, prefix in violations
        )
    )


def test_expected_workspace_inventory(workspace_dir: Path) -> None:
    """Inventory lock: 22 items today. Bump this when you add a new workspace item.

    Stream A (deployment.yaml + parameter.yml) and tools/deploy.py SUPPORTED_TYPES
    must move together; this test forces the author of a new item to think about
    both.
    """
    counts: dict[str, int] = {}
    for p in _all_platform_files(workspace_dir):
        doc = json.loads(p.read_text(encoding="utf-8"))
        t = doc["metadata"]["type"]
        counts[t] = counts.get(t, 0) + 1
    expected = {
        "Lakehouse": 4,
        "Notebook": 5,
        "DataPipeline": 2,
        "SemanticModel": 1,
        "Ontology": 1,
        "DataAgent": 7,
        "Eventhouse": 1,
        "KQLDatabase": 1,
    }
    assert counts == expected, (
        f"workspace inventory drift\n  expected: {expected}\n  actual:   {counts}"
    )

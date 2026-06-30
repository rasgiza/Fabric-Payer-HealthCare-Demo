"""Locks Fabric notebook shape under workspace/ (Stream A.2).

For every `.Notebook` item we ship, we want to catch at PR time:
- `.platform` exists, type=Notebook, displayName matches folder name
- logicalIds are unique across the workspace
- `notebook-content.py` starts with the magic `# Fabric notebook source` header
  (fabric-cicd refuses to publish files that don't)
- Every notebook has at least one CELL marker
- For NB_01_Bronze_Ingest the in-notebook BRONZE_TABLES list matches
  tools/run_local_etl.py BRONZE_TABLES (drift would silently miss columns)
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

EXPECTED_NOTEBOOKS = [
    "NB_00_Generate_Smoke_Data",
    "NB_01_Bronze_Ingest",
    "NB_02_Silver_Transform",
    "NB_03_Gold_Build",
    "NB_RTI_01_Ingest_Claims_Stream",
    "NB_RTI_02_PA_Latency",
    "NB_RTI_03_ADT_Outreach",
    "NB_RTI_04_SIU_Intake_Scoring",
]


@pytest.fixture(scope="module")
def workspace_dir(repo_root: Path) -> Path:
    return repo_root / "workspace"


def _notebook_dirs(workspace_dir: Path) -> list[Path]:
    return sorted(workspace_dir.glob("*.Notebook"))


def test_all_three_notebooks_present(workspace_dir: Path) -> None:
    names = {p.name for p in _notebook_dirs(workspace_dir)}
    for nb in EXPECTED_NOTEBOOKS:
        assert f"{nb}.Notebook" in names, f"missing {nb}.Notebook"


def test_platform_and_content_files_exist(workspace_dir: Path) -> None:
    for nb in EXPECTED_NOTEBOOKS:
        d = workspace_dir / f"{nb}.Notebook"
        assert (d / ".platform").is_file(), f"{nb}: missing .platform"
        assert (d / "notebook-content.py").is_file(), f"{nb}: missing notebook-content.py"


def test_platform_descriptors_consistent(workspace_dir: Path) -> None:
    seen: dict[str, str] = {}
    for nb in EXPECTED_NOTEBOOKS:
        doc = json.loads((workspace_dir / f"{nb}.Notebook" / ".platform").read_text(encoding="utf-8"))
        assert doc["metadata"]["type"] == "Notebook"
        assert doc["metadata"]["displayName"] == nb, (
            f"{nb}: .platform displayName mismatch ({doc['metadata']['displayName']!r})"
        )
        lid = doc["config"]["logicalId"]
        assert lid not in seen, f"duplicate logicalId {lid} between {seen.get(lid)} and {nb}"
        seen[lid] = nb


def test_notebook_content_has_fabric_header_and_a_cell(workspace_dir: Path) -> None:
    for nb in EXPECTED_NOTEBOOKS:
        text = (workspace_dir / f"{nb}.Notebook" / "notebook-content.py").read_text(encoding="utf-8")
        assert text.lstrip().startswith("# Fabric notebook source"), (
            f"{nb}: notebook-content.py must start with '# Fabric notebook source'"
        )
        # Accept both Fabric serialisations of the CELL delimiter: the legacy
        # inline `# CELL **{"language":"python"}**` and the canonical export
        # `# CELL ********************` (language carried in the following META
        # block). Either way, at least one code cell must be present.
        assert re.search(r"^# CELL \*\*(\{|\*)", text, flags=re.MULTILINE), (
            f"{nb}: no CELL markers found — fabric-cicd would publish an empty notebook"
        )


def _extract_list_literal(source: str, name: str) -> list[str]:
    """Return the value of the first top-level assignment `name = [...]`."""
    tree = ast.parse(source)
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
            and isinstance(node.value, ast.List | ast.Tuple)
        ):
            return [
                elt.value for elt in node.value.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            ]
    raise AssertionError(f"no top-level list literal {name!r} in source")


def _extract_list_from_notebook(text: str, name: str) -> list[str]:
    # Stitch the file into a single source by stripping fabric markers; the
    # markers begin with `# CELL`, `# METADATA`, `# MARKDOWN`, `# PARAMETERS`.
    return _extract_list_literal(text, name)


def test_bronze_inventory_matches_etl_module(repo_root: Path, workspace_dir: Path) -> None:
    etl_src = (repo_root / "tools" / "run_local_etl.py").read_text(encoding="utf-8")
    etl_tables = _extract_list_literal(etl_src, "BRONZE_TABLES")

    nb_text = (workspace_dir / "NB_01_Bronze_Ingest.Notebook" / "notebook-content.py").read_text(encoding="utf-8")
    nb_tables = _extract_list_from_notebook(nb_text, "BRONZE_TABLES")

    assert nb_tables == etl_tables, (
        "NB_01_Bronze_Ingest BRONZE_TABLES has drifted from tools/run_local_etl.py: "
        f"etl={etl_tables} notebook={nb_tables}"
    )

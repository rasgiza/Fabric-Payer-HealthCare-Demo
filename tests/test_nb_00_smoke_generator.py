"""Shape tests for NB_00_Generate_Smoke_Data.

NB_00 fetches gen_payer_overlay.py + the data/reference/*.csv lookups from
GitHub raw at runtime, so its contract has two halves:

  1. The notebook's BRONZE_TABLES list must match NB_01's BRONZE_TABLES and
     the generator's actual output filenames (verified by
     test_bronze_inventory_matches_etl_module in test_notebook_shape.py,
     covered there for NB_01; this test extends it to NB_00).
  2. The notebook's REFERENCE_CSVS list must match the actual contents of
     data/reference/ so the staging tree the generator looks for is complete.

A regression in either list silently produces a notebook that either misses
tables (NB_01 then crashes on the missing CSV) or that fails to download a
reference file (generator raises NumPy / pandas errors mid-run).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

NB_00_DIR = "NB_00_Generate_Smoke_Data.Notebook"


@pytest.fixture
def workspace_dir(repo_root: Path) -> Path:
    return repo_root / "workspace"


def _read_nb(workspace_dir: Path) -> str:
    return (workspace_dir / NB_00_DIR / "notebook-content.py").read_text(encoding="utf-8")


def _extract_list(source: str, name: str) -> list[str]:
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


def test_nb_00_folder_and_files_exist(workspace_dir: Path) -> None:
    d = workspace_dir / NB_00_DIR
    assert d.is_dir(), f"missing folder {d}"
    assert (d / ".platform").is_file()
    assert (d / "notebook-content.py").is_file()


def test_nb_00_has_parameters_cell_with_defaults(workspace_dir: Path) -> None:
    text = _read_nb(workspace_dir)
    assert "# PARAMETERS CELL" in text, "NB_00: missing PARAMETERS CELL marker"
    # The 6 parameters the launcher passes through must all have defaults so
    # the notebook is runnable standalone.
    for name in ("run_id", "scale", "seed", "github_owner", "github_repo", "github_branch"):
        assert re.search(rf"^{name} = ", text, flags=re.MULTILINE), (
            f"NB_00: parameter {name!r} has no top-level default assignment"
        )


def test_nb_00_bronze_tables_match_nb_01(workspace_dir: Path) -> None:
    nb_00 = _extract_list(_read_nb(workspace_dir), "BRONZE_TABLES")
    nb_01_text = (workspace_dir / "NB_01_Bronze_Ingest.Notebook" / "notebook-content.py").read_text(encoding="utf-8")
    nb_01 = _extract_list(nb_01_text, "BRONZE_TABLES")
    assert nb_00 == nb_01, (
        f"NB_00.BRONZE_TABLES drifts from NB_01.BRONZE_TABLES\n  NB_00: {nb_00}\n  NB_01: {nb_01}"
    )
    assert len(nb_00) == 21, f"expected 21 bronze tables, got {len(nb_00)}"


def test_nb_00_reference_csvs_match_repo(workspace_dir: Path, repo_root: Path) -> None:
    declared = set(_extract_list(_read_nb(workspace_dir), "REFERENCE_CSVS"))
    actual = {p.name for p in (repo_root / "data" / "reference").glob("*.csv")}
    assert declared == actual, (
        f"NB_00.REFERENCE_CSVS drifts from data/reference/\n"
        f"  declared but not on disk: {sorted(declared - actual)}\n"
        f"  on disk but not declared: {sorted(actual - declared)}"
    )


def test_nb_00_fetches_from_github_raw(workspace_dir: Path) -> None:
    text = _read_nb(workspace_dir)
    # urllib + raw.githubusercontent.com is the contract; if either disappears
    # this notebook can't run in a fresh Fabric workspace.
    assert "raw.githubusercontent.com" in text, "NB_00: must fetch via raw.githubusercontent.com"
    assert "urllib.request" in text, "NB_00: must use urllib.request (only stdlib HTTP available pre-pip)"


def test_nb_00_writes_to_bronze_lakehouse_default_path(workspace_dir: Path) -> None:
    text = _read_nb(workspace_dir)
    assert "/lakehouse/default/Files/synth/" in text, (
        "NB_00: must write to /lakehouse/default/Files/synth/<run_id>/ "
        "(NB_01 reads from Files/synth/<run_id>/ relative to default lakehouse)"
    )

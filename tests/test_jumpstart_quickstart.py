"""Locks the Tier 1 Quickstart jumpstart (Phase 5).

Validates the manifest, pre-baked gold parquet, launcher notebook shape, and
README so the smallest deployable slice stays internally consistent and a strict
subset of the full workspace.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

QUICKSTART = "jumpstarts/quickstart"
LAUNCHER = "quickstart_launcher"
SHIPPED_AGENTS = ("CFOAgent", "StarsAgent")


@pytest.fixture(scope="module")
def qs_dir(repo_root: Path) -> Path:
    d = repo_root / "jumpstarts" / "quickstart"
    assert d.is_dir(), "jumpstarts/quickstart missing"
    return d


@pytest.fixture(scope="module")
def manifest(qs_dir: Path) -> dict:
    return yaml.safe_load((qs_dir / "manifest.yaml").read_text(encoding="utf-8"))


def test_validator_passes(repo_root: Path) -> None:
    """The dedicated validator must report zero issues."""
    import tools.validate_jumpstart as vj

    assert vj.validate() == []


def test_manifest_header(manifest: dict) -> None:
    assert manifest["kind"] == "Jumpstart"
    assert manifest["tier"] == 1
    assert manifest["name"] == "quickstart"


def test_manifest_ships_cfo_and_stars_only(manifest: dict) -> None:
    agents = [e["name"] for e in manifest["items"]["data_agents"]]
    assert sorted(agents) == sorted(SHIPPED_AGENTS), (
        "Tier 1 must ship exactly CFOAgent + StarsAgent"
    )


def test_manifest_report_pages_are_executive_and_stars(manifest: dict) -> None:
    pages = manifest["items"]["report"][0]["pages"]
    assert pages == ["01_Executive", "03_StarsQuality"]


def test_gold_tables_are_agent_allowlist_union(repo_root: Path, manifest: dict) -> None:
    """Gold slice must be exactly the union of the two shipped agents' allowlists."""
    union: set[str] = set()
    for agent in SHIPPED_AGENTS:
        b = yaml.safe_load(
            (repo_root / "data_agents" / f"{agent}.DataAgent" / "binding.yaml").read_text(
                encoding="utf-8"
            )
        )
        union |= set(b["fabric_data_agent"]["table_allowlist"])
    assert set(manifest["data"]["tables"]) == union


def test_prebaked_parquet_present_and_exact(repo_root: Path, manifest: dict) -> None:
    gold_dir = repo_root / manifest["data"]["gold_dir"]
    assert gold_dir.is_dir(), f"gold dir missing: {gold_dir}"
    declared = set(manifest["data"]["tables"])
    on_disk = {p.stem for p in gold_dir.glob("*.parquet")}
    assert on_disk == declared, f"parquet mismatch: extra={on_disk - declared} missing={declared - on_disk}"
    # every parquet must be non-trivial (not a zero-byte placeholder)
    for p in gold_dir.glob("*.parquet"):
        assert p.stat().st_size > 0, f"empty parquet: {p.name}"


def test_gold_tables_are_subset_of_full_workspace(repo_root: Path, manifest: dict) -> None:
    """Tier 1 must be a strict subset of the full gold slice (promotion safety)."""
    full = {p.stem for p in (repo_root / "data" / "lakehouse" / "smoke" / "gold").glob("*.parquet")}
    if not full:
        pytest.skip("full smoke gold slice not materialized locally")
    assert set(manifest["data"]["tables"]).issubset(full)


def test_launcher_platform(qs_dir: Path) -> None:
    plat = json.loads((qs_dir / f"{LAUNCHER}.Notebook" / ".platform").read_text(encoding="utf-8"))
    assert plat["metadata"]["type"] == "Notebook"
    assert plat["metadata"]["displayName"] == LAUNCHER
    assert plat["config"]["logicalId"].startswith("b3000003-"), (
        "launcher logicalId must use the notebook namespace"
    )


def test_launcher_shape_and_scope(qs_dir: Path) -> None:
    content = (qs_dir / f"{LAUNCHER}.Notebook" / "notebook-content.py").read_text(encoding="utf-8")
    assert content.startswith("# Fabric notebook source"), "missing fabric header"
    md = content.count('# MARKDOWN **{"language":"markdown"}**')
    py = content.count('# CELL **{"language":"python"}**')
    assert md == 1, f"expected 1 markdown cell, found {md}"
    assert py == 5, f"expected 5 python cells (CONFIG + 4 steps), found {py}"
    # Quickstart loads pre-baked gold, never the medallion chain.
    assert 'AGENT_NAMES = ("CFOAgent", "StarsAgent")' in content
    assert "LOAD_GOLD_DATA" in content
    assert "notebook.run(" not in content, "quickstart must not invoke the ETL chain"


def test_readme_documents_three_use_cases(qs_dir: Path, manifest: dict) -> None:
    readme = (qs_dir / "README.md").read_text(encoding="utf-8")
    ucs = manifest["use_cases"]
    assert len(ucs) == 3, "quickstart must document exactly three use cases"
    for uc in ucs:
        assert uc["id"] in readme, f"README missing use case {uc['id']}"

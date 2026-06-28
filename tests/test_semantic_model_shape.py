"""Locks the PayerAnalytics.SemanticModel shape (Stream B.1).

Drift checks fall into three buckets that each correspond to a real failure
mode at deploy time:

  1. Folder shape — fabric-cicd refuses to import a Direct Lake semantic
     model without `.platform`, `definition.pbism`, and the canonical
     definition/ subtree.
  2. Direct Lake binding — every table must declare a `mode: directLake`
     partition pointing at the `DirectLake - lh_gold_curated` expression,
     and that expression must reference `lh_gold_curated`'s logicalId.
  3. Relationship hygiene — every from/to column referenced in
     relationships.tmdl must exist in the table TMDLs. This is the silent
     killer that surfaces only when the report fails to refresh.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

EXPECTED_GOLD_TABLES = {
    # dims (10)
    "dim_date", "dim_member", "dim_provider", "dim_payer", "dim_lob", "dim_product",
    "dim_diagnosis", "dim_procedure", "dim_drug", "dim_hcc",
    # facts (16)
    "fact_claim", "fact_rx_claim", "fact_auth", "fact_appeal", "fact_premium",
    "fact_member_month", "fact_quality_event", "fact_raf_score",
    "fact_pharmacy_pa", "fact_provider_sanction", "fact_provider_directory_attestation",
    "fact_readmission", "fact_sdoh_assessment", "fact_cahps_response",
    "fact_outreach", "fact_vbc_attribution",
    # aggs (9)
    "agg_denial_by_payer", "agg_mlr_monthly", "agg_pa_tat", "agg_stars_compliance",
    "agg_readmissions", "agg_glp1_pa_yield", "agg_sdoh_burden",
    "agg_health_equity_index_proxy", "agg_oon_directory_inaccuracy",
}

GOLD_LH_LOGICAL_ID = "a2000002-0001-0001-0001-000000000004"
# Workspace-id placeholder for the DirectLake-on-OneLake URL's first path
# segment. It is rewritten to the target workspace id by parameter.yml and is
# intentionally distinct from the lakehouse logicalId (the second segment) so
# Analysis Services does not reject the refresh with a "Workspace Id should be
# consistent" error.
WORKSPACE_PLACEHOLDER = "a0000000-0001-0001-0001-000000000000"
SM_LOGICAL_ID = "d5000005-0001-0001-0001-000000000001"


@pytest.fixture(scope="module")
def sm_root(repo_root: Path) -> Path:
    p = repo_root / "workspace" / "PayerAnalytics.SemanticModel"
    assert p.is_dir(), "PayerAnalytics.SemanticModel folder missing"
    return p


def test_required_top_level_files(sm_root: Path) -> None:
    assert (sm_root / ".platform").is_file()
    assert (sm_root / "definition.pbism").is_file()
    for fname in ("database.tmdl", "model.tmdl", "expressions.tmdl", "relationships.tmdl"):
        assert (sm_root / "definition" / fname).is_file(), f"missing definition/{fname}"
    assert (sm_root / "definition" / "cultures" / "en-US.tmdl").is_file()
    assert (sm_root / "definition" / "tables").is_dir()


def test_platform_descriptor(sm_root: Path) -> None:
    doc = json.loads((sm_root / ".platform").read_text(encoding="utf-8"))
    assert doc["metadata"]["type"] == "SemanticModel"
    assert doc["metadata"]["displayName"] == "PayerAnalytics"
    assert doc["config"]["version"] == "2.0"
    assert doc["config"]["logicalId"] == SM_LOGICAL_ID


def test_every_gold_table_has_tmdl(sm_root: Path) -> None:
    tables_dir = sm_root / "definition" / "tables"
    on_disk = {p.stem for p in tables_dir.glob("*.tmdl")}
    missing = EXPECTED_GOLD_TABLES - on_disk
    extra = on_disk - EXPECTED_GOLD_TABLES
    assert not missing, f"missing TMDL for gold tables: {sorted(missing)}"
    assert not extra, f"unexpected TMDL files (not in NB_03 gold): {sorted(extra)}"


def test_every_table_is_direct_lake(sm_root: Path) -> None:
    for tmdl in (sm_root / "definition" / "tables").glob("*.tmdl"):
        text = tmdl.read_text(encoding="utf-8")
        assert "mode: directLake" in text, f"{tmdl.name} is not Direct Lake"
        assert "expressionSource: 'DirectLake - lh_gold_curated'" in text, (
            f"{tmdl.name} not bound to lh_gold_curated expression"
        )


def test_expression_points_at_gold_lakehouse(sm_root: Path) -> None:
    text = (sm_root / "definition" / "expressions.tmdl").read_text(encoding="utf-8")
    assert "'DirectLake - lh_gold_curated'" in text
    # The OneLake DFS URL has two path segments: /{workspaceId}/{lakehouseId}.
    # The first MUST be the workspace placeholder (not the lakehouse id) or AS
    # rejects the refresh; the second is the gold lakehouse logicalId.
    assert text.count(WORKSPACE_PLACEHOLDER) >= 1, (
        f"expressions.tmdl must reference {WORKSPACE_PLACEHOLDER} (workspace path segment)"
    )
    assert text.count(GOLD_LH_LOGICAL_ID) >= 1, (
        f"expressions.tmdl must reference {GOLD_LH_LOGICAL_ID} (lakehouse path segment)"
    )
    assert f"{WORKSPACE_PLACEHOLDER}/{GOLD_LH_LOGICAL_ID}" in text, (
        "DirectLake URL must be /{workspacePlaceholder}/{lakehouseLogicalId} "
        "(distinct segments) to avoid the AS workspace-id-consistency error"
    )
    assert "[HierarchicalNavigation=true]" in text


_COL_RE = re.compile(r"^\tcolumn\s+(\S+)", re.MULTILINE)
_TABLE_RE = re.compile(r"^table\s+(\S+)", re.MULTILINE)
_REL_RE = re.compile(
    r"fromColumn:\s*(\S+)\.(\S+)\s+toColumn:\s*(\S+)\.(\S+)",
    re.MULTILINE,
)


def _load_table_columns(sm_root: Path) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for tmdl in (sm_root / "definition" / "tables").glob("*.tmdl"):
        text = tmdl.read_text(encoding="utf-8")
        t = _TABLE_RE.search(text)
        assert t, f"{tmdl.name} has no `table` declaration"
        out[t.group(1)] = set(_COL_RE.findall(text))
    return out


def test_relationships_reference_real_columns(sm_root: Path) -> None:
    cols = _load_table_columns(sm_root)
    rel_text = (sm_root / "definition" / "relationships.tmdl").read_text(encoding="utf-8")
    pairs = _REL_RE.findall(rel_text)
    assert pairs, "relationships.tmdl has no relationships"
    errors: list[str] = []
    for ft, fc, tt, tc in pairs:
        if ft not in cols:
            errors.append(f"unknown fromTable: {ft}")
            continue
        if tt not in cols:
            errors.append(f"unknown toTable: {tt}")
            continue
        if fc not in cols[ft]:
            errors.append(f"missing column {ft}.{fc}")
        if tc not in cols[tt]:
            errors.append(f"missing column {tt}.{tc}")
    assert not errors, "relationship drift:\n  " + "\n  ".join(errors)


def test_model_references_every_table(sm_root: Path) -> None:
    text = (sm_root / "definition" / "model.tmdl").read_text(encoding="utf-8")
    refs = set(re.findall(r"^ref table\s+(\S+)", text, re.MULTILINE))
    assert refs == EXPECTED_GOLD_TABLES, (
        f"model.tmdl ref-table set drifted; missing={EXPECTED_GOLD_TABLES - refs}, "
        f"extra={refs - EXPECTED_GOLD_TABLES}"
    )


def test_no_duplicate_logical_ids_across_repo(repo_root: Path) -> None:
    """Adding the semantic model must not collide with any other item's logicalId."""
    seen: dict[str, Path] = {}
    for platform in (repo_root / "workspace").rglob(".platform"):
        try:
            doc = json.loads(platform.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        lid = doc.get("config", {}).get("logicalId")
        if not lid:
            continue
        if lid in seen:
            pytest.fail(
                f"duplicate logicalId {lid} in {platform} (also in {seen[lid]})"
            )
        seen[lid] = platform

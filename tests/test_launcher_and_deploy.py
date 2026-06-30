"""Locks the Healthcare_Launcher notebook + tools/deploy.py wrapper (A.4 + A.5)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

LAUNCHER = "Healthcare_Launcher"


@pytest.fixture(scope="module")
def workspace_dir(repo_root: Path) -> Path:
    return repo_root / "workspace"


def test_launcher_present_and_valid(workspace_dir: Path) -> None:
    d = workspace_dir / f"{LAUNCHER}.Notebook"
    assert d.is_dir(), "Healthcare_Launcher.Notebook missing"

    plat = json.loads((d / ".platform").read_text(encoding="utf-8"))
    assert plat["metadata"]["type"] == "Notebook"
    assert plat["metadata"]["displayName"] == LAUNCHER
    assert plat["config"]["logicalId"].startswith("b3000003-"), (
        "launcher logicalId must use the notebook namespace"
    )

    content = (d / "notebook-content.py").read_text(encoding="utf-8")
    assert content.startswith("# Fabric notebook source"), "missing fabric header"

    # Launcher must orchestrate all three medallion notebooks by displayName,
    # not by logicalId — mssparkutils.notebook.run resolves on displayName.
    for nb in ("NB_01_Bronze_Ingest", "NB_02_Silver_Transform", "NB_03_Gold_Build"):
        assert re.search(rf'notebook\.run\(\s*"{nb}"', content), (
            f"launcher does not invoke {nb} via mssparkutils.notebook.run"
        )


def test_launcher_gold_sanity_check_covers_key_aggregates(workspace_dir: Path) -> None:
    content = (workspace_dir / f"{LAUNCHER}.Notebook" / "notebook-content.py").read_text(encoding="utf-8")
    # These are the surfaces the 7 Foundry data agents bind to in Stream B —
    # if any is missing the launcher will silently leave agents broken.
    for must in (
        "fact_claim",
        "fact_pharmacy_pa",
        "agg_denial_by_payer",
        "agg_pa_tat",
        "agg_stars_compliance",
        "agg_health_equity_index_proxy",
    ):
        assert must in content, f"launcher sanity check missing {must}"


# ---------------------------------------------------------------------------
# B.3.5 — Jumpstart distribution: knowledge upload + DataAgent ID patching
# ---------------------------------------------------------------------------


def test_launcher_has_b35_cell_count(workspace_dir: Path) -> None:
    """Launcher must keep its 6-cell shape (1 markdown + 5 python).

    Accepts both Fabric notebook serialisations of the cell delimiter:
      - canonical export:  `# CELL ********************` / `# MARKDOWN ****...`
        (cell language lives in the following `# META {...}` block), and
      - legacy inline:     `# CELL **{"language":"python"}**`.
    Only the cell *shape* (1 markdown + 5 python) is asserted, not the token
    spelling, so a format round-trip through Fabric doesn't break the gate.
    """
    import re

    content = (workspace_dir / f"{LAUNCHER}.Notebook" / "notebook-content.py").read_text(encoding="utf-8")

    md_inline = len(re.findall(r'# MARKDOWN \*\*\{', content))
    py_inline = len(re.findall(r'# CELL \*\*\{"language":"python"\}\*\*', content))
    if md_inline or py_inline:
        md, py = md_inline, py_inline
    else:
        # Canonical format: delimiters are bare asterisks; language is in META.
        md = len(re.findall(r'^# MARKDOWN \*{4,}\s*$', content, re.MULTILINE))
        cells = len(re.findall(r'^# CELL \*{4,}\s*$', content, re.MULTILINE))
        py = cells  # all non-markdown cells in the launcher are python

    assert md == 1, f"expected 1 markdown cell, found {md}"
    assert py == 5, f"expected 5 python cells (CONFIG + 4 steps), found {py}"


def test_launcher_exposes_jumpstart_config(workspace_dir: Path) -> None:
    """Jumpstart installer + analyst-edit path require these CONFIG knobs."""
    content = (workspace_dir / f"{LAUNCHER}.Notebook" / "notebook-content.py").read_text(encoding="utf-8")
    for knob in (
        "GITHUB_OWNER",
        "GITHUB_REPO",
        "GITHUB_BRANCH",
        "UPLOAD_KNOWLEDGE_DOCS",
        "RUN_ETL",
        "PATCH_DATA_AGENTS",
        "RUN_SANITY_CHECK",
    ):
        assert knob in content, f"launcher CONFIG missing {knob}"


def test_launcher_uploads_all_payer_knowledge_docs(workspace_dir: Path, repo_root: Path) -> None:
    """The KNOWN_DOCS fallback list must list every .md actually in payer_knowledge/."""
    content = (workspace_dir / f"{LAUNCHER}.Notebook" / "notebook-content.py").read_text(encoding="utf-8")
    on_disk = sorted(p.name for p in (repo_root / "payer_knowledge").glob("*.md"))
    assert on_disk, "payer_knowledge/*.md is empty — check repo state"
    for name in on_disk:
        assert f'"{name}"' in content, (
            f"launcher KNOWN_DOCS fallback missing payer_knowledge/{name}"
        )


def test_launcher_patches_all_eight_data_agents(workspace_dir: Path) -> None:
    """Cell 3 must rebind exactly the 8 DataAgents shipped (B.3 + C.4 ClaimsRawExplorer)."""
    content = (workspace_dir / f"{LAUNCHER}.Notebook" / "notebook-content.py").read_text(encoding="utf-8")
    for agent in (
        "CFOAgent", "StarsAgent", "RiskAdjustmentAgent", "SIUAgent",
        "CareMgmtAgent", "NetworkAgent", "UMAgent", "ClaimsRawExplorer",
    ):
        assert f'"{agent}"' in content, f"launcher DataAgent patch list missing {agent}"
    # And it must drive Fabric REST API LRO (getDefinition / updateDefinition)
    assert "getDefinition" in content
    assert "updateDefinition" in content
    assert "00000000-0000-0000-0000-000000000000" in content, "zero-GUID placeholder marker missing"


def test_deploy_script_exists_and_dry_run_renders(repo_root: Path) -> None:
    script = repo_root / "tools" / "deploy.py"
    assert script.is_file(), "tools/deploy.py missing"

    # Dry run must succeed without any FABRIC_WORKSPACE_ID_* env vars
    # (the placeholder is rendered instead of resolving the var).
    res = subprocess.run(
        [sys.executable, str(script), "--env", "dev", "--dry-run"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"deploy.py dry-run failed: stderr={res.stderr!r}"
    out = res.stdout
    assert "DRY RUN" in out
    assert "would be published" in out
    # Every item type that has at least one folder on disk must be listed.
    for kind in ("Lakehouse", "Notebook", "DataPipeline"):
        assert f"[{kind}]" in out, f"dry-run preview missing [{kind}] section"


def test_deploy_script_blocks_prod_without_confirm(repo_root: Path) -> None:
    res = subprocess.run(
        [sys.executable, str(repo_root / "tools" / "deploy.py"), "--env", "prod"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0
    assert "--confirm" in (res.stderr + res.stdout)


def test_ci_workflow_runs_all_gates(repo_root: Path) -> None:
    ci = (repo_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for step in (
        "ruff check",
        "pytest",
        "tools/check_citations.py",
        "tools/audit_data.py",
        "tools/data_fidelity.py",
        "tools/deploy.py --check",
        "tools/deploy.py --env dev --dry-run",
    ):
        assert step in ci, f"CI workflow missing step: {step}"

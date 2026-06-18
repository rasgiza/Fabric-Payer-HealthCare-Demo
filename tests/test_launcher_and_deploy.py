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
        "tools/deploy.py --env dev --dry-run",
    ):
        assert step in ci, f"CI workflow missing step: {step}"

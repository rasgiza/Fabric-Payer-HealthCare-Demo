"""Drift gate for the per-tier self-contained jumpstart workspace folders.

The Fabric Jumpstart installer (``fabric_jumpstart._install_from_github``) deploys
whatever lives under a tier's ``source.workspace_path``. Those folders are
generated from the repo-root ``workspace/`` source-of-truth by
``tools/build_jumpstart_workspace.py``. This test fails if a committed tier
folder has drifted from what the generator would produce (e.g. someone edited an
item under ``workspace/`` but forgot to regenerate), mirroring the
``tools/deploy.py --check`` parameter drift gate.

Regenerate with::

    python tools/build_jumpstart_workspace.py --all
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.build_jumpstart_workspace import build_tier

# Tiers that ship a generated, installer-ready ``workspace/`` folder today.
GENERATED_TIERS = ("analytics",)


@pytest.mark.parametrize("tier", GENERATED_TIERS)
def test_tier_workspace_matches_source(repo_root: Path, tier: str) -> None:
    tier_dir = repo_root / "jumpstarts" / tier
    assert (tier_dir / "workspace").exists(), (
        f"{tier}: jumpstarts/{tier}/workspace/ is missing — run "
        f"`python tools/build_jumpstart_workspace.py --tier {tier}`"
    )
    assert build_tier(tier_dir, check=True), (
        f"{tier}: jumpstarts/{tier}/workspace/ has drifted from workspace/ — run "
        f"`python tools/build_jumpstart_workspace.py --tier {tier}`"
    )


@pytest.mark.parametrize("tier", GENERATED_TIERS)
def test_tier_workspace_excludes_higher_tier_items(repo_root: Path, tier: str) -> None:
    """A tier folder must not contain items reserved for a higher tier."""
    ws = repo_root / "jumpstarts" / tier / "workspace"
    names = {p.name for p in ws.iterdir() if p.is_dir()}
    # Tier-3-only surfaces must never leak into the Tier-2 installer folder.
    forbidden = {
        "NB_RTI_01_Ingest_Claims_Stream.Notebook",
        "NB_RTI_02_PA_Latency.Notebook",
        "NB_RTI_03_ADT_Outreach.Notebook",
        "NB_RTI_04_SIU_Intake_Scoring.Notebook",
        "eh_payer_rt.Eventhouse",
        "es_claims_arrivals.Eventstream",
        "kqldb_payer_rt.KQLDatabase",
        "PayerOps_Activator.Reflex",
        "Payer_Ontology.Ontology",
    }
    leaked = names & forbidden
    assert not leaked, f"{tier}: higher-tier items leaked into workspace/: {sorted(leaked)}"


@pytest.mark.parametrize("tier", GENERATED_TIERS)
def test_tier_agents_have_no_undeployed_datasources(repo_root: Path, tier: str) -> None:
    """DataAgents must not reference items outside the tier (e.g. the Tier-3 graph).

    A leftover ``graph-Payer_Ontology`` datasource points at an Ontology this tier
    never deploys; the launcher can't rebind it, so it lingers as a dangling
    zero-GUID reference. The generator prunes these — assert none survive.
    """
    ws = repo_root / "jumpstarts" / tier / "workspace"
    dangling = sorted(
        str(p.relative_to(ws))
        for p in ws.glob("*.DataAgent/Files/Config/*/graph-*")
        if p.is_dir()
    )
    assert not dangling, f"{tier}: undeployed graph datasources leaked into agents: {dangling}"


@pytest.mark.parametrize("tier", GENERATED_TIERS)
def test_tier_workspace_has_parameter_yml(repo_root: Path, tier: str) -> None:
    """fabric-cicd resolves parameter.yml at the workspace_path root."""
    param = repo_root / "jumpstarts" / tier / "workspace" / "parameter.yml"
    assert param.exists(), f"{tier}: workspace/parameter.yml missing"
    # The workspace-id sentinel rule must fire under the installer's default
    # environment ("N/A"), which requires the _ALL_ wildcard key.
    text = param.read_text(encoding="utf-8")
    assert "_ALL_" in text, (
        f"{tier}: parameter.yml is missing the _ALL_ workspace-id rule; the "
        "DirectLake binding will not resolve under the installer"
    )

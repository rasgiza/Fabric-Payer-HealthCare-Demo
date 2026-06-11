"""Shared pytest fixtures for the Fabric-Payer-HealthCare-Demo test suite.

These fixtures point tests at the bundled `smoke` synth run + graph so the
suite is self-contained: no Fabric workspace, no Foundry account, no live
network required. Tier 1B harness only — runtime credentials are out of
scope here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Make repo modules (mission_control, tools) importable without installing the
# repo as a package — it deliberately isn't a package.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def smoke_synth_dir(repo_root: Path) -> Path:
    d = repo_root / "data" / "synth" / "smoke"
    if not d.exists():
        pytest.skip(f"smoke synth dir missing: {d}")
    return d


@pytest.fixture(scope="session")
def smoke_graph_path(repo_root: Path) -> Path:
    p = repo_root / "data" / "graph" / "smoke" / "payer_graph.gpickle"
    if not p.exists():
        pytest.skip(f"smoke graph missing: {p}")
    return p


@pytest.fixture(scope="session")
def data_agent_dirs(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "data_agents").glob("*.DataAgent"))


@pytest.fixture(scope="session")
def hosted_agent_dirs(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "data_agents").glob("*.HostedAgent"))

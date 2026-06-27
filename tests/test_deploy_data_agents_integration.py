"""Integration test for `python tools/deploy_data_agents.py --dry-run`.

Unlike `tests/test_hosted_agent_artifacts.py` (per-file shape assertions) and
`tests/test_pareviewcopilot_shape.py` (per-tool stub assertions), this test
exercises the *whole* deploy_data_agents.py script end-to-end as a subprocess.
The goal is to catch regressions where each piece passes its unit shape check
but the orchestrator-build / hosted-agent-build / KB-index code paths happen to
crash when wired together.

Sister test to `test_launcher_and_deploy::test_deploy_script_exists_and_dry_run_renders`
which does the same thing for `tools/deploy.py` (fabric-cicd wrapper).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_deploy_data_agents_dry_run_returns_zero(repo_root: Path) -> None:
    """Default invocation (no flags) is dry-run and must exit 0."""
    res = subprocess.run(
        [sys.executable, str(repo_root / "tools" / "deploy_data_agents.py")],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"deploy_data_agents.py dry-run failed: stderr={res.stderr!r}"


def test_deploy_data_agents_dry_run_lists_all_eight_agents(repo_root: Path) -> None:
    """The dry-run plan must mention every DataAgent (B.3 + C.4) + both hosted Copilots (B.4 + C.5)."""
    res = subprocess.run(
        [sys.executable, str(repo_root / "tools" / "deploy_data_agents.py"), "--dry-run"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    out = res.stdout
    # The 8 Fabric DataAgents (B.3 + C.4 ClaimsRawExplorer).
    for agent in ("CFOAgent", "StarsAgent", "RiskAdjustmentAgent", "SIUAgent",
                  "CareMgmtAgent", "NetworkAgent", "UMAgent", "ClaimsRawExplorer"):
        assert agent in out, f"deploy_data_agents.py dry-run plan missing {agent!r}"
    # The hosted Copilots: PAReviewCopilot (B.4) + PayerRT_Copilot (C.5)
    assert "PAReviewCopilot" in out, "deploy_data_agents.py dry-run plan missing PAReviewCopilot"
    assert "PayerRT_Copilot" in out, "deploy_data_agents.py dry-run plan missing PayerRT_Copilot"
    # The OK marker should report function_tools=8 (one per Fabric DataAgent) and hosted=2
    assert "function_tools=8" in out, f"expected function_tools=8 in summary, got: {out!r}"
    assert "hosted=2" in out, f"expected hosted=2 in summary, got: {out!r}"


def test_deploy_data_agents_live_without_credentials_exits_2(repo_root: Path) -> None:
    """--live without --foundry-project/--workspace-id must exit 2 (not 0, not crash)."""
    res = subprocess.run(
        [sys.executable, str(repo_root / "tools" / "deploy_data_agents.py"), "--live"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        # Scrub env so a developer's local FOUNDRY_PROJECT/FABRIC_WORKSPACE_ID
        # doesn't make this test pass spuriously.
        env={k: v for k, v in __import__("os").environ.items()
             if k not in ("FOUNDRY_PROJECT", "FABRIC_WORKSPACE_ID")},
    )
    assert res.returncode == 2, (
        f"--live without credentials should exit 2, got {res.returncode}; "
        f"stderr={res.stderr!r}"
    )
    assert "--foundry-project" in (res.stderr + res.stdout)


def test_deploy_data_agents_dry_run_does_not_import_foundry_sdk(repo_root: Path) -> None:
    """Dry-run must NOT import agent-framework-azure-ai.

    The hosted-agent live path lazy-imports the SDK; the dry-run path does not.
    Locking this means CI / contributors without the Foundry SDK installed can
    still validate the deployment plan. We run the script in a subprocess and
    inspect `sys.modules` afterward via a wrapper that prints the membership.
    """
    probe = (
        "import sys, runpy\n"
        f"runpy.run_path(r'{(repo_root / 'tools' / 'deploy_data_agents.py').as_posix()}', "
        "run_name='__main__')\n"
    )
    # The script ends with `raise SystemExit(main())`, so wrap it.
    wrapper = (
        "import sys, runpy\n"
        "try:\n"
        f"    runpy.run_path(r'{(repo_root / 'tools' / 'deploy_data_agents.py').as_posix()}', "
        "run_name='__main__')\n"
        "except SystemExit as e:\n"
        "    rc = e.code or 0\n"
        "else:\n"
        "    rc = 0\n"
        "print(f'__SDK_IMPORTED__={\"agent_framework_azure_ai\" in sys.modules}')\n"
        "print(f'__RC__={rc}')\n"
    )
    del probe
    res = subprocess.run(
        [sys.executable, "-c", wrapper],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "__SDK_IMPORTED__=False" in res.stdout, (
        f"dry-run must not import agent_framework_azure_ai; stdout={res.stdout!r}, "
        f"stderr={res.stderr!r}"
    )
    assert "__RC__=0" in res.stdout, (
        f"dry-run wrapper expected rc=0; stdout={res.stdout!r}, stderr={res.stderr!r}"
    )

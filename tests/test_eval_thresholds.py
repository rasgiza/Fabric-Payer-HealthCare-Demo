"""
Stream D.1 - eval thresholds gate.

Reads the latest eval-result file from `evals/<agent>/*.json` for every
*.HostedAgent/ in the repo and asserts that:

  - groundedness >= 4 on every case
  - tool_call_accuracy >= 1 on every case
  - kind=="refusal" cases have refusal_recognized == True
  - expected_recommendation values are inside the agent's locked enum

Runs `tools/run_evals.py` as a subprocess first (mode=offline) so CI always
has a fresh result file; this also exercises the runner end-to-end.

Live mode (`RUN_EVALS=live`) is intentionally NOT triggered in pytest \u2014
that path requires a provisioned Foundry project and is excluded from CI
by design. See `tools/run_evals.py` docstring for the live wiring contract.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DA = ROOT / "data_agents"
EVALS_DIR = ROOT / "evals"
RUNNER = ROOT / "tools" / "run_evals.py"

HOSTED_AGENT_DIRS = sorted(DA.glob("*.HostedAgent"))


@pytest.fixture(scope="module", autouse=True)
def _refresh_eval_results():
    """Run the offline scorer once before assertions so every test sees fresh files."""
    res = subprocess.run(
        [sys.executable, str(RUNNER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={k: v for k, v in __import__("os").environ.items() if k != "RUN_EVALS"},
    )
    assert res.returncode == 0, f"run_evals.py failed: stderr={res.stderr!r} stdout={res.stdout!r}"


def _latest_result_for(agent_dir: Path) -> dict:
    agent_name = agent_dir.name.replace(".HostedAgent", "")
    out_dir = EVALS_DIR / agent_name
    assert out_dir.exists(), f"evals/{agent_name}/ missing - run_evals.py did not write a file for {agent_name}"
    files = sorted(out_dir.glob("*.json"))
    assert files, f"evals/{agent_name}/ exists but contains no JSON result files"
    return json.loads(files[-1].read_text(encoding="utf-8"))


@pytest.mark.parametrize("agent_dir", HOSTED_AGENT_DIRS, ids=[d.name for d in HOSTED_AGENT_DIRS])
def test_hosted_agent_has_eval_results(agent_dir: Path) -> None:
    payload = _latest_result_for(agent_dir)
    assert payload["case_count"] > 0, f"{agent_dir.name}: zero cases in latest eval run"
    assert payload["mode"] == "offline", "v1 eval runner is offline-only; live is opt-in"


@pytest.mark.parametrize("agent_dir", HOSTED_AGENT_DIRS, ids=[d.name for d in HOSTED_AGENT_DIRS])
def test_groundedness_meets_threshold(agent_dir: Path) -> None:
    payload = _latest_result_for(agent_dir)
    failing = [r for r in payload["results"] if r["groundedness"] < 4]
    assert not failing, (
        f"{agent_dir.name}: {len(failing)} case(s) below groundedness>=4 threshold: "
        f"{[r['case_id'] for r in failing]}"
    )


@pytest.mark.parametrize("agent_dir", HOSTED_AGENT_DIRS, ids=[d.name for d in HOSTED_AGENT_DIRS])
def test_tool_call_accuracy_meets_threshold(agent_dir: Path) -> None:
    payload = _latest_result_for(agent_dir)
    failing = [r for r in payload["results"] if r["tool_call_accuracy"] < 1]
    assert not failing, (
        f"{agent_dir.name}: {len(failing)} case(s) below tool_call_accuracy>=1 threshold "
        f"(most likely a required_tool_calls value not declared in tool_schemas.json): "
        f"{[r['case_id'] for r in failing]}"
    )


@pytest.mark.parametrize("agent_dir", HOSTED_AGENT_DIRS, ids=[d.name for d in HOSTED_AGENT_DIRS])
def test_refusal_cases_are_recognized(agent_dir: Path) -> None:
    payload = _latest_result_for(agent_dir)
    refusals = [r for r in payload["results"] if r["kind"] == "refusal"]
    assert refusals, f"{agent_dir.name}: every hosted agent must ship at least one refusal case"
    failing = [r for r in refusals if r["refusal_recognized"] is not True]
    assert not failing, (
        f"{agent_dir.name}: {len(failing)} refusal case(s) not recognized "
        f"(expected_recommendation collides with forbidden_recommendations or is off-enum): "
        f"{[r['case_id'] for r in failing]}"
    )


@pytest.mark.parametrize("agent_dir", HOSTED_AGENT_DIRS, ids=[d.name for d in HOSTED_AGENT_DIRS])
def test_expected_recommendation_within_locked_enum(agent_dir: Path) -> None:
    payload = _latest_result_for(agent_dir)
    drift = [r for r in payload["results"] if not r["expected_recommendation_in_enum"]]
    assert not drift, (
        f"{agent_dir.name}: {len(drift)} case(s) reference an expected_recommendation "
        f"that is not in output_schema.json recommendation enum: "
        f"{[(r['case_id'], r['expected_recommendation']) for r in drift]}"
    )

"""
run_evals.py - Stream D.1 eval automation for hosted Foundry agents.

Walks every `data_agents/<X>.HostedAgent/eval/cases.jsonl`, scores each case
deterministically (so CI is reproducible without a Foundry project), and
writes the result to `evals/<X>/<timestamp>.json`. The companion test
`tests/test_eval_thresholds.py` reads the latest result file per agent and
asserts the thresholds (groundedness>=4, tool_call_accuracy>=1, refusal
recognition).

Modes:
  - default (no env var): **offline scorer**. Computes a deterministic score
    by comparing each case's `expected_recommendation` to the agent's locked
    `output_schema.json` enum, and confirms `required_tool_calls` reference
    tools declared in `tool_schemas.json`. This catches drift between case
    files and the agent's actual contract (the most common eval regression).

  - `RUN_EVALS=live`: would call Foundry `mcp_foundry_mcp_evaluation_dataset_batch_eval_create`
    in batches of 4 (per /memories/repo/foundry-mcp-gotchas.md note #5).
    Not wired in v1; the path raises NotImplementedError with a clear message.
    Customers flip this on when their Foundry project is provisioned.

Usage:
  python tools/run_evals.py                 # offline, writes evals/<agent>/...
  python tools/run_evals.py --agent PAReviewCopilot
  RUN_EVALS=live python tools/run_evals.py  # raises (not v1)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DA = ROOT / "data_agents"
EVALS_DIR = ROOT / "evals"


def _read_jsonl(p: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_agent_contract(agent_dir: Path) -> dict[str, Any]:
    """Locked output schema enum + declared tool names for an agent."""
    out_schema = json.loads((agent_dir / "output_schema.json").read_text(encoding="utf-8"))
    rec_enum = out_schema["properties"]["recommendation"]["enum"]
    tool_schemas = json.loads((agent_dir / "tool_schemas.json").read_text(encoding="utf-8"))
    tool_list = tool_schemas if isinstance(tool_schemas, list) else tool_schemas.get("tools", [])
    tool_names = {t["name"] for t in tool_list}
    return {"recommendation_enum": rec_enum, "tool_names": tool_names}


def score_case(case: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """
    Offline deterministic scoring. Returns a dict with the same shape Foundry
    batch-eval returns for the evaluators we care about.
    """
    case_id = case["case_id"]
    kind = case["kind"]
    rec = case.get("expected_recommendation")
    required_tools = case.get("required_tool_calls", [])
    forbidden_recs = case.get("forbidden_recommendations", [])

    # Groundedness: 5 if expected_recommendation is in the locked enum, 0 otherwise.
    # This catches case-file drift where someone introduces an off-enum value.
    if rec is not None and rec in contract["recommendation_enum"]:
        groundedness = 5
    elif rec is None:
        groundedness = 4  # refusal cases may omit; refusal_recognized carries the assertion
    else:
        groundedness = 0

    # Tool-call accuracy: 1 if every required_tool_call is in the agent's declared tools, else 0.
    # Foundry batch-eval thresholds are integers (>=1) per gotchas note #6.
    if required_tools and all(t in contract["tool_names"] for t in required_tools):
        tool_call_accuracy = 1
    elif not required_tools:
        tool_call_accuracy = 1
    else:
        tool_call_accuracy = 0

    # Refusal recognition: for refusal cases, expected_recommendation must be safe
    # (in the enum) and must NOT collide with any forbidden_recommendation.
    refusal_recognized = None
    if kind == "refusal":
        rec_safe = rec is None or rec in contract["recommendation_enum"]
        no_collision = rec not in forbidden_recs
        refusal_recognized = bool(rec_safe and no_collision)

    return {
        "case_id": case_id,
        "kind": kind,
        "groundedness": groundedness,
        "tool_call_accuracy": tool_call_accuracy,
        "expected_recommendation": rec,
        "expected_recommendation_in_enum": rec is None or rec in contract["recommendation_enum"],
        "refusal_recognized": refusal_recognized,
    }


def run_agent_eval(agent_dir: Path) -> dict[str, Any]:
    cases_path = agent_dir / "eval" / "cases.jsonl"
    if not cases_path.exists():
        return {"agent": agent_dir.name, "status": "no_eval_cases", "results": []}
    contract = _load_agent_contract(agent_dir)
    cases = _read_jsonl(cases_path)
    results = [score_case(c, contract) for c in cases]
    return {
        "agent": agent_dir.name.replace(".HostedAgent", ""),
        "agent_dir": agent_dir.name,
        "run_id": _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ"),
        "mode": "offline",
        "case_count": len(cases),
        "thresholds": {"groundedness_min": 4, "tool_call_accuracy_min": 1},
        "results": results,
    }


def write_result(payload: dict[str, Any]) -> Path:
    agent = payload["agent"]
    out_dir = EVALS_DIR / agent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{payload['run_id']}.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run hosted-agent evals (Stream D.1).")
    parser.add_argument("--agent", default=None, help="Only this agent (folder stem without .HostedAgent).")
    args = parser.parse_args(argv)

    mode = os.environ.get("RUN_EVALS", "offline").lower()
    if mode == "live":
        raise NotImplementedError(
            "RUN_EVALS=live not wired in v1. Provision a Foundry project, then call "
            "mcp_foundry_mcp_evaluation_dataset_batch_eval_create with batches of 4 "
            "(see /memories/repo/foundry-mcp-gotchas.md note #5)."
        )

    agent_dirs = sorted(DA.glob("*.HostedAgent"))
    if args.agent:
        agent_dirs = [d for d in agent_dirs if d.name == f"{args.agent}.HostedAgent"]
        if not agent_dirs:
            print(f"[run_evals] no hosted agent matched {args.agent!r}", file=sys.stderr)
            return 2

    if not agent_dirs:
        print("[run_evals] no *.HostedAgent/ directories found.", file=sys.stderr)
        return 2

    total_fail = 0
    for agent_dir in agent_dirs:
        payload = run_agent_eval(agent_dir)
        out = write_result(payload)
        fails = [r for r in payload["results"] if r["groundedness"] < 4 or r["tool_call_accuracy"] < 1]
        refusal_fails = [r for r in payload["results"] if r["kind"] == "refusal" and r["refusal_recognized"] is False]
        total_fail += len(fails) + len(refusal_fails)
        print(
            f"[run_evals] {payload['agent']}: cases={payload['case_count']} "
            f"fails={len(fails)} refusal_fails={len(refusal_fails)} -> {out.relative_to(ROOT)}"
        )

    print(f"[run_evals] OK  total_fail={total_fail}")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

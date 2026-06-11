"""Schema + content checks per `data_agents/<X>.DataAgent/` directory.

Asserts (per agent):
  - `aiInstructions.md` exists and is >= 500 chars (no empty stubs)
  - `binding.yaml` parses, has `max_items: 1` (Foundry maxItems constraint),
    `mcp_tool.require_approval: never`, and an `ai_instructions` pointer that
    resolves on disk
  - `fewshots.jsonl` has >= 5 examples and every line is valid JSON
  - `eval/cases.jsonl` has >= 3 happy_path + >= 1 refusal case

These checks complement `eval_agents_offline.py` (which validates routing +
measure resolution) by catching shape regressions in the artifacts themselves.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


def _agent_dirs() -> list[Path]:
    repo_root = Path(__file__).resolve().parent.parent
    return sorted((repo_root / "data_agents").glob("*.DataAgent"))


@pytest.mark.parametrize("agent_dir", _agent_dirs(), ids=lambda p: p.name)
def test_data_agent_artifacts(agent_dir: Path) -> None:
    name = agent_dir.name

    ai = agent_dir / "aiInstructions.md"
    assert ai.exists(), f"{name}: missing aiInstructions.md"
    assert len(ai.read_text(encoding="utf-8")) >= 500, (
        f"{name}: aiInstructions.md is shorter than 500 chars (looks like a stub)"
    )

    binding_path = agent_dir / "binding.yaml"
    assert binding_path.exists(), f"{name}: missing binding.yaml"
    binding = yaml.safe_load(binding_path.read_text(encoding="utf-8"))
    assert binding.get("fabric_data_agent", {}).get("max_items") == 1, (
        f"{name}: binding.fabric_data_agent.max_items must be 1 "
        "(Foundry one-agent-one-data-source constraint)"
    )
    assert binding.get("mcp_tool", {}).get("require_approval") == "never", (
        f"{name}: binding.mcp_tool.require_approval must be 'never' "
        "(default 'always' silently hangs orchestrator on mcp_approval_request)"
    )
    ai_pointer = binding.get("ai_instructions")
    assert ai_pointer, f"{name}: binding missing ai_instructions pointer"
    assert (agent_dir / ai_pointer).exists(), (
        f"{name}: binding.ai_instructions={ai_pointer!r} does not exist"
    )

    fewshots = agent_dir / "fewshots.jsonl"
    assert fewshots.exists(), f"{name}: missing fewshots.jsonl"
    lines = [line for line in fewshots.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 5, f"{name}: only {len(lines)} fewshots (need >= 5)"
    for i, line in enumerate(lines):
        try:
            json.loads(line)
        except json.JSONDecodeError as e:
            pytest.fail(f"{name}: fewshots.jsonl line {i + 1} is not valid JSON: {e}")

    cases_path = agent_dir / "eval" / "cases.jsonl"
    assert cases_path.exists(), f"{name}: missing eval/cases.jsonl"
    cases = [
        json.loads(line)
        for line in cases_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    happy = [c for c in cases if c.get("kind") == "happy_path"]
    refusal = [c for c in cases if c.get("kind") == "refusal"]
    assert len(happy) >= 3, f"{name}: only {len(happy)} happy_path cases (need >= 3)"
    assert len(refusal) >= 1, f"{name}: only {len(refusal)} refusal cases (need >= 1)"

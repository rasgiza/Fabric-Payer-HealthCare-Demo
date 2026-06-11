"""Schema + governance checks per `data_agents/<X>.HostedAgent/` directory.

Hosted agents are workqueue-invoked Foundry hosted agents (PREVIEW as of
2026-06-10). They use a different artifact shape than `*.DataAgent/`:
  - `agent.yaml` declares foundry config + tools + knowledge sources +
    governance flags
  - `tool_schemas.json` declares function tools (name + parameters)
  - `output_schema.json` is a JSON-schema draft-07 envelope with a required
    `recommendation` enum
  - governance.phi_minimization must be 'required' and decision_authority
    must be 'deny' (these are gate-blocking for HIPAA-grade demos)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


def _hosted_dirs() -> list[Path]:
    repo_root = Path(__file__).resolve().parent.parent
    return sorted((repo_root / "data_agents").glob("*.HostedAgent"))


@pytest.mark.parametrize("agent_dir", _hosted_dirs(), ids=lambda p: p.name)
def test_hosted_agent_artifacts(agent_dir: Path) -> None:
    name = agent_dir.name

    yaml_path = agent_dir / "agent.yaml"
    tools_path = agent_dir / "tool_schemas.json"
    schema_path = agent_dir / "output_schema.json"
    cases_path = agent_dir / "eval" / "cases.jsonl"

    for p in (yaml_path, tools_path, schema_path, cases_path):
        assert p.exists(), f"{name}: missing {p.name}"

    spec = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    required_keys = (
        "agent", "kind", "foundry", "mcp_tool", "tools",
        "knowledge_sources", "output_schema", "ai_instructions", "governance",
    )
    missing = [k for k in required_keys if k not in spec]
    assert not missing, f"{name}: agent.yaml missing keys {missing}"

    assert spec["mcp_tool"].get("require_approval") == "never", (
        f"{name}: mcp_tool.require_approval must be 'never'"
    )
    assert spec["foundry"].get("auth") == "project_msi", (
        f"{name}: foundry.auth must be 'project_msi' (not account-scoped MSI)"
    )

    gov = spec.get("governance", {})
    assert gov.get("phi_minimization") == "required", (
        f"{name}: governance.phi_minimization must be 'required'"
    )
    assert gov.get("decision_authority") == "deny", (
        f"{name}: governance.decision_authority must be 'deny' "
        "(hosted agent must not authorize coverage decisions)"
    )
    assert gov.get("audit_log") == "required", (
        f"{name}: governance.audit_log must be 'required'"
    )

    repo_root = Path(__file__).resolve().parent.parent
    for ks in spec.get("knowledge_sources", []):
        assert (repo_root / ks).exists(), f"{name}: knowledge_source missing on disk: {ks}"

    tools = json.loads(tools_path.read_text(encoding="utf-8"))
    assert isinstance(tools, list) and tools, f"{name}: tool_schemas.json must be non-empty list"
    for i, t in enumerate(tools):
        assert t.get("name"), f"{name}: tool[{i}] missing 'name'"
        assert t.get("parameters"), f"{name}: tool[{i}] missing 'parameters'"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    rec = schema.get("properties", {}).get("recommendation", {})
    assert rec.get("type") == "string", f"{name}: output_schema.recommendation must be a string"
    assert "enum" in rec and rec["enum"], (
        f"{name}: output_schema.recommendation must declare an enum"
    )

    cases = [
        json.loads(line)
        for line in cases_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    happy = [c for c in cases if c.get("kind") == "happy_path"]
    refusal = [c for c in cases if c.get("kind") == "refusal"]
    assert len(happy) >= 3, f"{name}: only {len(happy)} happy_path cases (need >= 3)"
    assert len(refusal) >= 1, f"{name}: only {len(refusal)} refusal cases (need >= 1)"

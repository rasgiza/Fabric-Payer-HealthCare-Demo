"""
eval_agents_offline.py - Phase 5 calibrated offline gate.

Loads every <Agent>.DataAgent/eval/cases.jsonl and:

  1. Routes the question through MissionControlRouter.
  2. For happy-path: assert routed_agent == expected_agent.
  3. For refusal:    assert router triggered refusal_pattern OR routed correctly
                     to the agent that owns the refusal class.
  4. Verifies that every expected_measure exists in semantic_model/measure_catalog.yaml
     so we don't ship a fewshot that references a measure we didn't build.

Hosted agents (<Agent>.HostedAgent/) have a separate validation path because
they are workqueue-invoked, not routed through MissionControl. We validate:
  - agent.yaml schema (required keys + governance fields)
  - tool_schemas.json is valid JSON and every tool has name + parameters
  - output_schema.json is valid JSON-schema draft-07 with required `recommendation` enum
  - every knowledge_source path exists on disk
  - eval/cases.jsonl loads, has >=3 happy + >=1 refusal, every expected_regulatory_pointer
    resolves in citations.yaml

Gate (must all pass):
  - >= 30 happy-path cases pass routing (data agents)
  - routing accuracy >= 0.90
  - 100% of refusal cases trigger refusal_reason (or correct agent)
  - 100% of expected_measures exist in measure_catalog.yaml
  - 100% of hosted-agent artifact checks pass
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DA = ROOT / "data_agents"
CATALOG = ROOT / "semantic_model" / "measure_catalog.yaml"
CITATIONS = ROOT / "citations.yaml"

sys.path.insert(0, str(ROOT))
from mission_control.orchestrator import MissionControlRouter  # noqa: E402


def load_known_measures() -> set[str]:
    cat = yaml.safe_load(CATALOG.read_text())
    return {m["name"] for m in cat["measures"]}


def load_known_citations() -> set[str]:
    if not CITATIONS.exists():
        return set()
    cit = yaml.safe_load(CITATIONS.read_text())
    rows = cit if isinstance(cit, list) else cit.get("citations", [])
    return {r["id"] for r in rows if isinstance(r, dict) and "id" in r}


def validate_hosted_agent(agent_dir: Path, citations: set[str]) -> list[str]:
    """Return list of failure strings (empty = PASS)."""
    fails: list[str] = []
    name = agent_dir.name.removesuffix(".HostedAgent")

    yaml_path = agent_dir / "agent.yaml"
    tools_path = agent_dir / "tool_schemas.json"
    schema_path = agent_dir / "output_schema.json"
    cases_path = agent_dir / "eval" / "cases.jsonl"

    for p in (yaml_path, tools_path, schema_path, cases_path):
        if not p.exists():
            fails.append(f"{name}: missing {p.relative_to(ROOT)}")

    if fails:
        return fails

    spec = yaml.safe_load(yaml_path.read_text())
    for k in ("agent", "kind", "foundry", "mcp_tool", "tools", "knowledge_sources",
              "output_schema", "ai_instructions", "governance"):
        if k not in spec:
            fails.append(f"{name}: agent.yaml missing key `{k}`")
    if spec.get("mcp_tool", {}).get("require_approval") != "never":
        fails.append(f"{name}: mcp_tool.require_approval must be 'never'")
    if spec.get("foundry", {}).get("auth") != "project_msi":
        fails.append(f"{name}: foundry.auth must be 'project_msi'")
    for ks in spec.get("knowledge_sources", []):
        if not (ROOT / ks).exists():
            fails.append(f"{name}: knowledge_source missing on disk: {ks}")

    try:
        tools = json.loads(tools_path.read_text())
    except json.JSONDecodeError as e:
        fails.append(f"{name}: tool_schemas.json invalid: {e}")
        tools = []
    for i, t in enumerate(tools):
        if not (t.get("name") and t.get("parameters")):
            fails.append(f"{name}: tool[{i}] missing name or parameters")

    try:
        schema = json.loads(schema_path.read_text())
    except json.JSONDecodeError as e:
        fails.append(f"{name}: output_schema.json invalid: {e}")
        schema = {}
    rec = schema.get("properties", {}).get("recommendation", {})
    if rec.get("type") != "string" or "enum" not in rec:
        fails.append(f"{name}: output_schema.recommendation must be enum string")

    cases = [json.loads(line) for line in cases_path.read_text().splitlines() if line.strip()]
    happy = [c for c in cases if c["kind"] == "happy_path"]
    refusal = [c for c in cases if c["kind"] == "refusal"]
    if len(happy) < 3:
        fails.append(f"{name}: only {len(happy)} happy-path cases (need >=3)")
    if len(refusal) < 1:
        fails.append(f"{name}: only {len(refusal)} refusal cases (need >=1)")
    if citations:
        for c in cases:
            for cid in c.get("expected_regulatory_pointers", []) or []:
                if cid not in citations:
                    fails.append(f"{name}/{c['case_id']}: regulatory pointer `{cid}` not in citations.yaml")

    return fails


def main() -> int:
    router = MissionControlRouter()
    measures = load_known_measures()
    citations = load_known_citations()

    cases: list[dict] = []
    for d in sorted(DA.glob("*.DataAgent")):
        eval_file = d / "eval" / "cases.jsonl"
        if not eval_file.exists():
            continue
        for line in eval_file.read_text().splitlines():
            if line.strip():
                cases.append(json.loads(line))

    happy = [c for c in cases if c["kind"] == "happy_path"]
    refusals = [c for c in cases if c["kind"] == "refusal"]

    routing_ok = 0
    routing_fail: list[tuple[str, str, str | None]] = []
    measure_fail: list[tuple[str, str]] = []

    for c in happy:
        d = router.route(c["question"])
        if d.agent == c["expected_agent"]:
            routing_ok += 1
        else:
            routing_fail.append((c["case_id"], c["expected_agent"], d.agent))

        for m in c.get("expected_measures", []):
            if m not in measures:
                measure_fail.append((c["case_id"], m))

    refusal_ok = 0
    refusal_fail: list[tuple[str, str | None, str | None]] = []
    for c in refusals:
        d = router.route(c["question"])
        if d.refusal_reason or d.agent == c["expected_agent"]:
            refusal_ok += 1
        else:
            refusal_fail.append((c["case_id"], d.refusal_reason, d.agent))

    routing_acc = routing_ok / len(happy) if happy else 0.0
    refusal_acc = refusal_ok / len(refusals) if refusals else 0.0

    hosted_dirs = sorted(DA.glob("*.HostedAgent"))
    hosted_fails: list[str] = []
    for hd in hosted_dirs:
        hosted_fails.extend(validate_hosted_agent(hd, citations))

    print(f"[eval] data-agent cases happy={len(happy)} refusal={len(refusals)}")
    print(f"[eval] routing accuracy: {routing_ok}/{len(happy)} = {routing_acc:.2%}")
    print(f"[eval] refusal accuracy: {refusal_ok}/{len(refusals)} = {refusal_acc:.2%}")
    print(f"[eval] measure-resolution: {len(happy) * 1 - len(measure_fail)}/{sum(len(c['expected_measures']) for c in happy)} unique-OK")
    print(f"[eval] hosted-agents: {len(hosted_dirs)} validated, {len(hosted_fails)} failures")

    fails = []
    if len(happy) < 30:
        fails.append(f"only {len(happy)} happy-path cases (need >= 30)")
    if routing_acc < 0.90:
        fails.append(f"routing accuracy {routing_acc:.2%} < 90%")
    if refusal_acc < 1.0:
        fails.append(f"refusal accuracy {refusal_acc:.2%} < 100%")
    if measure_fail:
        fails.append(f"{len(measure_fail)} measure refs not in catalog")
    if hosted_fails:
        fails.append(f"{len(hosted_fails)} hosted-agent artifact failures")

    if routing_fail:
        print("\n  Routing misses:")
        for cid, exp, got in routing_fail[:10]:
            print(f"    {cid}: expected={exp}  got={got}")
    if refusal_fail:
        print("\n  Refusal misses:")
        for cid, r, a in refusal_fail[:10]:
            print(f"    {cid}: refusal={r}  routed={a}")
    if measure_fail:
        print("\n  Unknown measures:")
        for cid, m in measure_fail[:10]:
            print(f"    {cid}: {m}")
    if hosted_fails:
        print("\n  Hosted-agent failures:")
        for f in hosted_fails[:20]:
            print(f"    {f}")

    if fails:
        print(f"\n[eval] FAIL - {len(fails)} gate(s):")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\n[eval] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

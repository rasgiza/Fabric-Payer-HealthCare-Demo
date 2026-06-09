"""
eval_agents_offline.py - Phase 5 calibrated offline gate.

Loads every <Agent>.DataAgent/eval/cases.jsonl and:

  1. Routes the question through MissionControlRouter.
  2. For happy-path: assert routed_agent == expected_agent.
  3. For refusal:    assert router triggered refusal_pattern OR routed correctly
                     to the agent that owns the refusal class.
  4. Verifies that every expected_measure exists in semantic_model/measure_catalog.yaml
     so we don't ship a fewshot that references a measure we didn't build.

Gate (must all pass):
  - >= 30 happy-path cases pass routing
  - routing accuracy >= 0.90
  - 100% of refusal cases trigger refusal_reason (or correct agent)
  - 100% of expected_measures exist in measure_catalog.yaml
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DA = ROOT / "data_agents"
CATALOG = ROOT / "semantic_model" / "measure_catalog.yaml"

sys.path.insert(0, str(ROOT))
from mission_control.orchestrator import MissionControlRouter  # noqa: E402


def load_known_measures() -> set[str]:
    cat = yaml.safe_load(CATALOG.read_text())
    return {m["name"] for m in cat["measures"]}


def main() -> int:
    router = MissionControlRouter()
    measures = load_known_measures()

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

    print(f"[eval] cases happy={len(happy)} refusal={len(refusals)}")
    print(f"[eval] routing accuracy: {routing_ok}/{len(happy)} = {routing_acc:.2%}")
    print(f"[eval] refusal accuracy: {refusal_ok}/{len(refusals)} = {refusal_acc:.2%}")
    print(f"[eval] measure-resolution: {len(happy) * 1 - len(measure_fail)}/{sum(len(c['expected_measures']) for c in happy)} unique-OK")

    fails = []
    if len(happy) < 30:
        fails.append(f"only {len(happy)} happy-path cases (need >= 30)")
    if routing_acc < 0.90:
        fails.append(f"routing accuracy {routing_acc:.2%} < 90%")
    if refusal_acc < 1.0:
        fails.append(f"refusal accuracy {refusal_acc:.2%} < 100%")
    if measure_fail:
        fails.append(f"{len(measure_fail)} measure refs not in catalog")

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

    if fails:
        print(f"\n[eval] FAIL - {len(fails)} gate(s):")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\n[eval] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

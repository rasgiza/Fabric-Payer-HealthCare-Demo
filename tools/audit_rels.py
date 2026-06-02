"""
audit_rels.py - Verify every relationship in payer_ontology.yaml has 100%
endpoint resolution in the built graph. Fails (exit 1) on any unresolved
edges. Used as Phase 3 gate.
"""
from __future__ import annotations
import argparse
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", default="smoke")
    p.add_argument("--ontology", default=str(ROOT / "ontology" / "payer_ontology.yaml"))
    args = p.parse_args()

    onto = yaml.safe_load(Path(args.ontology).read_text())
    declared_rels = {r["name"]: (r["from"], r["to"]) for r in onto["relationships"]}
    built_flags = {r["name"]: r.get("built", True) and not r.get("synthetic", False)
                   for r in onto["relationships"]}

    gpath = ROOT / "data" / "graph" / args.run_id / "payer_graph.gpickle"
    if not gpath.exists():
        print(f"[audit] missing graph {gpath}", file=sys.stderr)
        return 2
    with gpath.open("rb") as f:
        G = pickle.load(f)

    # For each edge in the graph, verify the source/target types match the
    # declared relationship's expected endpoints.
    by_rel = defaultdict(lambda: {"ok": 0, "type_mismatch": 0, "missing_node": 0})
    edge_rels_seen = set()

    for s, t, k, d in G.edges(keys=True, data=True):
        rel = d.get("rel", k)
        edge_rels_seen.add(rel)
        s_attr = G.nodes.get(s, {})
        t_attr = G.nodes.get(t, {})
        if not s_attr or not t_attr:
            by_rel[rel]["missing_node"] += 1
            continue
        if rel not in declared_rels:
            # Edge present in graph but not declared in ontology — record as mismatch
            by_rel[rel]["type_mismatch"] += 1
            continue
        exp_s, exp_t = declared_rels[rel]
        if s_attr.get("type") != exp_s or t_attr.get("type") != exp_t:
            by_rel[rel]["type_mismatch"] += 1
        else:
            by_rel[rel]["ok"] += 1

    # Report
    print("[audit] relationship resolution report")
    print(f"  ontology relationships declared: {len(declared_rels)}")
    print(f"  graph relationships present:     {len(edge_rels_seen)}")
    print()
    total_violations = 0
    print(f"  {'relationship':28s} {'ok':>10s} {'type_mismatch':>15s} {'missing_node':>14s}")
    for rel in sorted(declared_rels):
        c = by_rel.get(rel, {"ok": 0, "type_mismatch": 0, "missing_node": 0})
        v = c["type_mismatch"] + c["missing_node"]
        total_violations += v
        marker = " " if v == 0 else "!"
        print(f"  {marker} {rel:26s} {c['ok']:>10,} {c['type_mismatch']:>15,} {c['missing_node']:>14,}")

    # Relationships declared but absent from graph (zero edges)
    declared_missing = sorted(set(declared_rels) - edge_rels_seen)
    if declared_missing:
        print(f"\n  declared relationships with 0 edges in graph:")
        for r in declared_missing:
            spec = next((x for x in onto["relationships"] if x["name"] == r), {})
            if spec.get("synthetic"):
                tag = "(synthetic - Phase 6)"
            elif not spec.get("built", True):
                tag = "(built: false - Phase 7 deploy only)"
            else:
                tag = "(MISSING)"
                total_violations += 1
            print(f"    - {r} {tag}")

    print()
    if total_violations == 0:
        print("[audit] PASS - 0 endpoint violations")
        return 0
    print(f"[audit] FAIL - {total_violations:,} violations")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

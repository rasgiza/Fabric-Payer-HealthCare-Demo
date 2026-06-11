"""
eval_graph.py - Run ontology eval set against the built NetworkX graph.

Approach:
  - The graph is the ground truth (deterministic).
  - Each Q-ONTO-NN question has a declarative traversal spec; we execute it on
    the graph to get the "expected" value, then echo that as the agent's would-be
    target answer. The eval here is structural (does the traversal resolve?
    does it produce a non-degenerate value? does it match for calibration?).
  - The 16 calibration pairs check yes/no factuality (precision/recall surrogate).
    Calibrated accuracy >= 0.85 is the gate.

The Foundry agent eval (Phase 5) will run the same questions against the live
agent and score answers vs. the values produced here.
"""
from __future__ import annotations

import argparse
import json
import pickle
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_graph(run_id: str):
    gpath = ROOT / "data" / "graph" / run_id / "payer_graph.gpickle"
    with gpath.open("rb") as f:
        return pickle.load(f)


def edges_by_rel(G, rel):
    return [(s, t) for s, t, k in G.edges(keys=True) if k == rel]


def execute(G, spec):
    t = spec["type"]

    if t == "count_edges":
        edges = edges_by_rel(G, spec["edge"])
        if "target_filter" in spec:
            tf = spec["target_filter"]
            ids = set(tf.get("id_in", []))
            edges = [(s, x) for s, x in edges if any(x.endswith(f":{i}") for i in ids)]
        return len(edges)

    if t == "count_distinct_targets":
        return len({t_ for _, t_ in edges_by_rel(G, spec["edge"])})

    if t == "count_distinct_sources":
        return len({s for s, _ in edges_by_rel(G, spec["edge"])})

    if t == "count_nodes":
        return sum(1 for _, d in G.nodes(data=True) if d.get("type") == spec["node_type"])

    if t == "argmax_outdegree":
        from_type = spec["from_type"]
        rel = spec["edge"]
        deg = Counter()
        for s, _, k in G.edges(keys=True):
            if k == rel and G.nodes[s].get("type") == from_type:
                deg[s] += 1
        if not deg:
            return None
        return deg.most_common(1)[0]

    if t == "ratio":
        num = execute(G, spec["numerator"])
        den = execute(G, spec["denominator"])
        return None if not den else round(num / den, 4)

    if t == "count_nodes_with_edge_in":
        rels = spec["edges"]
        nodes = set()
        for _s, t_, k in G.edges(keys=True):
            if k in rels:
                nodes.add(t_)
        return len(nodes)

    if t == "count_distinct_path":
        # 2-hop: count distinct anchors that reach via path
        rels = spec["path"]
        anchor = spec["anchor"]  # 'source' or 'target'
        # Build adjacency by rel
        first = defaultdict(set)
        for s, t_, k in G.edges(keys=True):
            if k == rels[0]:
                first[s].add(t_)
        second = defaultdict(set)
        for s, t_, k in G.edges(keys=True):
            if k == rels[1]:
                second[s].add(t_)
        anchors = set()
        for src, mids in first.items():
            for m in mids:
                if m in second and second[m]:
                    anchors.add(src if anchor == "source" else m)
        return len(anchors)

    if t == "count_paths":
        rels = spec["path"]
        first = defaultdict(set)
        for s, t_, k in G.edges(keys=True):
            if k == rels[0]:
                first[s].add(t_)
        second = defaultdict(set)
        for s, t_, k in G.edges(keys=True):
            if k == rels[1]:
                second[s].add(t_)
        verify = spec.get("verify_loop", {})
        loop_edge = verify.get("via_edge")
        loop_pairs = set()
        if loop_edge:
            for s, t_, k in G.edges(keys=True):
                if k == loop_edge:
                    loop_pairs.add((s, t_))  # Payer -> Member for coversMember
        # Path: Member -filedClaim-> Claim -claimAdjudicatedBy-> Payer.
        # Verify loop: (Payer, Member) in coversMember.
        count = 0
        for member, claims in first.items():
            for cl in claims:
                for payer in second.get(cl, []):
                    if (payer, member) in loop_pairs:
                        count += 1
        return count

    if t == "nonzero_edges":
        return len(edges_by_rel(G, spec["edge"])) > 0

    if t == "nonzero_path":
        return execute(G, {"type": "count_distinct_path", "path": spec["path"], "anchor": "source"}) > 0

    raise ValueError(f"unknown traversal type: {t}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", default="smoke")
    p.add_argument("--eval-set", default=str(ROOT / "ontology" / "eval_set.yaml"))
    p.add_argument("--out", default=None, help="Write JSON results here")
    args = p.parse_args()

    G = load_graph(args.run_id)
    es = yaml.safe_load(Path(args.eval_set).read_text())

    print(f"[eval] loaded graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges\n")

    # KPI questions
    print("[eval] KPI questions (Q-ONTO-*)")
    kpi_results = []
    for q in es["eval_questions"]:
        try:
            val = execute(G, q["traversal"])
            ok = val is not None and val != 0 and val is not False
            print(f"  {'OK ' if ok else 'WARN'} {q['id']:11s} ({q['persona']:9s}) -> {val}")
            kpi_results.append({"id": q["id"], "persona": q["persona"], "value": val, "ok": ok})
        except Exception as e:
            print(f"  FAIL {q['id']:11s} -> {e}")
            kpi_results.append({"id": q["id"], "error": str(e), "ok": False})

    # Calibration pairs
    print("\n[eval] calibration (yes/no factuality)")
    cal_correct = 0
    cal_total = 0
    cal_results = []
    for c in es["calibration"]:
        actual = bool(execute(G, c["traversal"]))
        expected = c["expected"] == "yes" or c["expected"] is True
        match = actual == expected
        cal_correct += int(match)
        cal_total += 1
        flag = "OK " if match else "FAIL"
        print(f"  {flag} {c['id']:7s} expected={c['expected']:>3} actual={'yes' if actual else 'no':>3}  {c['question']}")
        cal_results.append({"id": c["id"], "expected": c["expected"], "actual": "yes" if actual else "no", "match": match})

    accuracy = cal_correct / cal_total if cal_total else 0.0
    kpi_ok = sum(1 for r in kpi_results if r.get("ok"))
    print()
    print(f"[eval] KPI questions: {kpi_ok}/{len(kpi_results)} returned non-degenerate values")
    print(f"[eval] calibration:   {cal_correct}/{cal_total} = {accuracy:.3f} (gate: >= 0.85)")

    summary = {
        "run_id": args.run_id,
        "kpi_total": len(kpi_results),
        "kpi_ok": kpi_ok,
        "calibration_total": cal_total,
        "calibration_correct": cal_correct,
        "calibration_accuracy": round(accuracy, 4),
        "passed": accuracy >= 0.85 and kpi_ok == len(kpi_results),
        "kpi_results": kpi_results,
        "calibration_results": cal_results,
    }
    out_path = Path(args.out) if args.out else (ROOT / "data" / "graph" / args.run_id / "eval_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"[eval] wrote {out_path}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

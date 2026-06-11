"""
build_graph.py - Build a NetworkX MultiDiGraph from the gold lakehouse for
local ontology traversal + Phase 5 ontology agent eval. Mirrors the entity/
relationship spec in ontology/payer_ontology.yaml.

Output:
    data/graph/<run_id>/payer_graph.gpickle  - serialized NetworkX graph
    data/graph/<run_id>/graph_summary.json   - node/edge counts per type
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from collections import Counter
from pathlib import Path

import duckdb
import networkx as nx

ROOT = Path(__file__).resolve().parent.parent
LAKE = ROOT / "data" / "lakehouse"
OUT = ROOT / "data" / "graph"


def _q(con, sql):
    return con.execute(sql).fetchdf()


def build(run_id: str) -> int:
    gold = LAKE / run_id / "gold"
    silver = LAKE / run_id / "silver"
    if not gold.exists():
        print(f"[graph] missing {gold}", file=sys.stderr)
        return 2

    con = duckdb.connect(":memory:")
    # Register all parquet files as views
    for p in list(gold.glob("*.parquet")) + list(silver.glob("*.parquet")):
        layer = "gold" if p.parent.name == "gold" else "silver"
        con.execute(f"CREATE OR REPLACE VIEW {layer}_{p.stem} AS SELECT * FROM read_parquet('{p.as_posix()}')")

    G = nx.MultiDiGraph()
    print("[graph] adding nodes...")

    # Node loaders: (type, sql, key_cols)
    node_specs = [
        ("Member",       "SELECT member_id AS id, lob, product, payer_id, age_band, zip3 FROM gold_dim_member"),
        ("Provider",     "SELECT provider_npi AS id, specialty_type, in_network_flag, apm_tier FROM gold_dim_provider"),
        ("Payer",        "SELECT payer_id AS id, payer_name, parent_org FROM gold_dim_payer"),
        ("LOB",          "SELECT lob_id AS id FROM gold_dim_lob"),
        ("Product",      "SELECT product_id AS id, lob FROM gold_dim_product"),
        ("Diagnosis",    "SELECT dx_code AS id FROM gold_dim_diagnosis"),
        ("Procedure",    "SELECT cpt_hcpcs AS id FROM gold_dim_procedure"),
        ("Drug",         "SELECT ndc_code AS id, drug_class FROM gold_dim_drug"),
        ("HCC",          "SELECT hcc_id AS id FROM gold_dim_hcc"),
        ("Claim",        "SELECT DISTINCT claim_id AS id, payer_id, plan_year, denied_int, carc_code FROM gold_fact_claim"),
        ("RxClaim",      "SELECT rx_claim_id AS id, drug_class, plan_year FROM gold_fact_rx_claim"),
        ("Authorization","SELECT auth_id AS id, decision, request_type, sla_met FROM gold_fact_auth"),
        ("Appeal",       "SELECT appeal_id AS id, level, decision FROM gold_fact_appeal"),
        ("HEDISMeasure", "SELECT DISTINCT measure_id AS id FROM gold_fact_quality_event"),
        ("CARC",         "SELECT DISTINCT carc_code AS id FROM silver_claims_header WHERE carc_code IS NOT NULL"),
        ("SDOHArea",     "SELECT DISTINCT zip3 AS id FROM gold_dim_member WHERE zip3 IS NOT NULL"),
    ]
    for ntype, sql in node_specs:
        df = _q(con, sql)
        for row in df.itertuples(index=False):
            attrs = {k: v for k, v in row._asdict().items() if k != "id"}
            attrs["type"] = ntype
            G.add_node(f"{ntype}:{row.id}", **attrs)
        print(f"  + {ntype:14s} {len(df):>7,}")

    print("[graph] adding edges...")
    edge_specs = [
        ("coversMember",         "SELECT payer_id AS s, member_id AS t FROM gold_dim_member",
         "Payer", "Member"),
        ("filedClaim",           "SELECT DISTINCT member_id AS s, claim_id AS t FROM gold_fact_claim",
         "Member", "Claim"),
        ("billsClaim",           "SELECT DISTINCT provider_npi AS s, claim_id AS t FROM gold_fact_claim",
         "Provider", "Claim"),
        ("claimAdjudicatedBy",   "SELECT DISTINCT claim_id AS s, payer_id AS t FROM gold_fact_claim",
         "Claim", "Payer"),
        ("claimHasPrimaryDx",    "SELECT DISTINCT claim_id AS s, primary_dx_code AS t FROM gold_fact_claim WHERE primary_dx_code IS NOT NULL",
         "Claim", "Diagnosis"),
        ("claimDeniedWith",      "SELECT DISTINCT claim_id AS s, carc_code AS t FROM gold_fact_claim WHERE denied_int = 1 AND carc_code IS NOT NULL",
         "Claim", "CARC"),
        ("claimRequiresAuth",    "SELECT linked_claim_id AS s, auth_id AS t FROM gold_fact_auth WHERE linked_claim_id IS NOT NULL",
         "Claim", "Authorization"),
        ("appealOf",             "SELECT appeal_id AS s, claim_id AS t FROM gold_fact_appeal",
         "Appeal", "Claim"),
        ("filledRx",             "SELECT member_id AS s, rx_claim_id AS t FROM gold_fact_rx_claim",
         "Member", "RxClaim"),
        ("prescribedDrug",       "SELECT rx_claim_id AS s, ndc_code AS t FROM gold_fact_rx_claim",
         "RxClaim", "Drug"),
        ("rxPrescribedBy",       "SELECT prescriber_npi AS s, rx_claim_id AS t FROM gold_fact_rx_claim",
         "Provider", "RxClaim"),
        ("memberHasCondition",   "SELECT member_id AS s, hcc_v28 AS t FROM silver_conditions WHERE hcc_v28 IS NOT NULL",
         "Member", "HCC"),
        ("memberQualityEvent",   "SELECT member_id AS s, measure_id AS t FROM gold_fact_quality_event WHERE compliant",
         "Member", "HEDISMeasure"),
        ("pcpOfMember",          "SELECT pcp_provider_id AS s, member_id AS t FROM gold_dim_member",
         "Provider", "Member"),
        ("livesInArea",          "SELECT member_id AS s, zip3 AS t FROM gold_dim_member WHERE zip3 IS NOT NULL",
         "Member", "SDOHArea"),
        ("memberInProduct",      "SELECT DISTINCT member_id AS s, product AS t FROM gold_dim_member",
         "Member", "Product"),
        ("productOfLOB",         "SELECT DISTINCT product_id AS s, lob AS t FROM gold_dim_product",
         "Product", "LOB"),
    ]
    edge_count = Counter()
    for rel, sql, stype, ttype in edge_specs:
        df = _q(con, sql)
        added = 0
        for row in df.itertuples(index=False):
            s = f"{stype}:{row.s}"; t = f"{ttype}:{row.t}"
            if s in G and t in G:
                G.add_edge(s, t, key=rel, rel=rel)
                added += 1
        edge_count[rel] = added
        print(f"  + {rel:24s} {added:>7,}")

    out_dir = OUT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "payer_graph.gpickle").open("wb") as f:
        pickle.dump(G, f)
    summary = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "node_types": dict(Counter(d["type"] for _, d in G.nodes(data=True))),
        "edge_types": dict(edge_count),
    }
    (out_dir / "graph_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\n[graph] {summary['nodes']:,} nodes, {summary['edges']:,} edges -> {out_dir}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", default="smoke")
    args = p.parse_args()
    return build(args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())

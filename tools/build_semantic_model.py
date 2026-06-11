"""
build_semantic_model.py - Generate TMDL files for the PayerAnalytics semantic model
from the gold lakehouse schema + measure_catalog.yaml.

Output structure:
  semantic_model/PayerAnalytics.SemanticModel/
    definition.pbism                 (JSON header)
    definition/
      database.tmdl
      model.tmdl                     (datasource + culture + relationships)
      tables/<table>.tmdl            (one per gold table; measures attached to fact_claim)

Phase 7 (fabric-cicd) replaces the parquet-path expressions with Direct Lake
bindings against the deployed lakehouse SQL endpoint.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "data" / "lakehouse" / "smoke" / "gold"
CATALOG = ROOT / "semantic_model" / "measure_catalog.yaml"
OUT = ROOT / "semantic_model" / "PayerAnalytics.SemanticModel"

# Map duckdb / arrow types to TMDL data types.
TYPE_MAP = {
    "BIGINT": "int64", "INTEGER": "int64", "SMALLINT": "int64", "TINYINT": "int64",
    "DOUBLE": "double", "FLOAT": "double", "DECIMAL": "decimal",
    "VARCHAR": "string", "TEXT": "string",
    "BOOLEAN": "boolean",
    "DATE": "dateTime", "TIMESTAMP": "dateTime", "TIMESTAMP_NS": "dateTime", "TIMESTAMP WITH TIME ZONE": "dateTime",
}

# (from_table, from_col)  ->  (to_table, to_col)  : 1-to-many from many-side declared
RELATIONSHIPS = [
    ("fact_claim",          "member_id",        "dim_member",      "member_id"),
    ("fact_claim",          "provider_npi",     "dim_provider",    "provider_npi"),
    ("fact_claim",          "payer_id",         "dim_payer",       "payer_id"),
    ("fact_claim",          "primary_dx_code",  "dim_diagnosis",   "dx_code"),
    ("fact_claim",          "service_date",     "dim_date",        "date"),
    ("fact_rx_claim",       "member_id",        "dim_member",      "member_id"),
    ("fact_rx_claim",       "ndc_code",         "dim_drug",        "ndc_code"),
    ("fact_rx_claim",       "fill_date",        "dim_date",        "date"),
    ("fact_auth",           "member_id",        "dim_member",      "member_id"),
    ("fact_auth",           "request_date",     "dim_date",        "date"),
    ("fact_appeal",         "claim_id",         "fact_claim",      "claim_id"),
    ("fact_member_month",   "member_id",        "dim_member",      "member_id"),
    ("fact_member_month",   "month_start",      "dim_date",        "date"),
    ("fact_premium",        "member_id",        "dim_member",      "member_id"),
    ("fact_quality_event",  "member_id",        "dim_member",      "member_id"),
    ("fact_raf_score",      "member_id",        "dim_member",      "member_id"),
    ("dim_member",          "payer_id",         "dim_payer",       "payer_id"),
    ("dim_member",          "lob",              "dim_lob",         "lob_id"),
    ("dim_product",         "lob",              "dim_lob",         "lob_id"),
]

# Where to attach each measure (group by folder is informational; all measures
# live on fact_claim by convention so they roam across the model).
MEASURE_HOST = "fact_claim"


def col_type(duck_type: str) -> str:
    base = duck_type.split("(")[0].strip().upper()
    return TYPE_MAP.get(base, "string")


def get_schema(con, table: str):
    df = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{(GOLD / (table + '.parquet')).as_posix()}')").fetchdf()
    return [(r["column_name"], col_type(r["column_type"])) for _, r in df.iterrows()]


def emit_table_tmdl(table: str, columns, measures=None) -> str:
    parquet_uri = (GOLD / f"{table}.parquet").as_posix()
    lines = [
        f"table {table}",
        f"\tlineageTag: {table}",
        "",
    ]
    for col, dtype in columns:
        lines += [
            f"\tcolumn {col}",
            f"\t\tdataType: {dtype}",
            f"\t\tlineageTag: {table}.{col}",
            "\t\tsummarizeBy: none",
            f"\t\tsourceColumn: {col}",
            "",
        ]
    if measures:
        for m in measures:
            lines += [
                f"\tmeasure {m['name']} = {m['dax']}",
                f"\t\tdisplayFolder: {m['folder']}",
                f"\t\tformatString: {m['format']}",
                f"\t\tlineageTag: measure.{m['name']}",
                "",
                f"\t\tannotation Description = {m['description']}",
                f"\t\tannotation Persona = {m['persona']}",
                "",
            ]
    lines += [
        f"\tpartition {table} = m",
        "\t\tmode: import",
        "\t\tsource = ",
        "\t\t\tlet",
        f'\t\t\t  Source = Parquet.Document(File.Contents("{parquet_uri}"))',
        "\t\t\tin",
        "\t\t\t  Source",
        "",
        "\tannotation PBI_ResultType = Table",
    ]
    return "\n".join(lines) + "\n"


def emit_relationships_tmdl() -> str:
    lines = []
    for _i, (ft, fc, tt, tc) in enumerate(RELATIONSHIPS):
        rid = f"rel_{ft}_{fc}_{tt}".replace(".", "_")
        lines += [
            f"relationship {rid}",
            f"\tfromColumn: {ft}.{fc}",
            f"\ttoColumn: {tt}.{tc}",
            "\tjoinOnDateBehavior: datePartOnly" if "date" in fc.lower() or fc.lower().endswith("_date") or fc.lower() == "month_start" else "",
            "",
        ]
    return "\n".join([l for l in lines if l != ""])


def emit_database_tmdl() -> str:
    return ('database\n'
            '\tcompatibilityLevel: 1605\n'
            '\n'
            '\tmodel Model\n'
            '\t\tculture: en-US\n'
            '\t\tdiscourageImplicitMeasures\n'
            '\t\tdefaultPowerBIDataSourceVersion: powerBI_V3\n')


def emit_model_tmdl(rels_text: str) -> str:
    return ("model Model\n"
            "\tculture: en-US\n"
            "\tdataAccessOptions\n"
            "\t\tlegacyRedirects\n"
            "\t\treturnErrorValuesAsNull\n"
            "\n"
            "\tannotation PBI_QueryOrder = []\n"
            "\n"
            f"{rels_text}\n")


def emit_pbism() -> str:
    return json.dumps({
        "version": "4.0",
        "settings": {}
    }, indent=2)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--clean", action="store_true", help="Remove and recreate output dir")
    args = p.parse_args()

    if not GOLD.exists():
        print(f"[sm] missing {GOLD}; run ETL first", file=sys.stderr)
        return 2

    if args.clean and OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "definition" / "tables").mkdir(parents=True, exist_ok=True)

    catalog = yaml.safe_load(CATALOG.read_text())
    measures = catalog["measures"]
    print(f"[sm] {len(measures)} measures in catalog")

    con = duckdb.connect(":memory:")
    tables = sorted(p.stem for p in GOLD.glob("*.parquet"))
    print(f"[sm] {len(tables)} gold tables")

    for t in tables:
        cols = get_schema(con, t)
        attach = measures if t == MEASURE_HOST else None
        (OUT / "definition" / "tables" / f"{t}.tmdl").write_text(emit_table_tmdl(t, cols, attach), encoding="utf-8")
        print(f"  + tables/{t}.tmdl  ({len(cols)} cols{', '+str(len(attach))+' measures' if attach else ''})")

    rels_text = emit_relationships_tmdl()
    (OUT / "definition" / "database.tmdl").write_text(emit_database_tmdl(), encoding="utf-8")
    (OUT / "definition" / "model.tmdl").write_text(emit_model_tmdl(rels_text), encoding="utf-8")
    (OUT / "definition.pbism").write_text(emit_pbism(), encoding="utf-8")
    print(f"  + database.tmdl, model.tmdl ({len(RELATIONSHIPS)} relationships)")

    print(f"\n[sm] OK -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

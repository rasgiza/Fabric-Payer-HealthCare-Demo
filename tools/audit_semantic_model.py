"""
audit_semantic_model.py - Validate that every measure DAX references columns
that exist in the gold parquet schemas, and that every PBIR visual.field
reference resolves to a real measure or column.

Used as Phase 4 gate.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

import duckdb
import yaml

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "data" / "lakehouse" / "smoke" / "gold"
CATALOG = ROOT / "semantic_model" / "measure_catalog.yaml"
PAGES = ROOT / "powerbi" / "pages.yaml"

COLREF = re.compile(r"'([^']+)'\[([^\]]+)\]")
MEASUREREF = re.compile(r"\[([A-Za-z][A-Za-z0-9_]*)\]")


def load_schemas():
    con = duckdb.connect(":memory:")
    schemas = {}
    for p in GOLD.glob("*.parquet"):
        df = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{p.as_posix()}')").fetchdf()
        schemas[p.stem] = set(df["column_name"].tolist())
    return schemas


def main() -> int:
    schemas = load_schemas()
    catalog = yaml.safe_load(CATALOG.read_text())
    measures = {m["name"]: m for m in catalog["measures"]}

    errors = []

    # 1. Validate measure DAX column references
    for m in measures.values():
        for tbl, col in COLREF.findall(m["dax"]):
            if tbl not in schemas:
                errors.append(f"[measure {m['name']}] table '{tbl}' not in gold")
            elif col not in schemas[tbl]:
                errors.append(f"[measure {m['name']}] column '{tbl}.{col}' not in gold")
        for ref in MEASUREREF.findall(m["dax"]):
            if ref in measures or ref == m["name"]:
                continue
            # bracket refs may also be column refs already captured by COLREF; check
            if not any(ref == col for cols in schemas.values() for col in cols):
                # Not a measure, not a column anywhere → flag (but allow common DAX keywords)
                if ref.upper() in {"BLANK", "TRUE", "FALSE"}:
                    continue
                errors.append(f"[measure {m['name']}] unresolved bracket-ref [{ref}]")

    # 2. Validate PBIR field references
    spec = yaml.safe_load(PAGES.read_text())
    for page in spec["pages"]:
        for v in page["visuals"]:
            for ref in v.get("measures", []):
                if ref not in measures:
                    errors.append(f"[page {page['id']}/{v['id']}] unknown measure '{ref}'")
            for f in (v.get("fields") or []) + ([v["axis"]] if v.get("axis") else []):
                if not f or "." not in f:
                    continue
                tbl, col = f.split(".", 1)
                # synthetic columns like dim_date.year_month are allowed (computed)
                if tbl in schemas and col not in schemas[tbl] and not col in {"year_month"}:
                    errors.append(f"[page {page['id']}/{v['id']}] field '{f}' not in gold")
                if tbl not in schemas:
                    errors.append(f"[page {page['id']}/{v['id']}] table '{tbl}' not in gold")

    print(f"[audit_sm] {len(measures)} measures, {sum(len(p['visuals']) for p in spec['pages'])} visuals")
    if not errors:
        print("[audit_sm] PASS - all measure & visual refs resolve")
        return 0
    print(f"[audit_sm] FAIL - {len(errors)} unresolved refs:")
    for e in errors[:50]:
        print(f"  {e}")
    if len(errors) > 50:
        print(f"  ... and {len(errors) - 50} more")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

# Fabric notebook source

# METADATA **{"language":"markdown"}**

# MARKDOWN **{"language":"markdown"}**

# # NB_01 - Bronze Ingest (Payer)
#
# Reads the 21 synthetic CSVs uploaded into `lh_bronze_raw/Files/synth/<run_id>/`
# and lands them as Delta tables in `lh_bronze_raw/Tables/`.
#
# **Default lakehouse must be `lh_bronze_raw` when running manually.**
#
# **Parameters** (set by `PL_Payer_Master` or via the launcher):
# - `run_id`  — synth run folder under `Files/synth/` (default: `smoke`)
# - `mode`    — `overwrite` (default) or `append`

# METADATA **{"language":"python"}**

# PARAMETERS CELL **{"language":"python"}**

run_id = "smoke"
mode = "overwrite"

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

from datetime import datetime
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

assert mode in ("overwrite", "append"), f"invalid mode {mode!r}"
src_root = f"Files/synth/{run_id}"
print(f"[bronze] start={datetime.now().isoformat(timespec='seconds')} run_id={run_id} mode={mode}")
print(f"[bronze] src={src_root}")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# 21-table inventory matches tools/run_local_etl.py BRONZE_TABLES (kept in sync
# by tests/test_notebook_shape.py).
BRONZE_TABLES = [
    "members", "enrollment_spans", "providers", "payers", "conditions",
    "claims_header", "claims_line", "rx_claims", "auths", "appeals",
    "premiums", "raf_scores", "quality_events",
    "pharmacy_pa", "provider_sanctions", "provider_directory_attestation",
    "readmission", "sdoh_assessment", "cahps_response", "outreach",
    "vbc_attribution",
]

results = []
for t in BRONZE_TABLES:
    src = f"{src_root}/{t}.csv"
    df = (
        spark.read
             .option("header", "true")
             .option("inferSchema", "true")
             .csv(src)
    )
    n = df.count()
    (df.write.mode(mode).format("delta").saveAsTable(t))
    results.append((t, n))
    print(f"  [ok] {t:<35s} rows={n}")

print(f"[bronze] wrote {len(results)} tables")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# Smoke check: every bronze table queryable from the metastore
for t, _ in results:
    spark.sql(f"SELECT COUNT(*) FROM {t}").collect()
print("[bronze] PASS — all 21 tables registered in lh_bronze_raw")

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

# Fabric Spark + Delta tuning. V-Order is the Direct Lake prerequisite; without
# it, a semantic model on these tables silently falls back to DirectQuery.
# Optimize Write + Auto Compact keep file sizes in the 128 MB–1 GB sweet spot
# without manual OPTIMIZE between runs. AQE + skewJoin handle the wide gold
# joins. Shuffle partitions are tuned for smoke scale (~500 members); raise to
# 200 (default) for full-scale runs.
spark.conf.set("spark.sql.parquet.vorder.enabled", "true")
spark.conf.set("spark.microsoft.delta.optimizeWrite.enabled", "true")
spark.conf.set("spark.microsoft.delta.optimizeWrite.binSize", "1073741824")
spark.conf.set("spark.databricks.delta.autoCompact.enabled", "true")
spark.conf.set("spark.databricks.delta.properties.defaults.enableDeletionVectors", "true")
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.shuffle.partitions", "16")

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

# Delta write options applied to every bronze table. overwriteSchema=true keeps
# the overwrite path safe when synth column sets evolve between runs. CDF lets
# downstream silver use MERGE / readChangeFeed instead of full re-scan.
_DELTA_WRITE_OPTS = {
    "overwriteSchema": "true",
    "delta.enableChangeDataFeed": "true",
    "delta.enableDeletionVectors": "true",
}

# Critical-column casts. inferSchema is fine for synth but column types must be
# deterministic for downstream silver SQL — pin the few columns where bad
# inference would cause silent drift (dates as strings, IDs as longs, etc.).
_BRONZE_CASTS: dict[str, dict[str, str]] = {
    "members":          {"effective_year": "INT", "dob_year": "INT", "age_at_year_end": "INT"},
    "enrollment_spans": {"plan_year": "INT", "start_month": "INT", "end_month": "INT"},
    "claims_header":    {"service_date": "DATE", "plan_year": "INT"},
    "claims_line":      {"line_no": "INT", "units": "DECIMAL(10,2)",
                         "billed_amount": "DECIMAL(12,2)", "allowed_amount": "DECIMAL(12,2)",
                         "paid_amount": "DECIMAL(12,2)"},
    "rx_claims":        {"fill_date": "DATE", "days_supply": "INT", "quantity": "DECIMAL(10,2)"},
    "auths":            {"tat_hours": "DECIMAL(8,2)"},
    "appeals":          {},
    "premiums":         {"plan_year": "INT", "member_months": "INT",
                         "premium_total": "DECIMAL(14,2)"},
    "raf_scores":       {"plan_year": "INT", "raf_score": "DECIMAL(6,3)"},
    "quality_events":   {"plan_year": "INT"},
    "pharmacy_pa":      {},
    "readmission":      {"index_dis_date": "DATE", "readmit_date": "DATE", "plan_year": "INT"},
    "sdoh_assessment":  {"assessment_date": "DATE", "plan_year": "INT"},
    "outreach":         {"outreach_date": "DATE"},
}

results: list[tuple[str, int]] = []
for t in BRONZE_TABLES:
    src = f"{src_root}/{t}.csv"
    df = (
        spark.read
             .option("header", "true")
             .option("inferSchema", "true")
             .option("mode", "FAILFAST")
             .csv(src)
    )
    for col, sql_type in _BRONZE_CASTS.get(t, {}).items():
        if col in df.columns:
            df = df.withColumn(col, df[col].cast(sql_type))

    writer = df.write.mode(mode).format("delta")
    for k, v in _DELTA_WRITE_OPTS.items():
        writer = writer.option(k, v)
    writer.saveAsTable(t)

    # Make Delta properties sticky so MERGE / OPTIMIZE called by silver inherit
    # them, then read row count from the freshly written table (no extra scan
    # of the source CSV).
    spark.sql(f"""
        ALTER TABLE {t} SET TBLPROPERTIES (
            'delta.enableChangeDataFeed' = 'true',
            'delta.enableDeletionVectors' = 'true',
            'delta.autoOptimize.optimizeWrite' = 'true',
            'delta.autoOptimize.autoCompact' = 'true'
        )
    """)
    n = spark.sql(f"SELECT COUNT(*) AS n FROM {t}").collect()[0]["n"]
    results.append((t, n))
    print(f"  [ok] {t:<35s} rows={n}")

print(f"[bronze] wrote {len(results)} tables")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# Compact the small files left behind by the per-table writes so silver and
# gold see large parquet shards and V-Order kicks in immediately. Skipped on
# append (incremental) so we don't rewrite history every run.
if mode == "overwrite":
    for t, _ in results:
        spark.sql(f"OPTIMIZE {t}")
    print(f"[bronze] OPTIMIZE complete for {len(results)} tables")
else:
    print(f"[bronze] mode={mode}, skipping OPTIMIZE (run NB_99_Maintenance for periodic compaction)")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# Smoke check: every bronze table queryable from the metastore
for t, _ in results:
    spark.sql(f"SELECT COUNT(*) FROM {t}").collect()
print("[bronze] PASS — all 21 tables registered in lh_bronze_raw")

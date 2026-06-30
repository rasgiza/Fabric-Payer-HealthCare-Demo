# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "a2000002-0001-0001-0001-000000000002",
# META       "default_lakehouse_name": "lh_silver_stage",
# META       "default_lakehouse_workspace_id": "a0000000-0001-0001-0001-000000000000",
# META       "known_lakehouses": [
# META         {"id": "a2000002-0001-0001-0001-000000000001"},
# META         {"id": "a2000002-0001-0001-0001-000000000002"},
# META         {"id": "a2000002-0001-0001-0001-000000000003"},
# META         {"id": "a2000002-0001-0001-0001-000000000004"}
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# METADATA ********************

# META {
# META   "language": "markdown"
# META }

# # NB_02 - Silver Transform (Payer)
#
# Reads bronze Delta tables from `lh_bronze_raw` via shortcut/cross-lakehouse
# access and writes silver-stage + silver-ods Delta tables into `lh_silver_stage`
# (light de-id, date keys, member-month explosion) and `lh_silver_ods` (the
# A.0c passthroughs with derived date keys).
#
# **Default lakehouse must be `lh_silver_stage` when running manually**, with
# `lh_bronze_raw` attached as a secondary so the three-part names below resolve.
#
# SQL is a direct port of `tools/run_local_etl.py::silver()` — same column
# names, same semantics. DuckDB-only constructs are translated:
#   - `EXTRACT(year FROM d)`     → `YEAR(d)`
#   - `strftime(d, '%Y%m%d')`    → `DATE_FORMAT(d, 'yyyyMMdd')`
#   - `generate_series(1,12)`    → `EXPLODE(SEQUENCE(1,12))`

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

from datetime import datetime
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

# Audit-log run state — emitted at end of notebook into lh_gold_curated.audit_log.
import time as _time, uuid as _uuid, os as _os
_audit_started_at = datetime.utcnow()
_audit_t0 = _time.perf_counter()
_audit_run_uuid = str(_uuid.uuid4())
_audit_run_id = globals().get("run_id", _os.environ.get("AUDIT_RUN_ID", "auto"))
_audit_pipeline = _os.environ.get("AUDIT_PIPELINE", "PL_Payer_Master")
_audit_user = _os.environ.get("USER") or _os.environ.get("USERNAME") or "unknown"
_audit_git_sha = _os.environ.get("GIT_SHA")

# Fabric Spark + Delta tuning — mirrors NB_01. V-Order is the Direct Lake
# prerequisite; without it the PayerAnalytics semantic model silently falls
# back to DirectQuery and Foundry agents lose sub-second latency.
spark.conf.set("spark.sql.parquet.vorder.enabled", "true")
spark.conf.set("spark.microsoft.delta.optimizeWrite.enabled", "true")
spark.conf.set("spark.microsoft.delta.optimizeWrite.binSize", "1073741824")
spark.conf.set("spark.databricks.delta.autoCompact.enabled", "true")
spark.conf.set("spark.databricks.delta.properties.defaults.enableDeletionVectors", "true")
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.shuffle.partitions", "16")

print(f"[silver] start={datetime.now().isoformat(timespec='seconds')}")

BRONZE = "lh_bronze_raw"
STAGE = "lh_silver_stage"
ODS = "lh_silver_ods"

# Applied to every CREATE OR REPLACE TABLE below so Direct Lake, MERGE, and
# downstream Eventstream/Mirroring all get the right defaults from day one.
TBL_PROPS = """
USING DELTA
TBLPROPERTIES (
    'delta.enableChangeDataFeed'       = 'true',
    'delta.enableDeletionVectors'      = 'true',
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
)
"""

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

# ----- dim_date (rich calendar — day-of-week, ISO week, fiscal, weekend/month-end flags) -----
spark.sql(f"""
CREATE OR REPLACE TABLE {STAGE}.dim_date
{TBL_PROPS}
AS
WITH d AS (
    SELECT DISTINCT service_date AS d FROM {BRONZE}.claims_header
    UNION SELECT DISTINCT fill_date FROM {BRONZE}.rx_claims
)
SELECT
    CAST(DATE_FORMAT(d, 'yyyyMMdd') AS INT) AS date_key,
    d                                       AS full_date,
    YEAR(d)                                 AS year,
    MONTH(d)                                AS month,
    DAY(d)                                  AS day,
    QUARTER(d)                              AS quarter,
    WEEKOFYEAR(d)                           AS iso_week,
    DAYOFWEEK(d)                            AS day_of_week,
    DATE_FORMAT(d, 'EEE')                   AS day_name_short,
    DATE_FORMAT(d, 'EEEE')                  AS day_name,
    DATE_FORMAT(d, 'MMM')                   AS month_name_short,
    DATE_FORMAT(d, 'MMMM')                  AS month_name,
    DATE_FORMAT(d, 'yyyy-MM')               AS year_month,
    DATE_FORMAT(d, 'yyyy-Q')                AS year_quarter,
    YEAR(d)                                 AS fiscal_year,
    QUARTER(d)                              AS fiscal_quarter,
    CASE WHEN DAYOFWEEK(d) IN (1,7) THEN TRUE ELSE FALSE END AS is_weekend,
    CASE WHEN LAST_DAY(d) = d THEN TRUE ELSE FALSE END       AS is_month_end,
    CASE WHEN MONTH(d) = 12 AND DAY(d) = 31 THEN TRUE ELSE FALSE END AS is_year_end
FROM d WHERE d IS NOT NULL
""")

# ----- members (light de-id + age band + HEI/SDOH passthrough) -----
spark.sql(f"""
CREATE OR REPLACE TABLE {STAGE}.members
{TBL_PROPS}
AS
SELECT
    member_id, mbi_hash, subscriber_id,
    lob, product, state, race_ethnicity, sex, age_at_year_end, dob_year, zip3,
    payer_id, plan_id, pcp_provider_id, effective_year,
    sdoh_housing_unstable, sdoh_food_insecure, sdoh_transport_barrier,
    lis_de_flag, disability_flag, hei_eligible_flag,
    re_l_collection_method, sogi_collected_flag,
    CASE
        WHEN age_at_year_end < 18 THEN '0-17'
        WHEN age_at_year_end < 35 THEN '18-34'
        WHEN age_at_year_end < 50 THEN '35-49'
        WHEN age_at_year_end < 65 THEN '50-64'
        WHEN age_at_year_end < 75 THEN '65-74'
        WHEN age_at_year_end < 85 THEN '75-84'
        ELSE '85+'
    END AS age_band
FROM {BRONZE}.members
""")

# ----- claims_header (denial flags + date_key) -----
spark.sql(f"""
CREATE OR REPLACE TABLE {STAGE}.claims_header
{TBL_PROPS}
AS
SELECT
    *,
    CAST(DATE_FORMAT(service_date, 'yyyyMMdd') AS INT) AS service_date_key,
    CASE WHEN denied_flag THEN 1 ELSE 0 END AS denied_int,
    CASE WHEN paid_amount > 0 AND NOT denied_flag THEN 1 ELSE 0 END AS paid_int
FROM {BRONZE}.claims_header
""")

# ----- straight passthroughs (silver-stage) -----
for tbl, derived in [
    ("claims_line",     ""),
    ("rx_claims",       ", CAST(DATE_FORMAT(fill_date, 'yyyyMMdd') AS INT) AS fill_date_key"),
    ("auths",           ""),
    ("appeals",         ""),
    ("premiums",        ""),
    ("providers",       ""),
    ("payers",          ""),
    ("conditions",      ""),
    ("raf_scores",      ""),
    ("quality_events",  ""),
]:
    spark.sql(f"""
        CREATE OR REPLACE TABLE {STAGE}.{tbl}
        {TBL_PROPS}
        AS SELECT *{derived} FROM {BRONZE}.{tbl}
    """)

# ----- member_month explosion -----
spark.sql(f"""
CREATE OR REPLACE TABLE {STAGE}.member_month
{TBL_PROPS}
AS
WITH spans AS (
    SELECT member_id, plan_year, start_month, end_month, lob, product, payer_id
    FROM {BRONZE}.enrollment_spans
),
months AS (
    SELECT s.member_id, s.plan_year, m AS month, s.lob, s.product, s.payer_id
    FROM spans s
    LATERAL VIEW EXPLODE(SEQUENCE(1, 12)) AS m
    WHERE m BETWEEN s.start_month AND s.end_month
)
SELECT
    member_id, plan_year, month, lob, product, payer_id,
    CAST(plan_year * 100 + month AS INT) AS year_month_key
FROM months
""")

print("[silver-stage] 14 tables written (dim_date, members, claims_header, claims_line, rx_claims, auths, appeals, premiums, providers, payers, conditions, raf_scores, quality_events, member_month)")

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

# ----- A.0c passthroughs into silver_ods (with derived date keys) -----

spark.sql(f"""
CREATE OR REPLACE TABLE {ODS}.pharmacy_pa
{TBL_PROPS}
AS
SELECT *,
       CAST(DATE_FORMAT(CAST(submitted_at AS DATE), 'yyyyMMdd') AS INT) AS submitted_date_key,
       CAST(DATE_FORMAT(CAST(decision_at  AS DATE), 'yyyyMMdd') AS INT) AS decision_date_key
FROM {BRONZE}.pharmacy_pa
""")

spark.sql(f"CREATE OR REPLACE TABLE {ODS}.provider_sanctions {TBL_PROPS} AS SELECT * FROM {BRONZE}.provider_sanctions")
spark.sql(f"CREATE OR REPLACE TABLE {ODS}.provider_directory_attestation {TBL_PROPS} AS SELECT * FROM {BRONZE}.provider_directory_attestation")

spark.sql(f"""
CREATE OR REPLACE TABLE {ODS}.readmission
{TBL_PROPS}
AS
SELECT *,
       CAST(DATE_FORMAT(index_dis_date, 'yyyyMMdd') AS INT) AS index_dis_date_key,
       CAST(DATE_FORMAT(readmit_date,   'yyyyMMdd') AS INT) AS readmit_date_key
FROM {BRONZE}.readmission
""")

spark.sql(f"""
CREATE OR REPLACE TABLE {ODS}.sdoh_assessment
{TBL_PROPS}
AS
SELECT *, CAST(DATE_FORMAT(assessment_date, 'yyyyMMdd') AS INT) AS assessment_date_key
FROM {BRONZE}.sdoh_assessment
""")

spark.sql(f"CREATE OR REPLACE TABLE {ODS}.cahps_response {TBL_PROPS} AS SELECT * FROM {BRONZE}.cahps_response")

spark.sql(f"""
CREATE OR REPLACE TABLE {ODS}.outreach
{TBL_PROPS}
AS
SELECT *, CAST(DATE_FORMAT(outreach_date, 'yyyyMMdd') AS INT) AS outreach_date_key
FROM {BRONZE}.outreach
""")

spark.sql(f"CREATE OR REPLACE TABLE {ODS}.vbc_attribution {TBL_PROPS} AS SELECT * FROM {BRONZE}.vbc_attribution")

print("[silver-ods] 8 A.0c passthroughs written")

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

# OPTIMIZE silver tables so gold reads from compact V-Order'd shards. Cheap at
# smoke scale; at full scale this is what keeps Direct Lake snappy.
_SILVER_STAGE_TBLS = [
    "dim_date", "members", "claims_header", "claims_line", "rx_claims",
    "auths", "appeals", "premiums", "providers", "payers", "conditions",
    "raf_scores", "quality_events", "member_month",
]
_SILVER_ODS_TBLS = [
    "pharmacy_pa", "provider_sanctions", "provider_directory_attestation",
    "readmission", "sdoh_assessment", "cahps_response", "outreach",
    "vbc_attribution",
]
for t in _SILVER_STAGE_TBLS:
    spark.sql(f"OPTIMIZE {STAGE}.{t}")
for t in _SILVER_ODS_TBLS:
    spark.sql(f"OPTIMIZE {ODS}.{t}")

print(f"[silver] OPTIMIZE complete ({len(_SILVER_STAGE_TBLS)} stage + {len(_SILVER_ODS_TBLS)} ods)")
print("[silver] PASS — 22 tables total (14 stage + 8 ods)")

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

# Audit-log emit — see NB_01 for full doc. Counts silver rows by re-querying
# each table from the metastore so we capture post-write counts inclusive of
# de-dup / explosion logic, not pre-write row estimates.
from pyspark.sql.types import (
    IntegerType, LongType, StringType, StructField, StructType, TimestampType,
)

_audit_completed_at = datetime.utcnow()
_audit_duration_ms = int((_time.perf_counter() - _audit_t0) * 1000)

_audit_rowcount_out = 0
for _t in _SILVER_STAGE_TBLS:
    _audit_rowcount_out += spark.sql(f"SELECT COUNT(*) AS n FROM {STAGE}.{_t}").collect()[0]["n"]
for _t in _SILVER_ODS_TBLS:
    _audit_rowcount_out += spark.sql(f"SELECT COUNT(*) AS n FROM {ODS}.{_t}").collect()[0]["n"]
_audit_table_count = len(_SILVER_STAGE_TBLS) + len(_SILVER_ODS_TBLS)

_AUDIT_SCHEMA = StructType([
    StructField("audit_id", StringType(), False),
    StructField("run_id", StringType(), False),
    StructField("pipeline", StringType(), False),
    StructField("layer", StringType(), False),
    StructField("stage_name", StringType(), False),
    StructField("rowcount_in", LongType(), True),
    StructField("rowcount_out", LongType(), True),
    StructField("table_count", IntegerType(), True),
    StructField("duration_ms", LongType(), True),
    StructField("status", StringType(), False),
    StructField("error_msg", StringType(), True),
    StructField("started_at", TimestampType(), False),
    StructField("completed_at", TimestampType(), False),
    StructField("user_principal", StringType(), True),
    StructField("git_sha", StringType(), True),
])

_audit_df = spark.createDataFrame([(
    _audit_run_uuid, _audit_run_id, _audit_pipeline, "silver", "NB_02_Silver_Transform",
    None, _audit_rowcount_out, _audit_table_count, _audit_duration_ms,
    "success", None, _audit_started_at, _audit_completed_at,
    _audit_user, _audit_git_sha,
)], _AUDIT_SCHEMA)
try:
    (_audit_df.write
        .mode("append")
        .format("delta")
        .option("mergeSchema", "true")
        .saveAsTable("lh_gold_curated.audit_log"))
    print(f"[silver] audit_log row appended (run={_audit_run_uuid[:8]} rows={_audit_rowcount_out} dur_ms={_audit_duration_ms})")
except Exception as e:
    print(f"[silver] WARN audit_log write failed: {type(e).__name__}: {e}")

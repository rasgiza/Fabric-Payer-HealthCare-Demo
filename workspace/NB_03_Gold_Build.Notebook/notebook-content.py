# Fabric notebook source

# METADATA **{"language":"markdown"}**

# MARKDOWN **{"language":"markdown"}**

# # NB_03 - Gold Build (Payer)
#
# Builds the gold star-schema in `lh_gold_curated` from silver-stage + silver-ods:
# 10 dimensions, 16 facts, 9 aggregates = 35 tables.
#
# This is the Direct Lake source for PayerAnalytics SemanticModel and the
# 7 Foundry data agents (CFO / Stars / RA / SIU / CareMgmt / Network / UM).
#
# **Default lakehouse must be `lh_gold_curated`** with `lh_silver_stage` +
# `lh_silver_ods` attached as secondary so the three-part names resolve.
#
# SQL is a direct port of `tools/run_local_etl.py::gold()`.
# DuckDB `quantile_cont` is translated to Spark `PERCENTILE_APPROX`.

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

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

# Fabric Spark + Delta tuning — mirrors NB_01/02. Gold tables back Direct Lake
# in PayerAnalytics.SemanticModel and ground the 9 Foundry data agents; V-Order
# is non-negotiable here or DL falls back to DirectQuery.
spark.conf.set("spark.sql.parquet.vorder.enabled", "true")
spark.conf.set("spark.microsoft.delta.optimizeWrite.enabled", "true")
spark.conf.set("spark.microsoft.delta.optimizeWrite.binSize", "1073741824")
spark.conf.set("spark.databricks.delta.autoCompact.enabled", "true")
spark.conf.set("spark.databricks.delta.properties.defaults.enableDeletionVectors", "true")
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
spark.conf.set("spark.sql.shuffle.partitions", "16")

print(f"[gold] start={datetime.now().isoformat(timespec='seconds')}")

STAGE = "lh_silver_stage"
ODS = "lh_silver_ods"

TBL_PROPS = """
USING DELTA
TBLPROPERTIES (
    'delta.enableChangeDataFeed'       = 'true',
    'delta.enableDeletionVectors'      = 'true',
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
)
"""

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ----- Dimensions (10) -----

spark.sql(f"CREATE OR REPLACE TABLE dim_date     {TBL_PROPS} AS SELECT * FROM {STAGE}.dim_date")
spark.sql(f"CREATE OR REPLACE TABLE dim_member   {TBL_PROPS} AS SELECT * FROM {STAGE}.members")
spark.sql(f"CREATE OR REPLACE TABLE dim_provider {TBL_PROPS} AS SELECT * FROM {STAGE}.providers")
spark.sql(f"CREATE OR REPLACE TABLE dim_payer    {TBL_PROPS} AS SELECT * FROM {STAGE}.payers")
spark.sql(f"CREATE OR REPLACE TABLE dim_lob      {TBL_PROPS} AS SELECT DISTINCT lob AS lob_id, lob AS lob_name FROM {STAGE}.members")
spark.sql(f"CREATE OR REPLACE TABLE dim_product  {TBL_PROPS} AS SELECT DISTINCT product AS product_id, product AS product_name, lob FROM {STAGE}.members")
spark.sql(f"CREATE OR REPLACE TABLE dim_diagnosis {TBL_PROPS} AS SELECT DISTINCT primary_dx_code AS dx_code FROM {STAGE}.claims_header WHERE primary_dx_code IS NOT NULL")
spark.sql(f"CREATE OR REPLACE TABLE dim_procedure {TBL_PROPS} AS SELECT DISTINCT cpt_hcpcs FROM {STAGE}.claims_line WHERE cpt_hcpcs IS NOT NULL")
spark.sql(f"CREATE OR REPLACE TABLE dim_drug      {TBL_PROPS} AS SELECT DISTINCT ndc_code, drug_name, drug_class FROM {STAGE}.rx_claims")
spark.sql(f"CREATE OR REPLACE TABLE dim_hcc       {TBL_PROPS} AS SELECT DISTINCT hcc_v28 AS hcc_id FROM {STAGE}.conditions WHERE hcc_v28 IS NOT NULL")

print("[gold] 10 dims written")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ----- Facts (16) -----

spark.sql(f"""
CREATE OR REPLACE TABLE fact_claim
{TBL_PROPS}
AS
SELECT
    h.claim_id, l.line_no,
    h.member_id, h.provider_npi, h.payer_id,
    h.service_date, h.service_date_key, h.plan_year,
    h.claim_type, h.place_of_service, h.lob,
    h.primary_dx_code, l.cpt_hcpcs, l.modifier, l.units,
    l.billed_amount, l.allowed_amount, l.paid_amount,
    h.member_liability,
    h.denied_int, h.paid_int, h.carc_code, h.pa_required_flag
FROM {STAGE}.claims_header h
LEFT JOIN {STAGE}.claims_line l USING (claim_id)
""")

spark.sql(f"CREATE OR REPLACE TABLE fact_rx_claim       {TBL_PROPS} AS SELECT * FROM {STAGE}.rx_claims")
spark.sql(f"CREATE OR REPLACE TABLE fact_auth           {TBL_PROPS} AS SELECT * FROM {STAGE}.auths")
spark.sql(f"CREATE OR REPLACE TABLE fact_appeal         {TBL_PROPS} AS SELECT * FROM {STAGE}.appeals")
spark.sql(f"CREATE OR REPLACE TABLE fact_premium        {TBL_PROPS} AS SELECT * FROM {STAGE}.premiums")
spark.sql(f"CREATE OR REPLACE TABLE fact_member_month   {TBL_PROPS} AS SELECT * FROM {STAGE}.member_month")
spark.sql(f"CREATE OR REPLACE TABLE fact_quality_event  {TBL_PROPS} AS SELECT * FROM {STAGE}.quality_events")
spark.sql(f"CREATE OR REPLACE TABLE fact_raf_score      {TBL_PROPS} AS SELECT * FROM {STAGE}.raf_scores")

# A.0c facts (silver-ods sourced)
spark.sql(f"CREATE OR REPLACE TABLE fact_pharmacy_pa                    {TBL_PROPS} AS SELECT * FROM {ODS}.pharmacy_pa")
spark.sql(f"CREATE OR REPLACE TABLE fact_provider_sanction              {TBL_PROPS} AS SELECT * FROM {ODS}.provider_sanctions")
spark.sql(f"CREATE OR REPLACE TABLE fact_provider_directory_attestation {TBL_PROPS} AS SELECT * FROM {ODS}.provider_directory_attestation")
spark.sql(f"CREATE OR REPLACE TABLE fact_readmission                    {TBL_PROPS} AS SELECT * FROM {ODS}.readmission")
spark.sql(f"CREATE OR REPLACE TABLE fact_sdoh_assessment                {TBL_PROPS} AS SELECT * FROM {ODS}.sdoh_assessment")
spark.sql(f"CREATE OR REPLACE TABLE fact_cahps_response                 {TBL_PROPS} AS SELECT * FROM {ODS}.cahps_response")
spark.sql(f"CREATE OR REPLACE TABLE fact_outreach                       {TBL_PROPS} AS SELECT * FROM {ODS}.outreach")
spark.sql(f"CREATE OR REPLACE TABLE fact_vbc_attribution                {TBL_PROPS} AS SELECT * FROM {ODS}.vbc_attribution")

print("[gold] 16 facts written")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ----- Aggregates (9) -----

spark.sql(f"""
CREATE OR REPLACE TABLE agg_denial_by_payer
{TBL_PROPS}
AS
SELECT payer_id, plan_year,
       COUNT(*) AS claims,
       SUM(denied_int) AS denied_claims,
       1.0 * SUM(denied_int) / NULLIF(COUNT(*), 0) AS denial_rate,
       SUM(billed_amount)  AS billed_total,
       SUM(allowed_amount) AS allowed_total,
       SUM(paid_amount)    AS paid_total
FROM {STAGE}.claims_header
GROUP BY 1, 2
""")

spark.sql(f"""
CREATE OR REPLACE TABLE agg_mlr_monthly
{TBL_PROPS}
AS
WITH paid AS (
    SELECT payer_id, plan_year, MONTH(service_date) AS month,
           SUM(paid_amount) AS medical_paid
    FROM {STAGE}.claims_header
    GROUP BY 1, 2, 3
),
prem AS (
    SELECT payer_id, plan_year,
           SUM(premium_total) AS premium_total,
           SUM(member_months) AS mm
    FROM {STAGE}.premiums GROUP BY 1, 2
)
SELECT p.payer_id, p.plan_year, p.month,
       p.medical_paid, pr.premium_total, pr.mm,
       1.0 * p.medical_paid / NULLIF(pr.premium_total / 12.0, 0) AS mlr_monthly_est
FROM paid p
LEFT JOIN prem pr USING (payer_id, plan_year)
""")

spark.sql(f"""
CREATE OR REPLACE TABLE agg_pa_tat
{TBL_PROPS}
AS
SELECT payer_id, plan_year, request_type,
       COUNT(*) AS pa_count,
       PERCENTILE_APPROX(tat_hours, 0.50) AS tat_median_hrs,
       PERCENTILE_APPROX(tat_hours, 0.95) AS tat_p95_hrs,
       1.0 * SUM(CASE WHEN sla_met THEN 1 ELSE 0 END) / COUNT(*) AS sla_compliance_pct
FROM {STAGE}.auths
GROUP BY 1, 2, 3
""")

spark.sql(f"""
CREATE OR REPLACE TABLE agg_stars_compliance
{TBL_PROPS}
AS
SELECT measure_id, plan_year, lob,
       SUM(CASE WHEN eligible  THEN 1 ELSE 0 END) AS denominator,
       SUM(CASE WHEN compliant THEN 1 ELSE 0 END) AS numerator,
       1.0 * SUM(CASE WHEN compliant THEN 1 ELSE 0 END)
           / NULLIF(SUM(CASE WHEN eligible THEN 1 ELSE 0 END), 0) AS compliance_pct
FROM {STAGE}.quality_events
GROUP BY 1, 2, 3
""")

# A.0c aggregates
spark.sql(f"""
CREATE OR REPLACE TABLE agg_readmissions
{TBL_PROPS}
AS
SELECT plan_year, hrrp_cohort,
       COUNT(*) AS index_admits,
       SUM(CASE WHEN readmit_within_30d THEN 1 ELSE 0 END) AS readmits_30d,
       1.0 * SUM(CASE WHEN readmit_within_30d THEN 1 ELSE 0 END)
           / NULLIF(COUNT(*), 0) AS readmit_rate_30d
FROM {ODS}.readmission
GROUP BY 1, 2
""")

spark.sql(f"""
CREATE OR REPLACE TABLE agg_glp1_pa_yield
{TBL_PROPS}
AS
SELECT plan_year,
       COUNT(*) AS pa_count,
       SUM(CASE WHEN decision = 'approve' THEN 1 ELSE 0 END) AS approvals,
       SUM(CASE WHEN decision = 'deny'    THEN 1 ELSE 0 END) AS denials,
       1.0 * SUM(CASE WHEN decision = 'approve' THEN 1 ELSE 0 END)
           / NULLIF(COUNT(*), 0) AS approval_rate
FROM {ODS}.pharmacy_pa
WHERE drug_class = 'GLP1'
GROUP BY 1
""")

spark.sql(f"""
CREATE OR REPLACE TABLE agg_sdoh_burden
{TBL_PROPS}
AS
SELECT plan_year, domain,
       COUNT(*) AS assessed_count,
       SUM(CASE WHEN positive_screen THEN 1 ELSE 0 END) AS positive_count,
       1.0 * SUM(CASE WHEN positive_screen THEN 1 ELSE 0 END)
           / NULLIF(COUNT(*), 0) AS positive_rate,
       SUM(CASE WHEN intervention_referred THEN 1 ELSE 0 END) AS referred_count
FROM {ODS}.sdoh_assessment
GROUP BY 1, 2
""")

spark.sql(f"""
CREATE OR REPLACE TABLE agg_health_equity_index_proxy
{TBL_PROPS}
AS
SELECT
    m.payer_id, q.plan_year,
    CASE WHEN m.hei_eligible_flag THEN 'hei_eligible' ELSE 'non_hei' END AS hei_segment,
    SUM(CASE WHEN q.eligible  THEN 1 ELSE 0 END) AS denominator,
    SUM(CASE WHEN q.compliant THEN 1 ELSE 0 END) AS numerator,
    1.0 * SUM(CASE WHEN q.compliant THEN 1 ELSE 0 END)
        / NULLIF(SUM(CASE WHEN q.eligible THEN 1 ELSE 0 END), 0) AS compliance_pct
FROM {STAGE}.quality_events q
JOIN {STAGE}.members        m USING (member_id)
GROUP BY 1, 2, 3
""")

spark.sql(f"""
CREATE OR REPLACE TABLE agg_oon_directory_inaccuracy
{TBL_PROPS}
AS
WITH oon AS (
    SELECT payer_id, plan_year,
           COUNT(*) AS claims_total,
           SUM(CASE WHEN oon_flag           THEN 1 ELSE 0 END) AS oon_claims,
           SUM(CASE WHEN nsa_eligible_flag  THEN 1 ELSE 0 END) AS nsa_eligible_claims,
           1.0 * SUM(CASE WHEN oon_flag           THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS oon_pct,
           1.0 * SUM(CASE WHEN nsa_eligible_flag  THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS nsa_eligible_share
    FROM {STAGE}.claims_header
    GROUP BY 1, 2
),
dir AS (
    SELECT 1.0 * SUM(CASE WHEN stale_flag THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS directory_stale_pct
    FROM {ODS}.provider_directory_attestation
)
SELECT oon.*, dir.directory_stale_pct
FROM oon CROSS JOIN dir
""")

print("[gold] 9 aggregates written")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# Final compaction + cleanup. OPTIMIZE rewrites small files to V-Order'd shards
# so Direct Lake reads at line-rate. VACUUM with retentionDuration=168 hours
# (Delta default minimum) reclaims storage from prior CREATE OR REPLACE rounds.
# Drop the retention check to use shorter windows during dev; never in prod.

_GOLD_DIMS = [
    "dim_date", "dim_member", "dim_provider", "dim_payer", "dim_lob",
    "dim_product", "dim_diagnosis", "dim_procedure", "dim_drug", "dim_hcc",
]
_GOLD_FACTS = [
    "fact_claim", "fact_rx_claim", "fact_auth", "fact_appeal", "fact_premium",
    "fact_member_month", "fact_quality_event", "fact_raf_score",
    "fact_pharmacy_pa", "fact_provider_sanction",
    "fact_provider_directory_attestation", "fact_readmission",
    "fact_sdoh_assessment", "fact_cahps_response", "fact_outreach",
    "fact_vbc_attribution",
]
_GOLD_AGGS = [
    "agg_denial_by_payer", "agg_mlr_monthly", "agg_pa_tat",
    "agg_stars_compliance", "agg_readmissions", "agg_glp1_pa_yield",
    "agg_sdoh_burden", "agg_health_equity_index_proxy",
    "agg_oon_directory_inaccuracy",
]
_ALL_GOLD = _GOLD_DIMS + _GOLD_FACTS + _GOLD_AGGS

for t in _ALL_GOLD:
    spark.sql(f"OPTIMIZE {t}")
print(f"[gold] OPTIMIZE complete for {len(_ALL_GOLD)} tables")

# VACUUM with 168h retention (Delta default minimum without an unsafe override).
for t in _ALL_GOLD:
    spark.sql(f"VACUUM {t} RETAIN 168 HOURS")
print(f"[gold] VACUUM complete for {len(_ALL_GOLD)} tables")

print("[gold] PASS — 35 tables in lh_gold_curated (10 dims + 16 facts + 9 aggs)")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# Audit-log emit — see NB_01 for full doc. The default lakehouse here IS
# lh_gold_curated so the table name is unqualified.
from pyspark.sql.types import (
    IntegerType, LongType, StringType, StructField, StructType, TimestampType,
)

_audit_completed_at = datetime.utcnow()
_audit_duration_ms = int((_time.perf_counter() - _audit_t0) * 1000)

_audit_rowcount_out = 0
for _t in _ALL_GOLD:
    _audit_rowcount_out += spark.sql(f"SELECT COUNT(*) AS n FROM {_t}").collect()[0]["n"]
_audit_table_count = len(_ALL_GOLD)

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
    _audit_run_uuid, _audit_run_id, _audit_pipeline, "gold", "NB_03_Gold_Build",
    None, _audit_rowcount_out, _audit_table_count, _audit_duration_ms,
    "success", None, _audit_started_at, _audit_completed_at,
    _audit_user, _audit_git_sha,
)], _AUDIT_SCHEMA)

try:
    (_audit_df.write
        .mode("append")
        .format("delta")
        .option("mergeSchema", "true")
        .saveAsTable("audit_log"))
    print(f"[gold] audit_log row appended (run={_audit_run_uuid[:8]} rows={_audit_rowcount_out} dur_ms={_audit_duration_ms})")
except Exception as e:
    print(f"[gold] WARN audit_log write failed: {type(e).__name__}: {e}")

# Fabric notebook source

# METADATA **{"language":"markdown"}**

# MARKDOWN **{"language":"markdown"}**

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

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

from datetime import datetime
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
print(f"[silver] start={datetime.now().isoformat(timespec='seconds')}")

BRONZE = "lh_bronze_raw"
STAGE = "lh_silver_stage"
ODS = "lh_silver_ods"

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ----- dim_date -----
spark.sql(f"""
CREATE OR REPLACE TABLE {STAGE}.dim_date AS
WITH d AS (
    SELECT DISTINCT service_date AS d FROM {BRONZE}.claims_header
    UNION SELECT DISTINCT fill_date FROM {BRONZE}.rx_claims
)
SELECT
    CAST(DATE_FORMAT(d, 'yyyyMMdd') AS INT) AS date_key,
    d AS full_date,
    YEAR(d)    AS year,
    MONTH(d)   AS month,
    QUARTER(d) AS quarter,
    DATE_FORMAT(d, 'yyyy-MM') AS year_month
FROM d WHERE d IS NOT NULL
""")

# ----- members (light de-id + age band + HEI/SDOH passthrough) -----
spark.sql(f"""
CREATE OR REPLACE TABLE {STAGE}.members AS
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
CREATE OR REPLACE TABLE {STAGE}.claims_header AS
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
    spark.sql(f"CREATE OR REPLACE TABLE {STAGE}.{tbl} AS SELECT *{derived} FROM {BRONZE}.{tbl}")

# ----- member_month explosion -----
spark.sql(f"""
CREATE OR REPLACE TABLE {STAGE}.member_month AS
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

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ----- A.0c passthroughs into silver_ods (with derived date keys) -----

spark.sql(f"""
CREATE OR REPLACE TABLE {ODS}.pharmacy_pa AS
SELECT *,
       CAST(DATE_FORMAT(CAST(submitted_at AS DATE), 'yyyyMMdd') AS INT) AS submitted_date_key,
       CAST(DATE_FORMAT(CAST(decision_at  AS DATE), 'yyyyMMdd') AS INT) AS decision_date_key
FROM {BRONZE}.pharmacy_pa
""")

spark.sql(f"CREATE OR REPLACE TABLE {ODS}.provider_sanctions AS SELECT * FROM {BRONZE}.provider_sanctions")
spark.sql(f"CREATE OR REPLACE TABLE {ODS}.provider_directory_attestation AS SELECT * FROM {BRONZE}.provider_directory_attestation")

spark.sql(f"""
CREATE OR REPLACE TABLE {ODS}.readmission AS
SELECT *,
       CAST(DATE_FORMAT(index_dis_date, 'yyyyMMdd') AS INT) AS index_dis_date_key,
       CAST(DATE_FORMAT(readmit_date,   'yyyyMMdd') AS INT) AS readmit_date_key
FROM {BRONZE}.readmission
""")

spark.sql(f"""
CREATE OR REPLACE TABLE {ODS}.sdoh_assessment AS
SELECT *, CAST(DATE_FORMAT(assessment_date, 'yyyyMMdd') AS INT) AS assessment_date_key
FROM {BRONZE}.sdoh_assessment
""")

spark.sql(f"CREATE OR REPLACE TABLE {ODS}.cahps_response AS SELECT * FROM {BRONZE}.cahps_response")

spark.sql(f"""
CREATE OR REPLACE TABLE {ODS}.outreach AS
SELECT *, CAST(DATE_FORMAT(outreach_date, 'yyyyMMdd') AS INT) AS outreach_date_key
FROM {BRONZE}.outreach
""")

spark.sql(f"CREATE OR REPLACE TABLE {ODS}.vbc_attribution AS SELECT * FROM {BRONZE}.vbc_attribution")

print("[silver-ods] 8 A.0c passthroughs written")
print("[silver] PASS — 22 tables total (14 stage + 8 ods)")

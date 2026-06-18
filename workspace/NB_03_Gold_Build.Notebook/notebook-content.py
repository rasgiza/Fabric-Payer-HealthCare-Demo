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
print(f"[gold] start={datetime.now().isoformat(timespec='seconds')}")

STAGE = "lh_silver_stage"
ODS = "lh_silver_ods"

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ----- Dimensions (10) -----

spark.sql(f"CREATE OR REPLACE TABLE dim_date     AS SELECT * FROM {STAGE}.dim_date")
spark.sql(f"CREATE OR REPLACE TABLE dim_member   AS SELECT * FROM {STAGE}.members")
spark.sql(f"CREATE OR REPLACE TABLE dim_provider AS SELECT * FROM {STAGE}.providers")
spark.sql(f"CREATE OR REPLACE TABLE dim_payer    AS SELECT * FROM {STAGE}.payers")
spark.sql(f"CREATE OR REPLACE TABLE dim_lob      AS SELECT DISTINCT lob AS lob_id, lob AS lob_name FROM {STAGE}.members")
spark.sql(f"CREATE OR REPLACE TABLE dim_product  AS SELECT DISTINCT product AS product_id, product AS product_name, lob FROM {STAGE}.members")
spark.sql(f"CREATE OR REPLACE TABLE dim_diagnosis AS SELECT DISTINCT primary_dx_code AS dx_code FROM {STAGE}.claims_header WHERE primary_dx_code IS NOT NULL")
spark.sql(f"CREATE OR REPLACE TABLE dim_procedure AS SELECT DISTINCT cpt_hcpcs FROM {STAGE}.claims_line WHERE cpt_hcpcs IS NOT NULL")
spark.sql(f"CREATE OR REPLACE TABLE dim_drug      AS SELECT DISTINCT ndc_code, drug_name, drug_class FROM {STAGE}.rx_claims")
spark.sql(f"CREATE OR REPLACE TABLE dim_hcc       AS SELECT DISTINCT hcc_v28 AS hcc_id FROM {STAGE}.conditions WHERE hcc_v28 IS NOT NULL")

print("[gold] 10 dims written")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ----- Facts (16) -----

spark.sql(f"""
CREATE OR REPLACE TABLE fact_claim AS
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

spark.sql(f"CREATE OR REPLACE TABLE fact_rx_claim       AS SELECT * FROM {STAGE}.rx_claims")
spark.sql(f"CREATE OR REPLACE TABLE fact_auth           AS SELECT * FROM {STAGE}.auths")
spark.sql(f"CREATE OR REPLACE TABLE fact_appeal         AS SELECT * FROM {STAGE}.appeals")
spark.sql(f"CREATE OR REPLACE TABLE fact_premium        AS SELECT * FROM {STAGE}.premiums")
spark.sql(f"CREATE OR REPLACE TABLE fact_member_month   AS SELECT * FROM {STAGE}.member_month")
spark.sql(f"CREATE OR REPLACE TABLE fact_quality_event  AS SELECT * FROM {STAGE}.quality_events")
spark.sql(f"CREATE OR REPLACE TABLE fact_raf_score      AS SELECT * FROM {STAGE}.raf_scores")

# A.0c facts (silver-ods sourced)
spark.sql(f"CREATE OR REPLACE TABLE fact_pharmacy_pa                    AS SELECT * FROM {ODS}.pharmacy_pa")
spark.sql(f"CREATE OR REPLACE TABLE fact_provider_sanction              AS SELECT * FROM {ODS}.provider_sanctions")
spark.sql(f"CREATE OR REPLACE TABLE fact_provider_directory_attestation AS SELECT * FROM {ODS}.provider_directory_attestation")
spark.sql(f"CREATE OR REPLACE TABLE fact_readmission                    AS SELECT * FROM {ODS}.readmission")
spark.sql(f"CREATE OR REPLACE TABLE fact_sdoh_assessment                AS SELECT * FROM {ODS}.sdoh_assessment")
spark.sql(f"CREATE OR REPLACE TABLE fact_cahps_response                 AS SELECT * FROM {ODS}.cahps_response")
spark.sql(f"CREATE OR REPLACE TABLE fact_outreach                       AS SELECT * FROM {ODS}.outreach")
spark.sql(f"CREATE OR REPLACE TABLE fact_vbc_attribution                AS SELECT * FROM {ODS}.vbc_attribution")

print("[gold] 16 facts written")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ----- Aggregates (9) -----

spark.sql(f"""
CREATE OR REPLACE TABLE agg_denial_by_payer AS
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
CREATE OR REPLACE TABLE agg_mlr_monthly AS
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
CREATE OR REPLACE TABLE agg_pa_tat AS
SELECT payer_id, plan_year, request_type,
       COUNT(*) AS pa_count,
       PERCENTILE_APPROX(tat_hours, 0.50) AS tat_median_hrs,
       PERCENTILE_APPROX(tat_hours, 0.95) AS tat_p95_hrs,
       1.0 * SUM(CASE WHEN sla_met THEN 1 ELSE 0 END) / COUNT(*) AS sla_compliance_pct
FROM {STAGE}.auths
GROUP BY 1, 2, 3
""")

spark.sql(f"""
CREATE OR REPLACE TABLE agg_stars_compliance AS
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
CREATE OR REPLACE TABLE agg_readmissions AS
SELECT plan_year, hrrp_cohort,
       COUNT(*) AS index_admits,
       SUM(CASE WHEN readmit_within_30d THEN 1 ELSE 0 END) AS readmits_30d,
       1.0 * SUM(CASE WHEN readmit_within_30d THEN 1 ELSE 0 END)
           / NULLIF(COUNT(*), 0) AS readmit_rate_30d
FROM {ODS}.readmission
GROUP BY 1, 2
""")

spark.sql(f"""
CREATE OR REPLACE TABLE agg_glp1_pa_yield AS
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
CREATE OR REPLACE TABLE agg_sdoh_burden AS
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
CREATE OR REPLACE TABLE agg_health_equity_index_proxy AS
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
CREATE OR REPLACE TABLE agg_oon_directory_inaccuracy AS
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
print("[gold] PASS — 35 tables in lh_gold_curated (10 dims + 16 facts + 9 aggs)")

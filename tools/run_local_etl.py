"""
run_local_etl.py - Local DuckDB executor for the Phase 2 medallion ETL.

Reads synthetic CSVs from data/synth/<run_id>/, runs Bronze -> Silver -> Gold
SQL transforms, and writes Parquet outputs under data/lakehouse/<run_id>/
mirroring the Fabric lakehouse layout:

    data/lakehouse/<run>/bronze/<table>.parquet
    data/lakehouse/<run>/silver/<table>.parquet
    data/lakehouse/<run>/gold/<table>.parquet

This is a faithful local stand-in for the Fabric PySpark notebooks; the same
SQL ports cleanly to spark.sql() in Phase 7.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SYNTH = ROOT / "data" / "synth"
LAKE = ROOT / "data" / "lakehouse"

BRONZE_TABLES = [
    "members", "enrollment_spans", "providers", "payers", "conditions",
    "claims_header", "claims_line", "rx_claims", "auths", "appeals",
    "premiums", "raf_scores", "quality_events",
    "pharmacy_pa", "provider_sanctions", "provider_directory_attestation",
    "readmission", "sdoh_assessment", "cahps_response", "outreach",
    "vbc_attribution",
]


def bronze(con: duckdb.DuckDBPyConnection, src: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for t in BRONZE_TABLES:
        f = src / f"{t}.csv"
        con.execute(f"CREATE OR REPLACE TABLE bronze_{t} AS SELECT * FROM read_csv_auto('{f.as_posix()}')")
        con.execute(f"COPY bronze_{t} TO '{(out / f'{t}.parquet').as_posix()}' (FORMAT PARQUET)")
    print(f"  bronze: {len(BRONZE_TABLES)} tables")


def silver(con: duckdb.DuckDBPyConnection, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)

    # Dim date (silver-stage scaffold): one row per service date observed
    con.execute("""
        CREATE OR REPLACE TABLE silver_dim_date AS
        WITH d AS (
            SELECT DISTINCT service_date AS d FROM bronze_claims_header
            UNION SELECT DISTINCT fill_date FROM bronze_rx_claims
        )
        SELECT
            CAST(strftime(d, '%Y%m%d') AS INT) AS date_key,
            d AS full_date,
            EXTRACT(year FROM d) AS year,
            EXTRACT(month FROM d) AS month,
            EXTRACT(quarter FROM d) AS quarter,
            strftime(d, '%Y-%m') AS year_month
        FROM d WHERE d IS NOT NULL
    """)

    # Members - light de-id (zip3 already 3-digit; mbi already hashed; drop dob_year keep age band)
    con.execute("""
        CREATE OR REPLACE TABLE silver_members AS
        SELECT
            member_id,
            mbi_hash,
            subscriber_id,
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
        FROM bronze_members
    """)

    # Claims header with denial-rate-ready flags
    con.execute("""
        CREATE OR REPLACE TABLE silver_claims_header AS
        SELECT
            *,
            CAST(strftime(service_date, '%Y%m%d') AS INT) AS service_date_key,
            CASE WHEN denied_flag THEN 1 ELSE 0 END AS denied_int,
            CASE WHEN paid_amount > 0 AND NOT denied_flag THEN 1 ELSE 0 END AS paid_int
        FROM bronze_claims_header
    """)

    con.execute("CREATE OR REPLACE TABLE silver_claims_line AS SELECT * FROM bronze_claims_line")
    con.execute("CREATE OR REPLACE TABLE silver_rx_claims AS SELECT *, CAST(strftime(fill_date, '%Y%m%d') AS INT) AS fill_date_key FROM bronze_rx_claims")
    con.execute("CREATE OR REPLACE TABLE silver_auths AS SELECT * FROM bronze_auths")
    con.execute("CREATE OR REPLACE TABLE silver_appeals AS SELECT * FROM bronze_appeals")
    con.execute("CREATE OR REPLACE TABLE silver_premiums AS SELECT * FROM bronze_premiums")
    con.execute("CREATE OR REPLACE TABLE silver_providers AS SELECT * FROM bronze_providers")
    con.execute("CREATE OR REPLACE TABLE silver_payers AS SELECT * FROM bronze_payers")
    con.execute("CREATE OR REPLACE TABLE silver_conditions AS SELECT * FROM bronze_conditions")
    con.execute("CREATE OR REPLACE TABLE silver_raf_scores AS SELECT * FROM bronze_raf_scores")
    con.execute("CREATE OR REPLACE TABLE silver_quality_events AS SELECT * FROM bronze_quality_events")

    # New silver passthroughs (A.0c). Carry through any inline date keys where useful.
    con.execute("""
        CREATE OR REPLACE TABLE silver_pharmacy_pa AS
        SELECT *,
               CAST(strftime(CAST(submitted_at AS DATE), '%Y%m%d') AS INT) AS submitted_date_key,
               CAST(strftime(CAST(decision_at AS DATE), '%Y%m%d') AS INT) AS decision_date_key
        FROM bronze_pharmacy_pa
    """)
    con.execute("CREATE OR REPLACE TABLE silver_provider_sanctions AS SELECT * FROM bronze_provider_sanctions")
    con.execute("CREATE OR REPLACE TABLE silver_provider_directory_attestation AS SELECT * FROM bronze_provider_directory_attestation")
    con.execute("""
        CREATE OR REPLACE TABLE silver_readmission AS
        SELECT *,
               CAST(strftime(index_dis_date, '%Y%m%d') AS INT) AS index_dis_date_key,
               CAST(strftime(readmit_date, '%Y%m%d') AS INT) AS readmit_date_key
        FROM bronze_readmission
    """)
    con.execute("""
        CREATE OR REPLACE TABLE silver_sdoh_assessment AS
        SELECT *, CAST(strftime(assessment_date, '%Y%m%d') AS INT) AS assessment_date_key
        FROM bronze_sdoh_assessment
    """)
    con.execute("CREATE OR REPLACE TABLE silver_cahps_response AS SELECT * FROM bronze_cahps_response")
    con.execute("""
        CREATE OR REPLACE TABLE silver_outreach AS
        SELECT *, CAST(strftime(outreach_date, '%Y%m%d') AS INT) AS outreach_date_key
        FROM bronze_outreach
    """)
    con.execute("CREATE OR REPLACE TABLE silver_vbc_attribution AS SELECT * FROM bronze_vbc_attribution")

    # ODS-style member-month explosion from enrollment_spans
    con.execute("""
        CREATE OR REPLACE TABLE silver_member_month AS
        WITH spans AS (
            SELECT member_id, plan_year, start_month, end_month, lob, product, payer_id
            FROM bronze_enrollment_spans
        ),
        months AS (
            SELECT s.member_id, s.plan_year, m AS month, s.lob, s.product, s.payer_id
            FROM spans s, generate_series(1, 12) AS g(m)
            WHERE m BETWEEN s.start_month AND s.end_month
        )
        SELECT
            member_id, plan_year, month, lob, product, payer_id,
            CAST(plan_year * 100 + month AS INT) AS year_month_key
        FROM months
    """)

    silver_tables = [
        "dim_date", "members", "claims_header", "claims_line", "rx_claims",
        "auths", "appeals", "premiums", "providers", "payers", "conditions",
        "raf_scores", "quality_events", "member_month",
        "pharmacy_pa", "provider_sanctions", "provider_directory_attestation",
        "readmission", "sdoh_assessment", "cahps_response", "outreach",
        "vbc_attribution",
    ]
    for t in silver_tables:
        con.execute(f"COPY silver_{t} TO '{(out / f'{t}.parquet').as_posix()}' (FORMAT PARQUET)")
    print(f"  silver: {len(silver_tables)} tables (incl. member_month, dim_date, +8 new A.0c)")


def gold(con: duckdb.DuckDBPyConnection, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)

    # ----- Dimensions -----
    con.execute("CREATE OR REPLACE TABLE gold_dim_date AS SELECT * FROM silver_dim_date")
    con.execute("CREATE OR REPLACE TABLE gold_dim_member AS SELECT * FROM silver_members")
    con.execute("CREATE OR REPLACE TABLE gold_dim_provider AS SELECT * FROM silver_providers")
    con.execute("CREATE OR REPLACE TABLE gold_dim_payer AS SELECT * FROM silver_payers")
    con.execute("""
        CREATE OR REPLACE TABLE gold_dim_lob AS
        SELECT DISTINCT lob AS lob_id, lob AS lob_name FROM silver_members
    """)
    con.execute("""
        CREATE OR REPLACE TABLE gold_dim_product AS
        SELECT DISTINCT product AS product_id, product AS product_name, lob FROM silver_members
    """)
    con.execute("""
        CREATE OR REPLACE TABLE gold_dim_diagnosis AS
        SELECT DISTINCT primary_dx_code AS dx_code FROM silver_claims_header WHERE primary_dx_code IS NOT NULL
    """)
    con.execute("""
        CREATE OR REPLACE TABLE gold_dim_procedure AS
        SELECT DISTINCT cpt_hcpcs AS cpt_hcpcs FROM silver_claims_line WHERE cpt_hcpcs IS NOT NULL
    """)
    con.execute("""
        CREATE OR REPLACE TABLE gold_dim_drug AS
        SELECT DISTINCT ndc_code, drug_name, drug_class FROM silver_rx_claims
    """)
    con.execute("""
        CREATE OR REPLACE TABLE gold_dim_hcc AS
        SELECT DISTINCT hcc_v28 AS hcc_id FROM silver_conditions WHERE hcc_v28 IS NOT NULL
    """)

    # ----- Facts -----
    con.execute("""
        CREATE OR REPLACE TABLE gold_fact_claim AS
        SELECT
            h.claim_id, l.line_no,
            h.member_id, h.provider_npi, h.payer_id,
            h.service_date, h.service_date_key, h.plan_year,
            h.claim_type, h.place_of_service, h.lob,
            h.primary_dx_code, l.cpt_hcpcs, l.modifier, l.units,
            l.billed_amount, l.allowed_amount, l.paid_amount,
            h.member_liability,
            h.denied_int, h.paid_int, h.carc_code, h.pa_required_flag
        FROM silver_claims_header h
        LEFT JOIN silver_claims_line l USING (claim_id)
    """)
    con.execute("CREATE OR REPLACE TABLE gold_fact_rx_claim AS SELECT * FROM silver_rx_claims")
    con.execute("CREATE OR REPLACE TABLE gold_fact_auth AS SELECT * FROM silver_auths")
    con.execute("CREATE OR REPLACE TABLE gold_fact_appeal AS SELECT * FROM silver_appeals")
    con.execute("CREATE OR REPLACE TABLE gold_fact_premium AS SELECT * FROM silver_premiums")
    con.execute("CREATE OR REPLACE TABLE gold_fact_member_month AS SELECT * FROM silver_member_month")
    con.execute("CREATE OR REPLACE TABLE gold_fact_quality_event AS SELECT * FROM silver_quality_events")
    con.execute("CREATE OR REPLACE TABLE gold_fact_raf_score AS SELECT * FROM silver_raf_scores")
    # New facts (A.0c)
    con.execute("CREATE OR REPLACE TABLE gold_fact_pharmacy_pa AS SELECT * FROM silver_pharmacy_pa")
    con.execute("CREATE OR REPLACE TABLE gold_fact_provider_sanction AS SELECT * FROM silver_provider_sanctions")
    con.execute("CREATE OR REPLACE TABLE gold_fact_provider_directory_attestation AS SELECT * FROM silver_provider_directory_attestation")
    con.execute("CREATE OR REPLACE TABLE gold_fact_readmission AS SELECT * FROM silver_readmission")
    con.execute("CREATE OR REPLACE TABLE gold_fact_sdoh_assessment AS SELECT * FROM silver_sdoh_assessment")
    con.execute("CREATE OR REPLACE TABLE gold_fact_cahps_response AS SELECT * FROM silver_cahps_response")
    con.execute("CREATE OR REPLACE TABLE gold_fact_outreach AS SELECT * FROM silver_outreach")
    con.execute("CREATE OR REPLACE TABLE gold_fact_vbc_attribution AS SELECT * FROM silver_vbc_attribution")

    # ----- Aggregates -----
    con.execute("""
        CREATE OR REPLACE TABLE gold_agg_denial_by_payer AS
        SELECT payer_id, plan_year,
               COUNT(*) AS claims,
               SUM(denied_int) AS denied_claims,
               1.0 * SUM(denied_int) / NULLIF(COUNT(*), 0) AS denial_rate,
               SUM(billed_amount) AS billed_total,
               SUM(allowed_amount) AS allowed_total,
               SUM(paid_amount) AS paid_total
        FROM silver_claims_header
        GROUP BY 1, 2
    """)

    con.execute("""
        CREATE OR REPLACE TABLE gold_agg_mlr_monthly AS
        WITH paid AS (
            SELECT payer_id, plan_year,
                   EXTRACT(month FROM service_date) AS month,
                   SUM(paid_amount) AS medical_paid
            FROM silver_claims_header
            GROUP BY 1, 2, 3
        ),
        prem AS (
            SELECT payer_id, plan_year, SUM(premium_total) AS premium_total,
                   SUM(member_months) AS mm
            FROM silver_premiums GROUP BY 1, 2
        )
        SELECT p.payer_id, p.plan_year, p.month,
               p.medical_paid, pr.premium_total, pr.mm,
               1.0 * p.medical_paid / NULLIF(pr.premium_total / 12.0, 0) AS mlr_monthly_est
        FROM paid p
        LEFT JOIN prem pr USING (payer_id, plan_year)
    """)

    con.execute("""
        CREATE OR REPLACE TABLE gold_agg_pa_tat AS
        SELECT payer_id, plan_year, request_type,
               COUNT(*) AS pa_count,
               quantile_cont(tat_hours, 0.5) AS tat_median_hrs,
               quantile_cont(tat_hours, 0.95) AS tat_p95_hrs,
               1.0 * SUM(CASE WHEN sla_met THEN 1 ELSE 0 END) / COUNT(*) AS sla_compliance_pct
        FROM silver_auths
        GROUP BY 1, 2, 3
    """)

    con.execute("""
        CREATE OR REPLACE TABLE gold_agg_stars_compliance AS
        SELECT measure_id, plan_year, lob,
               SUM(CASE WHEN eligible THEN 1 ELSE 0 END) AS denominator,
               SUM(CASE WHEN compliant THEN 1 ELSE 0 END) AS numerator,
               1.0 * SUM(CASE WHEN compliant THEN 1 ELSE 0 END)
                   / NULLIF(SUM(CASE WHEN eligible THEN 1 ELSE 0 END), 0) AS compliance_pct
        FROM silver_quality_events
        GROUP BY 1, 2, 3
    """)

    # ----- New A.0c aggregates -----

    # HRRP 30-day readmission rate by cohort
    con.execute("""
        CREATE OR REPLACE TABLE gold_agg_readmissions AS
        SELECT plan_year, hrrp_cohort,
               COUNT(*) AS index_admits,
               SUM(CASE WHEN readmit_within_30d THEN 1 ELSE 0 END) AS readmits_30d,
               1.0 * SUM(CASE WHEN readmit_within_30d THEN 1 ELSE 0 END)
                   / NULLIF(COUNT(*), 0) AS readmit_rate_30d
        FROM silver_readmission
        GROUP BY 1, 2
    """)

    # GLP-1 PA volume + approval yield (KFF/IRA exposure)
    con.execute("""
        CREATE OR REPLACE TABLE gold_agg_glp1_pa_yield AS
        SELECT plan_year,
               COUNT(*) AS pa_count,
               SUM(CASE WHEN decision = 'approve' THEN 1 ELSE 0 END) AS approvals,
               SUM(CASE WHEN decision = 'deny' THEN 1 ELSE 0 END) AS denials,
               1.0 * SUM(CASE WHEN decision = 'approve' THEN 1 ELSE 0 END)
                   / NULLIF(COUNT(*), 0) AS approval_rate
        FROM silver_pharmacy_pa
        WHERE drug_class = 'GLP1'
        GROUP BY 1
    """)

    # SDOH burden by Gravity domain
    con.execute("""
        CREATE OR REPLACE TABLE gold_agg_sdoh_burden AS
        SELECT plan_year, domain,
               COUNT(*) AS assessed_count,
               SUM(CASE WHEN positive_screen THEN 1 ELSE 0 END) AS positive_count,
               1.0 * SUM(CASE WHEN positive_screen THEN 1 ELSE 0 END)
                   / NULLIF(COUNT(*), 0) AS positive_rate,
               SUM(CASE WHEN intervention_referred THEN 1 ELSE 0 END) AS referred_count
        FROM silver_sdoh_assessment
        GROUP BY 1, 2
    """)

    # Health Equity Index proxy: Stars compliance split by HEI-eligible vs non-HEI members
    con.execute("""
        CREATE OR REPLACE TABLE gold_agg_health_equity_index_proxy AS
        SELECT
            m.payer_id,
            q.plan_year,
            CASE WHEN m.hei_eligible_flag THEN 'hei_eligible' ELSE 'non_hei' END AS hei_segment,
            SUM(CASE WHEN q.eligible THEN 1 ELSE 0 END) AS denominator,
            SUM(CASE WHEN q.compliant THEN 1 ELSE 0 END) AS numerator,
            1.0 * SUM(CASE WHEN q.compliant THEN 1 ELSE 0 END)
                / NULLIF(SUM(CASE WHEN q.eligible THEN 1 ELSE 0 END), 0) AS compliance_pct
        FROM silver_quality_events q
        JOIN silver_members m USING (member_id)
        GROUP BY 1, 2, 3
    """)

    # OON exposure + NSA-eligible share + directory staleness (one row per payer/year + scalar stale_pct)
    con.execute("""
        CREATE OR REPLACE TABLE gold_agg_oon_directory_inaccuracy AS
        WITH oon AS (
            SELECT payer_id, plan_year,
                   COUNT(*) AS claims_total,
                   SUM(CASE WHEN oon_flag THEN 1 ELSE 0 END) AS oon_claims,
                   SUM(CASE WHEN nsa_eligible_flag THEN 1 ELSE 0 END) AS nsa_eligible_claims,
                   1.0 * SUM(CASE WHEN oon_flag THEN 1 ELSE 0 END)
                       / NULLIF(COUNT(*), 0) AS oon_pct,
                   1.0 * SUM(CASE WHEN nsa_eligible_flag THEN 1 ELSE 0 END)
                       / NULLIF(COUNT(*), 0) AS nsa_eligible_share
            FROM silver_claims_header
            GROUP BY 1, 2
        ),
        dir AS (
            SELECT 1.0 * SUM(CASE WHEN stale_flag THEN 1 ELSE 0 END)
                       / NULLIF(COUNT(*), 0) AS directory_stale_pct
            FROM silver_provider_directory_attestation
        )
        SELECT oon.*, dir.directory_stale_pct
        FROM oon CROSS JOIN dir
    """)

    gold_tables = [
        "dim_date", "dim_member", "dim_provider", "dim_payer", "dim_lob",
        "dim_product", "dim_diagnosis", "dim_procedure", "dim_drug", "dim_hcc",
        "fact_claim", "fact_rx_claim", "fact_auth", "fact_appeal", "fact_premium",
        "fact_member_month", "fact_quality_event", "fact_raf_score",
        "fact_pharmacy_pa", "fact_provider_sanction", "fact_provider_directory_attestation",
        "fact_readmission", "fact_sdoh_assessment", "fact_cahps_response",
        "fact_outreach", "fact_vbc_attribution",
        "agg_denial_by_payer", "agg_mlr_monthly", "agg_pa_tat", "agg_stars_compliance",
        "agg_readmissions", "agg_glp1_pa_yield", "agg_sdoh_burden",
        "agg_health_equity_index_proxy", "agg_oon_directory_inaccuracy",
    ]
    for t in gold_tables:
        con.execute(f"COPY gold_{t} TO '{(out / f'{t}.parquet').as_posix()}' (FORMAT PARQUET)")
    print(f"  gold: {len(gold_tables)} tables")


def smoke_checks(con: duckdb.DuckDBPyConnection) -> int:
    fails = 0
    print("\n[etl] gold smoke checks")
    checks = [
        ("fact_claim has rows", "SELECT COUNT(*) > 0 FROM gold_fact_claim"),
        ("fact_member_month rows == enrollment expansion",
         "SELECT (SELECT COUNT(*) FROM gold_fact_member_month) = "
         "(SELECT SUM(end_month - start_month + 1) FROM bronze_enrollment_spans)"),
        ("denial rate 0.05-0.25",
         "SELECT (1.0*SUM(denied_int)/COUNT(*)) BETWEEN 0.05 AND 0.25 FROM gold_fact_claim"),
        ("dim_member unique", "SELECT COUNT(*) = COUNT(DISTINCT member_id) FROM gold_dim_member"),
        ("agg_stars_compliance has rows", "SELECT COUNT(*) > 0 FROM gold_agg_stars_compliance"),
        ("agg_pa_tat has rows", "SELECT COUNT(*) > 0 FROM gold_agg_pa_tat"),
        ("agg_readmissions overall rate 0.05-0.35",
         "SELECT (1.0*SUM(readmits_30d)/NULLIF(SUM(index_admits),0)) BETWEEN 0.05 AND 0.35 FROM gold_agg_readmissions"),
        ("agg_glp1_pa_yield has rows", "SELECT COUNT(*) > 0 FROM gold_agg_glp1_pa_yield"),
        ("agg_sdoh_burden has rows", "SELECT COUNT(*) > 0 FROM gold_agg_sdoh_burden"),
        ("agg_health_equity_index_proxy has rows",
         "SELECT COUNT(*) > 0 FROM gold_agg_health_equity_index_proxy"),
        ("agg_oon_directory_inaccuracy oon_pct 0.0-0.3",
         "SELECT MIN(oon_pct) >= 0.0 AND MAX(oon_pct) <= 0.3 FROM gold_agg_oon_directory_inaccuracy"),
    ]
    for name, sql in checks:
        ok = con.execute(sql).fetchone()[0]
        tag = "PASS" if ok else "FAIL"
        if not ok: fails += 1
        print(f"  [{tag}] {name}")
    return fails


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", default="smoke")
    args = p.parse_args()

    src = SYNTH / args.run_id
    if not src.exists():
        print(f"[etl] missing source: {src}", file=sys.stderr)
        return 2

    out = LAKE / args.run_id
    print(f"[etl] {src} -> {out}")

    # Lazy import so audit_log stays optional for users who patch this file.
    from audit_log import audit_stage  # noqa: PLC0415

    con = duckdb.connect(":memory:")
    print("[etl] bronze...")
    with audit_stage(args.run_id, "local_etl", "bronze", "run_local_etl.bronze") as a:
        bronze(con, src, out / "bronze")
        a.rowcount_out = int(con.execute(
            "SELECT SUM(c) FROM (" + " UNION ALL ".join(
                f"SELECT COUNT(*) AS c FROM bronze_{t}" for t in BRONZE_TABLES
            ) + ")"
        ).fetchone()[0] or 0)
        a.table_count = len(BRONZE_TABLES)

    print("[etl] silver...")
    with audit_stage(args.run_id, "local_etl", "silver", "run_local_etl.silver") as a:
        silver(con, out / "silver")
        # Count by scanning what silver wrote (excluding registered bronze tables).
        silver_names = [r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name LIKE 'silver_%'"
        ).fetchall()]
        a.rowcount_in = int(con.execute(
            "SELECT SUM(c) FROM (" + " UNION ALL ".join(
                f"SELECT COUNT(*) AS c FROM bronze_{t}" for t in BRONZE_TABLES
            ) + ")"
        ).fetchone()[0] or 0)
        a.rowcount_out = int(con.execute(
            "SELECT SUM(c) FROM (" + " UNION ALL ".join(
                f"SELECT COUNT(*) AS c FROM {n}" for n in silver_names
            ) + ")"
        ).fetchone()[0] or 0)
        a.table_count = len(silver_names)

    print("[etl] gold...")
    with audit_stage(args.run_id, "local_etl", "gold", "run_local_etl.gold") as a:
        gold(con, out / "gold")
        gold_names = [r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name LIKE 'gold_%'"
        ).fetchall()]
        a.rowcount_out = int(con.execute(
            "SELECT SUM(c) FROM (" + " UNION ALL ".join(
                f"SELECT COUNT(*) AS c FROM {n}" for n in gold_names
            ) + ")"
        ).fetchone()[0] or 0)
        a.table_count = len(gold_names)

    fails = smoke_checks(con)
    if fails:
        print(f"\n[etl] FAIL - {fails} check(s)")
        return 1
    print("\n[etl] PASS - 0 check failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

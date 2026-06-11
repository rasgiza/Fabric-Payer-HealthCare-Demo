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

    for t in ["dim_date", "members", "claims_header", "claims_line", "rx_claims",
              "auths", "appeals", "premiums", "providers", "payers", "conditions",
              "raf_scores", "quality_events", "member_month"]:
        con.execute(f"COPY silver_{t} TO '{(out / f'{t}.parquet').as_posix()}' (FORMAT PARQUET)")
    print("  silver: 14 tables (incl. member_month, dim_date)")


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

    gold_tables = [
        "dim_date", "dim_member", "dim_provider", "dim_payer", "dim_lob",
        "dim_product", "dim_diagnosis", "dim_procedure", "dim_drug", "dim_hcc",
        "fact_claim", "fact_rx_claim", "fact_auth", "fact_appeal", "fact_premium",
        "fact_member_month", "fact_quality_event", "fact_raf_score",
        "agg_denial_by_payer", "agg_mlr_monthly", "agg_pa_tat", "agg_stars_compliance",
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

    con = duckdb.connect(":memory:")
    print("[etl] bronze...")
    bronze(con, src, out / "bronze")
    print("[etl] silver...")
    silver(con, out / "silver")
    print("[etl] gold...")
    gold(con, out / "gold")
    fails = smoke_checks(con)
    if fails:
        print(f"\n[etl] FAIL - {fails} check(s)")
        return 1
    print("\n[etl] PASS - 0 check failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

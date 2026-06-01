# Lakehouse schema (Phase 2 — gold star schema)

The gold layer is the source of truth for the PayerAnalytics semantic model (Phase 4) and all Foundry data agents (Phase 5). DuckDB-validated locally via `tools/run_local_etl.py`; the same SQL ports to Spark in Phase 7.

## Layers

| Layer | Path | Purpose |
|---|---|---|
| Bronze | `data/lakehouse/<run>/bronze/*.parquet` | Raw CSV → Parquet, no transforms |
| Silver | `data/lakehouse/<run>/silver/*.parquet` | Type cast, dedup, de-id (zip3 / mbi hash / age band), member-month explosion, code enrichment |
| Gold | `data/lakehouse/<run>/gold/*.parquet` | Star schema: dimensions, facts, aggregates |

## Gold dimensions

| Table | Grain | Notes |
|---|---|---|
| `dim_date` | one row per date | `date_key` (yyyymmdd int), year, month, quarter, year_month |
| `dim_member` | one row per member | includes `age_band`, SDOH flags, MBI hash |
| `dim_provider` | one row per NPI | specialty, in-network, APM tier, gold-card flag |
| `dim_payer` | one row per payer | name, parent org, market states |
| `dim_plan` | one row per plan_id | (Phase 4 — populated from members) |
| `dim_product` | one row per product | derived from members |
| `dim_lob` | one row per LOB | MA / Medicaid / Commercial / Dual |
| `dim_diagnosis` | one row per ICD-10 | from claims primary_dx |
| `dim_procedure` | one row per CPT/HCPCS | from claim lines |
| `dim_drug` | one row per NDC | name + class |
| `dim_hcc` | one row per HCC V28 | from conditions |

## Gold facts

| Table | Grain | Key measures |
|---|---|---|
| `fact_claim` | claim_id × line_no | billed/allowed/paid, denied_int, paid_int, member_liability, pa_required_flag, carc_code |
| `fact_rx_claim` | rx_claim_id | days_supply, paid_amount, formulary_tier (drives PDC) |
| `fact_auth` | auth_id | tat_hours, sla_met, decision, request_type, submitted_via_fhir |
| `fact_appeal` | appeal_id | level, carc, decision, peer_to_peer_flag |
| `fact_premium` | member_id × plan_year | premium_pmpm, premium_total, member_months |
| `fact_member_month` | member_id × plan_year × month | year_month_key for membership trend |
| `fact_quality_event` | member_id × measure_id × plan_year | eligible / compliant flags |
| `fact_raf_score` | member_id × plan_year | demographic_raf, coded_hcc_count, suspect_hcc_count, raf_score |

## Gold aggregates

| Table | Grain | Drives |
|---|---|---|
| `agg_denial_by_payer` | payer × plan_year | CFOAgent denial-rate measures |
| `agg_mlr_monthly` | payer × plan_year × month | CFOAgent MLR trend |
| `agg_pa_tat` | payer × plan_year × request_type | UMAgent TAT median, p95, SLA compliance % |
| `agg_stars_compliance` | measure × plan_year × LOB | StarsAgent compliance %, cut-point gap |

## Phase 4 follow-on aggregates (not yet built)

- `agg_pdc_member_drugclass` — PDC numerator/denominator per member × drug class
- `agg_rising_risk` — high-cost-trajectory cohort flag per member-month
- `agg_network_adequacy` — provider counts per (specialty, county_type)

## Local validation gates (in `run_local_etl.py`)

1. `fact_claim` has rows
2. `fact_member_month` row count = sum of enrollment span months (no gaps)
3. denial rate in 5–25% band (gold-side sanity, broader than synth-side audit)
4. `dim_member` PK uniqueness
5. `agg_stars_compliance` has rows
6. `agg_pa_tat` has rows

All six PASS on the smoke run (500 members × 5 years).

## Fabric port (Phase 7)

The same SQL runs verbatim in Fabric notebooks via `spark.sql(...)`:
- Bronze: replace `read_csv_auto(...)` with Lakehouse Files mount path.
- Silver/Gold: identical CTEs.
- Output: `df.write.mode("overwrite").format("delta").saveAsTable("lh_gold_payer.<table>")` instead of `COPY ... TO ... PARQUET`.

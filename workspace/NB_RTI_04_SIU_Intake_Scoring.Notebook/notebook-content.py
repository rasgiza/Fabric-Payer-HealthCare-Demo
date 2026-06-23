# Fabric notebook source

# METADATA **{"language":"markdown"}**

# MARKDOWN **{"language":"markdown"}**

# # NB_RTI_04 - SIU Intake Scoring (SIU persona)
#
# Scores incoming claim_arrivals against simple intake heuristics so the SIU
# (Special Investigations Unit) gets a ranked queue of suspect claims at
# adjudication time, not after payment. Reads directly from the
# `claim_arrivals` table that NB_RTI_01 seeds + es_claims_arrivals streams.
#
# **Default lakehouse must be `lh_bronze_raw` when running manually.**
#
# Unlike NB_RTI_02 / NB_RTI_03, this notebook does NOT seed its own events --
# it reads the existing `claim_arrivals` table populated by NB_RTI_01 /
# es_claims_arrivals. Run NB_RTI_01 first if the table is empty.
#
# **Parameters**:
# - `lookback_min`  - score claims arriving in the last N minutes (default: 60)
# - `score_threshold` - emit a SIU alert if intake_score >= threshold
#       (default: 0.6; matches the C.4 Activator rule's predicate)
# - `kql_cluster_uri` - eh_payer_rt query endpoint; must be set when
#       `dry_run=False`
# - `kql_database`  - target KQL database (default: `kqldb_payer_rt`)
# - `dry_run`       - if True, print KQL but skip Kusto read
#       (default: True; publishable before the Eventhouse is provisioned)

# METADATA **{"language":"python"}**

# PARAMETERS CELL **{"language":"python"}**

lookback_min = 60
score_threshold = 0.6
kql_cluster_uri = ""
kql_database = "kqldb_payer_rt"
dry_run = True

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# Locked scored-output schema. C.4 Activator rule + C.6 RUNBOOK consume
# this projection; do not edit either side in isolation.
SIU_SCORE_COLUMNS = [
    "claim_id",
    "arrived_at",
    "payer_id",
    "provider_id",
    "member_id",
    "billed_amount",
    "intake_score",
    "score_reasons",
]

assert 0.0 <= score_threshold <= 1.0, (
    f"score_threshold must be in [0, 1], got {score_threshold}"
)
assert lookback_min >= 1, f"lookback_min must be >= 1, got {lookback_min}"
assert kql_database, "kql_database must be non-empty"

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# Locked KQL: simple additive intake score from three signals. C.4
# Activator predicate is `intake_score >= score_threshold`. Update both
# sides in the same commit if the formula changes.
#
# Signals (each contributes 0.25 -- so max possible score = 0.75; a 4th
# signal will land in a later C.x iteration):
#   * billed_amount > 3x payer+claim_type median (lognormal-tail outlier)
#   * submission_channel == "fax_ocr"
#   * prior_auth_present == false AND claim_type == "professional"
SIU_SCORING_KQL = """
let lookback = {lookback_min}m;
let recent = claim_arrivals | where arrived_at > ago(lookback);
let medians = recent
    | summarize median_billed = percentile(billed_amount, 50)
        by payer_id, claim_type;
recent
| join kind=inner medians on payer_id, claim_type
| extend sig_amount = iff(billed_amount > 3.0 * median_billed, 0.25, 0.0)
| extend sig_channel = iff(submission_channel == "fax_ocr", 0.25, 0.0)
| extend sig_noauth = iff(prior_auth_present == false
                          and claim_type == "professional", 0.25, 0.0)
| extend intake_score = sig_amount + sig_channel + sig_noauth
| extend score_reasons = strcat(
    iff(sig_amount > 0, "billed_outlier;", ""),
    iff(sig_channel > 0, "fax_ocr;", ""),
    iff(sig_noauth > 0, "no_pa_professional;", "")
  )
| where intake_score >= {score_threshold}
| project claim_id, arrived_at, payer_id, provider_id, member_id,
          billed_amount, intake_score, score_reasons
| order by intake_score desc, arrived_at desc
""".strip()

# {lookback_min} / {score_threshold} are substituted at run time so the
# operator can move the dial without editing the notebook.
rendered_kql = SIU_SCORING_KQL.format(
    lookback_min=lookback_min,
    score_threshold=score_threshold,
)
print("[rti_04] KQL query:")
print(rendered_kql)

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

if dry_run:
    print(f"[rti_04] dry_run=True -> skipping query against "
          f"{kql_database}.claim_arrivals")
else:
    assert kql_cluster_uri, "kql_cluster_uri must be set when dry_run=False"
    result = (
        spark.read  # noqa: F821  (Fabric-provided)
             .format("com.microsoft.kusto.spark.synapse.datasource")
             .option("kustoCluster", kql_cluster_uri)
             .option("kustoDatabase", kql_database)
             .option("kustoQuery", rendered_kql)
             .load()
    )
    result.show(50, truncate=False)
    n = result.count()
    print(f"[rti_04] PASS - {n} suspect claims at threshold>={score_threshold}")

print("[rti_04] done")

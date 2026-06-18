# Fabric notebook source

# METADATA **{"language":"markdown"}**

# MARKDOWN **{"language":"markdown"}**

# # Fabric Payer Healthcare Demo — Launcher
#
# **Single entry point** for the post-deploy steps after `fabric-cicd` publishes
# the workspace. Run All to:
#
# 1. Resolve workspace + lakehouse identifiers at runtime
# 2. Invoke the medallion notebook chain (NB_01 → NB_02 → NB_03) with the
#    chosen `run_id` and `mode`
# 3. Print a one-line gold-tier sanity check
#
# > Stream A is the **batch + notebook** layer only. Foundry data agents
# > (Stream B) and Real-Time Intelligence (Stream C) attach to the same gold
# > lakehouse but are deployed separately.

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ============================================================================
# CONFIGURATION — edit these values
# ============================================================================

# The synthetic batch under Files/synth/<run_id>/ that NB_01 will ingest.
RUN_ID = "smoke"

# 'overwrite' on first run (rebuilds bronze), 'append' for incremental days.
MODE = "overwrite"

# Set False if data is already in lh_bronze_raw and you only want to rebuild
# silver + gold (useful for iterating on transforms).
RUN_BRONZE = True

workspace_id = spark.conf.get("trident.workspace.id")
print(f"Workspace: {workspace_id}")
print(f"run_id={RUN_ID}  mode={MODE}  run_bronze={RUN_BRONZE}")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ============================================================================
# Run the medallion notebook chain
# ============================================================================
# Each step times out after 60 minutes (3600 sec). PL_Payer_Master is the
# schedulable production path; this launcher is the interactive equivalent
# so we don't need pipeline RBAC to drive a fresh workspace.

from notebookutils import mssparkutils

results: dict[str, str] = {}

if RUN_BRONZE:
    results["NB_01_Bronze_Ingest"] = mssparkutils.notebook.run(
        "NB_01_Bronze_Ingest",
        3600,
        {"run_id": RUN_ID, "mode": MODE},
    )

results["NB_02_Silver_Transform"] = mssparkutils.notebook.run(
    "NB_02_Silver_Transform", 3600, {}
)

results["NB_03_Gold_Build"] = mssparkutils.notebook.run(
    "NB_03_Gold_Build", 3600, {}
)

for k, v in results.items():
    print(f"[{k}] exit={v}")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ============================================================================
# Sanity check — confirm gold tier published the headline aggregates
# ============================================================================

REQUIRED_GOLD = [
    "dim_member",
    "dim_date",
    "fact_claim",
    "fact_pharmacy_pa",
    "agg_denial_by_payer",
    "agg_pa_tat",
    "agg_stars_compliance",
    "agg_health_equity_index_proxy",
]

missing = []
for t in REQUIRED_GOLD:
    n = spark.sql(f"SELECT COUNT(*) AS n FROM lh_gold_curated.{t}").collect()[0]["n"]
    if n == 0:
        missing.append(f"{t} (empty)")
    print(f"  {t:40s} rows={n}")

if missing:
    raise RuntimeError(f"[launcher] FAIL — empty gold tables: {missing}")

print("\n[launcher] PASS — gold tier ready for PayerAnalytics SemanticModel + 7 Foundry data agents")

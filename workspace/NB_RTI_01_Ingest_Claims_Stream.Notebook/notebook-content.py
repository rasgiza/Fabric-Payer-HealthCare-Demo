# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   }
# META }

# MARKDOWN ********************

# METADATA ********************

# META {
# META   "language": "markdown"
# META }

# # NB_RTI_01 - Ingest Claims Stream (Payer)
#
# Demo-time replay path into the RTI Eventhouse. Generates synthetic
# `claim_arrivals` events deterministically from the same seed used by NB_00
# (so the streaming demo matches the batch demo) and ingests them into
# `kqldb_payer_rt.claim_arrivals` via the Kusto Spark connector.
#
# Production / steady-state ingest happens through `es_claims_arrivals`
# (Eventstream); this notebook exists so a presenter can land a fresh batch
# of events at the start of the demo without waiting for a live source.
#
# **Default lakehouse must be `lh_bronze_raw` when running manually.**
#
# **Parameters** (set by `Healthcare_Launcher` or `PL_Payer_Master`):
# - `run_id`        - synth batch under `Files/synth/` (default: `smoke`)
# - `event_count`   - number of claim_arrival events to emit (default: 5000)
# - `lookback_min`  - spread events over the past N minutes (default: 60)
# - `seed`          - RNG seed (default: 42; matches NB_00 default)
# - `kql_cluster_uri` - eh_payer_rt query endpoint; e.g.
#       `https://<eh-id>.<region>.kusto.fabric.microsoft.com`
#       (must be set; the launcher resolves it from the live Eventhouse)
# - `kql_database`  - target KQL database name (default: `kqldb_payer_rt`)
# - `kql_table`     - target table name (default: `claim_arrivals`)
# - `dry_run`       - if True, generate + stage parquet but skip Kusto ingest
#       (default: True so this notebook is safe to publish before the
#       Eventhouse cluster URI is wired up)

# METADATA **{"language":"python"}**

# PARAMETERS CELL **{"language":"python"}**

run_id = "smoke"
event_count = 5000
lookback_min = 60
seed = 42
kql_cluster_uri = ""
kql_database = "kqldb_payer_rt"
kql_table = "claim_arrivals"
dry_run = True

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

# claim_arrivals event schema. Kept here (not in a separate module) so the
# Eventhouse table DDL in C.3 + the Activator rules in C.4 can lift the same
# column list verbatim. The test_rti_c2_skeleton.py shape test parses this
# literal to lock the schema across the stream + KQL + Activator surfaces.
CLAIM_ARRIVAL_COLUMNS = [
    "claim_id",
    "arrived_at",
    "payer_id",
    "provider_id",
    "member_id",
    "billed_amount",
    "service_line_count",
    "claim_type",
    "submission_channel",
    "prior_auth_present",
]

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

assert kql_database, "kql_database must be non-empty"
assert kql_table, "kql_table must be non-empty"
assert event_count >= 1, f"event_count must be >= 1, got {event_count}"
assert lookback_min >= 1, f"lookback_min must be >= 1, got {lookback_min}"

rng = random.Random(seed)
now = datetime.now(timezone.utc).replace(microsecond=0)
window_start = now - timedelta(minutes=lookback_min)

PAYERS = ["P001", "P002", "P003", "P004", "P005"]
CLAIM_TYPES = ["professional", "institutional", "pharmacy"]
CHANNELS = ["edi_837", "portal", "fax_ocr"]

rows = []
for i in range(event_count):
    arrived_offset_s = rng.uniform(0, lookback_min * 60)
    arrived_at = window_start + timedelta(seconds=arrived_offset_s)
    rows.append({
        "claim_id":           f"CLM-{run_id}-{i:07d}",
        "arrived_at":         arrived_at.isoformat(),
        "payer_id":           rng.choice(PAYERS),
        "provider_id":        f"PRV-{rng.randint(1, 250):05d}",
        "member_id":          f"MBR-{rng.randint(1, 9500):07d}",
        "billed_amount":      round(rng.lognormvariate(5.6, 1.1), 2),
        "service_line_count": rng.randint(1, 8),
        "claim_type":         rng.choices(CLAIM_TYPES, weights=[0.6, 0.3, 0.1])[0],
        "submission_channel": rng.choices(CHANNELS, weights=[0.85, 0.12, 0.03])[0],
        "prior_auth_present": rng.random() < 0.18,
    })
events = pd.DataFrame(rows, columns=CLAIM_ARRIVAL_COLUMNS)
print(f"[rti_01] generated {len(events):,} events over {lookback_min} min "
      f"window ending {now.isoformat()}")

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

# Stage to parquet under Files/rt/<run_id>/ so the Eventstream's "OneLake
# parquet" source can pick it up too (C.2 demo path: presenter runs this
# notebook, Eventstream replays the parquet at wall-clock speed).
STAGE = Path(f"/lakehouse/default/Files/rt/{run_id}")
STAGE.mkdir(parents=True, exist_ok=True)
parquet_path = STAGE / "claim_arrivals.parquet"
events.to_parquet(parquet_path, index=False)
print(f"[rti_01] staged parquet -> {parquet_path}  ({parquet_path.stat().st_size:,} bytes)")

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

# Direct ingest into kqldb_payer_rt. Skipped when dry_run=True so this
# notebook is safe to publish before the Eventhouse cluster URI is known.
if dry_run:
    print(f"[rti_01] dry_run=True -> skipping Kusto ingest into "
          f"{kql_database}.{kql_table}; parquet is on OneLake for "
          f"Eventstream replay")
else:
    assert kql_cluster_uri, "kql_cluster_uri must be set when dry_run=False"
    # Spark Kusto connector (com.microsoft.azure.kusto:kusto-spark) ships in
    # the Fabric Spark runtime; auth uses the workspace MSI.
    sdf = spark.createDataFrame(events)  # noqa: F821  (spark provided by Fabric)
    (
        sdf.write
           .format("com.microsoft.kusto.spark.synapse.datasource")
           .option("kustoCluster", kql_cluster_uri)
           .option("kustoDatabase", kql_database)
           .option("kustoTable", kql_table)
           .option("tableCreateOptions", "CreateIfNotExist")
           .mode("Append")
           .save()
    )
    print(f"[rti_01] ingested {len(events):,} rows into "
          f"{kql_database}.{kql_table}")

print("[rti_01] PASS")

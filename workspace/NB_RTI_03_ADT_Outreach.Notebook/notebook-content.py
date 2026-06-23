# Fabric notebook source

# METADATA **{"language":"markdown"}**

# MARKDOWN **{"language":"markdown"}**

# # NB_RTI_03 - ADT Outreach (CareMgmt persona)
#
# Watches ADT admission/discharge events arriving from contracted facilities
# and emits a care-management outreach worklist: members admitted in the last
# N hours who haven't been touched by CareMgmt within a 24h window. Pairs
# with the C.4 Activator rule that routes the worklist to the CareMgmt queue
# in Teams.
#
# **Default lakehouse must be `lh_bronze_raw` when running manually.**
#
# **Parameters**:
# - `run_id`        - seed batch tag (default: `smoke`)
# - `event_count`   - number of ADT events to seed (default: 1500)
# - `lookback_min`  - spread events over the past N minutes (default: 180)
# - `seed`          - RNG seed (default: 42)
# - `kql_cluster_uri` - eh_payer_rt query endpoint; must be set when
#       `dry_run=False`
# - `kql_database`  - target KQL database (default: `kqldb_payer_rt`)
# - `kql_table`     - target table (default: `adt_admissions`)
# - `dry_run`       - if True, seed parquet + print KQL but skip Kusto I/O
#       (default: True; publishable before the Eventhouse is provisioned)

# METADATA **{"language":"python"}**

# PARAMETERS CELL **{"language":"python"}**

run_id = "smoke"
event_count = 1500
lookback_min = 180
seed = 42
kql_cluster_uri = ""
kql_database = "kqldb_payer_rt"
kql_table = "adt_admissions"
dry_run = True

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# Locked event schema. C.4 Activator rule + C.6 RUNBOOK lift this verbatim.
ADT_ADMISSION_COLUMNS = [
    "adt_event_id",
    "member_id",
    "facility_id",
    "event_at",
    "event_type",
    "admit_source",
    "primary_dx_chapter",
    "expected_los_days",
]

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

assert kql_database, "kql_database must be non-empty"
assert kql_table, "kql_table must be non-empty"
assert event_count >= 1, f"event_count must be >= 1, got {event_count}"

rng = random.Random(seed)
now = datetime.now(timezone.utc).replace(microsecond=0)
window_start = now - timedelta(minutes=lookback_min)

EVENT_TYPES = ["admit", "discharge", "transfer"]
ADMIT_SOURCES = ["emergency", "elective", "transfer_in", "observation"]
DX_CHAPTERS = ["circulatory", "respiratory", "endocrine", "behavioral",
               "musculoskeletal", "injury", "obstetric", "neoplasm"]

rows = []
for i in range(event_count):
    event_at = window_start + timedelta(seconds=rng.uniform(0, lookback_min * 60))
    event_type = rng.choices(EVENT_TYPES, weights=[0.55, 0.35, 0.10])[0]
    rows.append({
        "adt_event_id":       f"ADT-{run_id}-{i:07d}",
        "member_id":          f"MBR-{rng.randint(1, 9500):07d}",
        "facility_id":        f"FAC-{rng.randint(1, 40):04d}",
        "event_at":           event_at.isoformat(),
        "event_type":         event_type,
        "admit_source":       rng.choices(ADMIT_SOURCES, weights=[0.45, 0.30, 0.15, 0.10])[0],
        "primary_dx_chapter": rng.choice(DX_CHAPTERS),
        "expected_los_days":  rng.randint(1, 14),
    })
events = pd.DataFrame(rows, columns=ADT_ADMISSION_COLUMNS)
admits = (events["event_type"] == "admit").sum()
emergencies = ((events["event_type"] == "admit") & (events["admit_source"] == "emergency")).sum()
print(f"[rti_03] seeded {len(events):,} ADT events ({admits} admits, "
      f"{emergencies} emergency)")

STAGE = Path(f"/lakehouse/default/Files/rt/{run_id}")
STAGE.mkdir(parents=True, exist_ok=True)
parquet_path = STAGE / "adt_admissions.parquet"
events.to_parquet(parquet_path, index=False)
print(f"[rti_03] staged parquet -> {parquet_path}")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# Locked KQL query: emergency admits in the last 4h that have not been
# touched by a CareMgmt outreach (member_outreach table assumed populated
# by the existing batch path). C.4 Activator rule predicates this exact
# shape; do not edit without bumping the rule's WHERE clause.
ADT_OUTREACH_KQL = """
let lookback = 4h;
let outreach_window = 24h;
adt_admissions
| where event_at > ago(lookback)
| where event_type == "admit"
| where admit_source == "emergency"
| join kind=leftanti (
    member_outreach
    | where outreach_at > ago(outreach_window)
    | project member_id, outreach_at
  ) on member_id
| project
    member_id,
    facility_id,
    admit_at = event_at,
    primary_dx_chapter,
    expected_los_days,
    priority = case(
        primary_dx_chapter == "circulatory", "high",
        primary_dx_chapter == "respiratory", "high",
        primary_dx_chapter == "behavioral",  "high",
        "standard"
    )
| order by admit_at desc
""".strip()

print("[rti_03] KQL query:")
print(ADT_OUTREACH_KQL)

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

if dry_run:
    print(f"[rti_03] dry_run=True -> skipping ingest + query against "
          f"{kql_database}.{kql_table}")
else:
    assert kql_cluster_uri, "kql_cluster_uri must be set when dry_run=False"
    sdf = spark.createDataFrame(events)  # noqa: F821  (Fabric-provided)
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
    result = (
        spark.read
             .format("com.microsoft.kusto.spark.synapse.datasource")
             .option("kustoCluster", kql_cluster_uri)
             .option("kustoDatabase", kql_database)
             .option("kustoQuery", ADT_OUTREACH_KQL)
             .load()
    )
    result.show(50, truncate=False)
    print(f"[rti_03] PASS - {result.count()} outreach candidates")

print("[rti_03] done")

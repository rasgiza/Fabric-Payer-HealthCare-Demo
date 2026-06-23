# Fabric notebook source

# METADATA **{"language":"markdown"}**

# MARKDOWN **{"language":"markdown"}**

# # NB_RTI_02 - PA Latency (UM persona, CMS-0057-F)
#
# Monitors prior-auth turnaround against the CMS Interoperability and Prior
# Authorization Final Rule (CMS-0057-F): standard requests must be decided
# within 7 calendar days, expedited within 72 hours. This notebook seeds a
# deterministic `auth_lifecycle` event stream into `kqldb_payer_rt`, then
# runs the KQL aggregation that the UM dashboard + the C.4 Activator rule
# both consume.
#
# **Default lakehouse must be `lh_bronze_raw` when running manually.**
#
# **Parameters**:
# - `run_id`        - seed batch tag (default: `smoke`)
# - `event_count`   - number of auth decisions to seed (default: 2000)
# - `lookback_min`  - spread events over the past N minutes (default: 240)
# - `seed`          - RNG seed (default: 42)
# - `kql_cluster_uri` - eh_payer_rt query endpoint; must be set when
#       `dry_run=False`
# - `kql_database`  - target KQL database (default: `kqldb_payer_rt`)
# - `kql_table`     - target table (default: `auth_lifecycle`)
# - `dry_run`       - if True, seed parquet + print KQL but skip Kusto I/O
#       (default: True; publishable before the Eventhouse is provisioned)

# METADATA **{"language":"python"}**

# PARAMETERS CELL **{"language":"python"}**

run_id = "smoke"
event_count = 2000
lookback_min = 240
seed = 42
kql_cluster_uri = ""
kql_database = "kqldb_payer_rt"
kql_table = "auth_lifecycle"
dry_run = True

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# Locked event schema. C.4 Activator rule + C.6 RUNBOOK lift this verbatim.
AUTH_LIFECYCLE_COLUMNS = [
    "auth_id",
    "member_id",
    "provider_id",
    "service_category",
    "requested_at",
    "decided_at",
    "decision",
    "is_expedited",
    "latency_hours",
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

SERVICE_CATEGORIES = ["imaging", "surgical", "dme", "pharmacy", "behavioral"]
DECISIONS = ["approved", "denied", "pended"]

rows = []
for i in range(event_count):
    requested = window_start + timedelta(seconds=rng.uniform(0, lookback_min * 60))
    is_expedited = rng.random() < 0.18
    # Expedited target = 72h, standard target = 168h (7 days). Bias the
    # synthetic distribution so the demo shows both compliant + breaching
    # bands: 75% inside SLA, 20% near the line, 5% breach.
    if is_expedited:
        latency = rng.choices([rng.uniform(2, 60), rng.uniform(60, 72), rng.uniform(72, 96)],
                              weights=[0.75, 0.20, 0.05])[0]
    else:
        latency = rng.choices([rng.uniform(4, 120), rng.uniform(120, 168), rng.uniform(168, 240)],
                              weights=[0.75, 0.20, 0.05])[0]
    decided = requested + timedelta(hours=latency)
    rows.append({
        "auth_id":          f"AUTH-{run_id}-{i:07d}",
        "member_id":        f"MBR-{rng.randint(1, 9500):07d}",
        "provider_id":      f"PRV-{rng.randint(1, 250):05d}",
        "service_category": rng.choice(SERVICE_CATEGORIES),
        "requested_at":     requested.isoformat(),
        "decided_at":       decided.isoformat(),
        "decision":         rng.choices(DECISIONS, weights=[0.62, 0.28, 0.10])[0],
        "is_expedited":     is_expedited,
        "latency_hours":    round(latency, 2),
    })
events = pd.DataFrame(rows, columns=AUTH_LIFECYCLE_COLUMNS)
breach_pct = (events.apply(
    lambda r: (r["is_expedited"] and r["latency_hours"] > 72)
              or ((not r["is_expedited"]) and r["latency_hours"] > 168),
    axis=1,
).sum() / len(events)) * 100
print(f"[rti_02] seeded {len(events):,} auth decisions, {breach_pct:.1f}% breach CMS-0057-F SLA")

STAGE = Path(f"/lakehouse/default/Files/rt/{run_id}")
STAGE.mkdir(parents=True, exist_ok=True)
parquet_path = STAGE / "auth_lifecycle.parquet"
events.to_parquet(parquet_path, index=False)
print(f"[rti_02] staged parquet -> {parquet_path}")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# Locked KQL query. Tests pin this string so C.4 Activator + C.6 RUNBOOK
# can lift it verbatim; drift would break the downstream rule predicate.
PA_LATENCY_KQL = """
auth_lifecycle
| where decided_at > ago(4h)
| extend sla_hours = iff(is_expedited, 72.0, 168.0)
| extend breached = latency_hours > sla_hours
| summarize
    decisions     = count(),
    breaches      = countif(breached),
    p50_latency_h = percentile(latency_hours, 50),
    p90_latency_h = percentile(latency_hours, 90),
    p99_latency_h = percentile(latency_hours, 99)
    by bin(decided_at, 15m), is_expedited
| extend breach_rate = todouble(breaches) / todouble(decisions)
| order by decided_at desc, is_expedited asc
""".strip()

print("[rti_02] KQL query:")
print(PA_LATENCY_KQL)

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

if dry_run:
    print(f"[rti_02] dry_run=True -> skipping ingest + query against "
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
             .option("kustoQuery", PA_LATENCY_KQL)
             .load()
    )
    result.show(50, truncate=False)
    print(f"[rti_02] PASS - {result.count()} window rows returned")

print("[rti_02] done")

"""
audit_log.py — Pipeline run audit log emitter.

Writes one row per medallion-layer stage transition into a dedicated audit
table so downstream observability (PBI report, Workbook, KQL query) can
reconcile rowcounts, durations, and statuses across the full ETL pipeline.

Two modes:
  - **Local** (DuckDB / pandas): rows append to
        data/lakehouse/<run_id>/audit/audit_log.parquet
    Used by tools/run_local_etl.py and by tests/test_audit_log.py.
  - **Fabric / Spark**: the schema dict + build_row() helper are imported by
    NB_01 / NB_02 / NB_03 inline; rows are written by
        spark.createDataFrame([row], AUDIT_LOG_SCHEMA_SPARK)
             .write.mode("append").format("delta")
             .saveAsTable("audit_log")
    on the lh_gold_curated lakehouse.

Schema is INTENTIONALLY MINIMAL — every column has a clear business question:

| column            | question                                          |
|-------------------|---------------------------------------------------|
| audit_id          | unique row id (uuid4)                             |
| run_id            | which pipeline run                                |
| pipeline          | which orchestrator (PL_Payer_Full_Load / local)   |
| layer             | bronze / silver / gold                            |
| stage_name        | notebook or function name                         |
| rowcount_in       | rows read from prior layer (nullable for bronze)  |
| rowcount_out      | rows written to this layer                        |
| table_count       | distinct tables written this stage                |
| duration_ms       | wall-clock                                        |
| status            | success / failed                                  |
| error_msg         | exception summary on failure                      |
| started_at        | UTC timestamp                                     |
| completed_at      | UTC timestamp                                     |
| user_principal    | who ran it (nullable for service principals)      |
| git_sha           | commit pinning the code (nullable)                |
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LAKE = ROOT / "data" / "lakehouse"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

# pandas dtype mapping. For Spark, NB_01/02/03 use the equivalent StructType
# inline; the column list and order must stay in lockstep.
AUDIT_LOG_DTYPES: dict[str, str] = {
    "audit_id": "string",
    "run_id": "string",
    "pipeline": "string",
    "layer": "string",
    "stage_name": "string",
    "rowcount_in": "Int64",  # nullable int
    "rowcount_out": "Int64",
    "table_count": "Int64",
    "duration_ms": "Int64",
    "status": "string",
    "error_msg": "string",
    "started_at": "datetime64[us, UTC]",
    "completed_at": "datetime64[us, UTC]",
    "user_principal": "string",
    "git_sha": "string",
}

AUDIT_LOG_COLUMNS: tuple[str, ...] = tuple(AUDIT_LOG_DTYPES.keys())


@dataclass
class AuditRow:
    """One audit row. Build via .start() context manager or manually."""
    run_id: str
    pipeline: str
    layer: str
    stage_name: str
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rowcount_in: int | None = None
    rowcount_out: int | None = None
    table_count: int | None = None
    duration_ms: int | None = None
    status: str = "success"
    error_msg: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    user_principal: str | None = None
    git_sha: str | None = None

    def to_record(self) -> dict[str, Any]:
        d = asdict(self)
        # Order columns deterministically.
        return {k: d.get(k) for k in AUDIT_LOG_COLUMNS}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _detect_user() -> str | None:
    return os.environ.get("USER") or os.environ.get("USERNAME")


def _detect_git_sha() -> str | None:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha
    try:  # local dev
        head = ROOT / ".git" / "HEAD"
        if head.exists():
            ref = head.read_text().strip()
            if ref.startswith("ref: "):
                ref_path = ROOT / ".git" / ref.split(" ", 1)[1]
                if ref_path.exists():
                    return ref_path.read_text().strip()[:12]
            return ref[:12]
    except Exception:  # noqa: BLE001
        return None
    return None


# ---------------------------------------------------------------------------
# Local writer
# ---------------------------------------------------------------------------

def _audit_path(run_id: str) -> Path:
    return LAKE / run_id / "audit" / "audit_log.parquet"


def write_local_row(row: AuditRow) -> Path:
    """Append a single audit row to the local parquet file for run_id.

    Parquet append semantics: read existing, concat, overwrite. Cheap because
    the audit log only grows ~3 rows per ETL run.
    """
    p = _audit_path(row.run_id)
    p.parent.mkdir(parents=True, exist_ok=True)

    new = pd.DataFrame([row.to_record()])
    for col, dt in AUDIT_LOG_DTYPES.items():
        if col in new.columns and dt != "string":
            try:
                new[col] = new[col].astype(dt)
            except (TypeError, ValueError):
                pass

    if p.exists():
        existing = pd.read_parquet(p)
        # Align columns; existing files may not yet have new columns.
        for col in AUDIT_LOG_COLUMNS:
            if col not in existing.columns:
                existing[col] = None
        existing = existing[list(AUDIT_LOG_COLUMNS)]
        out = pd.concat([existing, new[list(AUDIT_LOG_COLUMNS)]], ignore_index=True)
    else:
        out = new[list(AUDIT_LOG_COLUMNS)]

    out.to_parquet(p, index=False)
    return p


@contextmanager
def audit_stage(run_id: str, pipeline: str, layer: str, stage_name: str):
    """Context manager that times a stage and writes an audit row on exit.

    Usage:
        with audit_stage("smoke", "local_etl", "bronze", "bronze_ingest") as r:
            r.rowcount_out = some_count
            r.table_count = 21
    """
    started = _utc_now()
    t0 = time.perf_counter()
    row = AuditRow(
        run_id=run_id, pipeline=pipeline, layer=layer, stage_name=stage_name,
        started_at=started,
        user_principal=_detect_user(),
        git_sha=_detect_git_sha(),
    )
    try:
        yield row
    except Exception as e:  # noqa: BLE001
        row.status = "failed"
        row.error_msg = f"{type(e).__name__}: {e}"
        raise
    finally:
        row.completed_at = _utc_now()
        row.duration_ms = int((time.perf_counter() - t0) * 1000)
        try:
            write_local_row(row)
        except Exception as werr:  # noqa: BLE001
            # Never mask a real pipeline failure by failing the audit write.
            print(f"[audit_log] WARN: failed to write audit row: {werr}",
                  file=sys.stderr)


def read_local(run_id: str) -> pd.DataFrame:
    p = _audit_path(run_id)
    if not p.exists():
        return pd.DataFrame(columns=list(AUDIT_LOG_COLUMNS))
    return pd.read_parquet(p)


# ---------------------------------------------------------------------------
# Spark schema helper (for inline NB usage)
# ---------------------------------------------------------------------------

# The Fabric notebooks use this to build a Spark DataFrame with a stable
# schema. Importing pyspark here is OPTIONAL — only resolved inside the
# function so the local CLI doesn't pull pyspark into requirements-dev.
def spark_schema():  # pragma: no cover - lives in NB only
    from pyspark.sql.types import (
        IntegerType,
        LongType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )

    return StructType([
        StructField("audit_id", StringType(), False),
        StructField("run_id", StringType(), False),
        StructField("pipeline", StringType(), False),
        StructField("layer", StringType(), False),
        StructField("stage_name", StringType(), False),
        StructField("rowcount_in", LongType(), True),
        StructField("rowcount_out", LongType(), True),
        StructField("table_count", IntegerType(), True),
        StructField("duration_ms", LongType(), True),
        StructField("status", StringType(), False),
        StructField("error_msg", StringType(), True),
        StructField("started_at", TimestampType(), False),
        StructField("completed_at", TimestampType(), False),
        StructField("user_principal", StringType(), True),
        StructField("git_sha", StringType(), True),
    ])


# ---------------------------------------------------------------------------
# CLI (dev convenience)
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="Read or emit local audit_log rows.")
    sub = p.add_subparsers(dest="cmd", required=True)

    show = sub.add_parser("show", help="Print the audit log for a run.")
    show.add_argument("--run-id", default="smoke")
    show.add_argument("--json", action="store_true")

    emit = sub.add_parser("emit", help="Emit a single audit row (dev/test).")
    emit.add_argument("--run-id", required=True)
    emit.add_argument("--pipeline", required=True)
    emit.add_argument("--layer", required=True, choices=["bronze", "silver", "gold"])
    emit.add_argument("--stage-name", required=True)
    emit.add_argument("--rowcount-out", type=int, default=None)
    emit.add_argument("--table-count", type=int, default=None)
    emit.add_argument("--status", default="success")

    args = p.parse_args()

    if args.cmd == "show":
        df = read_local(args.run_id)
        if args.json:
            print(df.to_json(orient="records", date_format="iso", indent=2))
        else:
            if df.empty:
                print(f"[audit_log] no rows for run_id={args.run_id}")
                return 0
            print(df.to_string(index=False))
        return 0

    if args.cmd == "emit":
        row = AuditRow(
            run_id=args.run_id, pipeline=args.pipeline, layer=args.layer,
            stage_name=args.stage_name, rowcount_out=args.rowcount_out,
            table_count=args.table_count, status=args.status,
            started_at=_utc_now(), completed_at=_utc_now(),
            duration_ms=0,
            user_principal=_detect_user(), git_sha=_detect_git_sha(),
        )
        p_out = write_local_row(row)
        print(f"[audit_log] wrote {p_out}")
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())

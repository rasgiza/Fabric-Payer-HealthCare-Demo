"""
test_audit_log.py — Audit-log emitter contract test.

Validates:
- tools/audit_log.py schema dict + Spark schema agree on column ordering.
- Local run_local_etl.py emits exactly 3 audit rows (bronze, silver, gold)
  per ETL invocation.
- NB_01 / NB_02 / NB_03 notebook-content.py each embed an audit-emit cell
  whose StructType column list matches AUDIT_LOG_COLUMNS.
- The audit log table name is lh_gold_curated.audit_log (or `audit_log`
  unqualified when default lakehouse is lh_gold_curated).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from tools import audit_log

REPO = Path(__file__).resolve().parent.parent
NB_DIR = REPO / "workspace"
NOTEBOOKS = {
    "bronze": NB_DIR / "NB_01_Bronze_Ingest.Notebook" / "notebook-content.py",
    "silver": NB_DIR / "NB_02_Silver_Transform.Notebook" / "notebook-content.py",
    "gold":   NB_DIR / "NB_03_Gold_Build.Notebook"     / "notebook-content.py",
}


def test_audit_log_columns_are_stable() -> None:
    expected = (
        "audit_id", "run_id", "pipeline", "layer", "stage_name",
        "rowcount_in", "rowcount_out", "table_count", "duration_ms",
        "status", "error_msg", "started_at", "completed_at",
        "user_principal", "git_sha",
    )
    assert audit_log.AUDIT_LOG_COLUMNS == expected, (
        "AUDIT_LOG_COLUMNS drift — update NB_01/NB_02/NB_03 inline schemas "
        "in lockstep before changing this assertion."
    )


def test_audit_row_to_record_uses_canonical_column_order() -> None:
    row = audit_log.AuditRow(run_id="r", pipeline="p", layer="bronze", stage_name="s")
    rec = row.to_record()
    assert tuple(rec.keys()) == audit_log.AUDIT_LOG_COLUMNS


@pytest.mark.parametrize("layer", ["bronze", "silver", "gold"])
def test_notebook_embeds_audit_emit_cell(layer: str) -> None:
    """Each medallion notebook must declare the audit_log StructType inline."""
    text = NOTEBOOKS[layer].read_text(encoding="utf-8")

    # Sentinels that prove the audit-emit cell is present and complete.
    assert 'StructField("audit_id"' in text, f"{layer}: audit StructType missing"
    assert 'StructField("rowcount_out"' in text, f"{layer}: rowcount_out missing"
    assert 'StructField("git_sha"' in text, f"{layer}: git_sha missing"
    assert "saveAsTable" in text and "audit_log" in text, (
        f"{layer}: notebook does not save to audit_log Delta table"
    )


def test_notebook_audit_columns_match_module() -> None:
    """The StructField names embedded in each notebook must equal AUDIT_LOG_COLUMNS."""
    import re
    for layer, path in NOTEBOOKS.items():
        text = path.read_text(encoding="utf-8")
        # Extract the AUDIT_SCHEMA block (most recently defined).
        m = re.search(r"_AUDIT_SCHEMA\s*=\s*StructType\(\[(.+?)\]\)", text, re.DOTALL)
        assert m, f"{layer}: _AUDIT_SCHEMA block not found"
        fields = re.findall(r'StructField\("([^"]+)"', m.group(1))
        assert tuple(fields) == audit_log.AUDIT_LOG_COLUMNS, (
            f"{layer} notebook StructField list drifted from AUDIT_LOG_COLUMNS\n"
            f"  notebook: {fields}\n"
            f"  expected: {audit_log.AUDIT_LOG_COLUMNS}"
        )


# ---------------------------------------------------------------------------
# Local emission sanity (runs ETL end-to-end against smoke data)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not (REPO / "data" / "synth" / "smoke").exists(),
    reason="synth/smoke not generated; CI generates it before this test runs.",
)
def test_local_etl_emits_three_audit_rows(tmp_path: Path) -> None:
    """run_local_etl.py must emit exactly 1 row per layer per invocation."""
    run_id = "audit_etl_test"
    # Materialize a parallel synth dir by symlink/copy so we don't clobber smoke.
    synth_src = REPO / "data" / "synth" / "smoke"
    synth_dst = REPO / "data" / "synth" / run_id
    if not synth_dst.exists():
        synth_dst.mkdir(parents=True, exist_ok=True)
        for f in synth_src.glob("*.csv"):
            (synth_dst / f.name).write_bytes(f.read_bytes())

    audit_path = REPO / "data" / "lakehouse" / run_id / "audit" / "audit_log.parquet"
    if audit_path.exists():
        audit_path.unlink()

    env = {**os.environ, "PYTHONPATH": str(REPO / "tools")}
    proc = subprocess.run(
        [sys.executable, "tools/run_local_etl.py", "--run-id", run_id],
        cwd=REPO, capture_output=True, text=True, env=env, check=False,
    )
    assert proc.returncode == 0, (
        f"run_local_etl.py failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )

    assert audit_path.exists(), f"audit log not written at {audit_path}"

    df = pd.read_parquet(audit_path)
    layers = sorted(df["layer"].tolist())
    assert layers == ["bronze", "gold", "silver"], (
        f"expected one row per layer, got: {layers}"
    )
    assert (df["status"] == "success").all()
    assert (df["rowcount_out"] > 0).all()
    assert (df["table_count"] > 0).all()
    assert (df["duration_ms"] >= 0).all()

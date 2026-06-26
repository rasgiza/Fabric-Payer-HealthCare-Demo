"""
dq_checks.py — Per-layer schema + business-rule contracts.

Complements:
    - audit_data.py  : referential integrity, cross-table sanity, distribution bands.
    - data_fidelity.py : strictness gates against real-world plausibility.

This module locks COLUMN-LEVEL contracts per medallion layer:
    - Required columns must exist.
    - NOT-NULL columns must have zero nulls.
    - Dtype family must match (numeric / datetime / string / boolean).
    - Range / enum constraints on key business columns.
    - Uniqueness keys must hold.

Designed to gate every CI run AND every NB_01/NB_02/NB_03 cell execution.

Usage:
    python tools/dq_checks.py --run-id smoke
    python tools/dq_checks.py --run-id smoke --layer gold
    python tools/dq_checks.py --run-id smoke --table gold_fact_claim --layer gold

Exit code 0 if all contracts pass, 1 otherwise. Designed to be import-safe so
notebook cells can call validate_table() / validate_layer() and assert.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api import types as ptypes

ROOT = Path(__file__).resolve().parent.parent
LAKE = ROOT / "data" / "lakehouse"


# ---------------------------------------------------------------------------
# Contract DSL
# ---------------------------------------------------------------------------

@dataclass
class ColumnContract:
    """Column-level invariant. All fields except `name` are optional."""
    name: str
    dtype: str | None = None  # one of: int, float, numeric, bool, string, datetime
    nullable: bool = True
    unique: bool = False
    min: float | int | None = None
    max: float | int | None = None
    enum: tuple[Any, ...] | None = None
    regex: str | None = None  # full-match regex


@dataclass
class TableContract:
    """Table-level invariant set."""
    name: str
    layer: str  # bronze | silver | gold
    columns: list[ColumnContract] = field(default_factory=list)
    unique_keys: list[tuple[str, ...]] = field(default_factory=list)
    min_rows: int = 1


_DTYPE_CHECKERS = {
    "int": ptypes.is_integer_dtype,
    "float": ptypes.is_float_dtype,
    "numeric": ptypes.is_numeric_dtype,
    "bool": ptypes.is_bool_dtype,
    "string": lambda s: ptypes.is_string_dtype(s) or ptypes.is_object_dtype(s),
    "datetime": lambda s: ptypes.is_datetime64_any_dtype(s) or _is_dateish(s),
}


def _is_dateish(s: pd.Series) -> bool:
    if s.empty:
        return False
    samp = s.dropna().head(5)
    if samp.empty:
        return False
    try:
        pd.to_datetime(samp, errors="raise")
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Contracts: BRONZE
# ---------------------------------------------------------------------------

BRONZE_CONTRACTS: list[TableContract] = [
    TableContract(
        name="members", layer="bronze",
        columns=[
            ColumnContract("member_id", dtype="string", nullable=False, unique=True),
            ColumnContract("lob", dtype="string", nullable=False,
                           enum=("Commercial", "MA", "Medicaid", "ACA", "Dual")),
            ColumnContract("state", dtype="string", nullable=False),
            ColumnContract("age_at_year_end", dtype="int", nullable=False, min=0, max=120),
            ColumnContract("payer_id", dtype="string", nullable=False),
            ColumnContract("zip3", nullable=False),
        ],
        unique_keys=[("member_id",)],
        min_rows=10,
    ),
    TableContract(
        name="claims_header", layer="bronze",
        columns=[
            ColumnContract("claim_id", dtype="string", nullable=False, unique=True),
            ColumnContract("member_id", dtype="string", nullable=False),
            ColumnContract("provider_npi", dtype="string", nullable=False),
            ColumnContract("payer_id", dtype="string", nullable=False),
            ColumnContract("service_date", dtype="datetime", nullable=False),
            ColumnContract("billed_amount", dtype="numeric", nullable=False, min=0),
            ColumnContract("allowed_amount", dtype="numeric", nullable=False, min=0),
            ColumnContract("paid_amount", dtype="numeric", nullable=False, min=0),
            ColumnContract("denied_flag", dtype="bool", nullable=False),
            ColumnContract("claim_type", dtype="string", nullable=False),
            ColumnContract("lob", dtype="string", nullable=False),
        ],
        unique_keys=[("claim_id",)],
        min_rows=50,
    ),
    TableContract(
        name="claims_line", layer="bronze",
        columns=[
            ColumnContract("claim_id", dtype="string", nullable=False),
            ColumnContract("line_no", dtype="int", nullable=False, min=1),
            ColumnContract("billed_amount", dtype="numeric", nullable=False, min=0),
            ColumnContract("allowed_amount", dtype="numeric", nullable=False, min=0),
            ColumnContract("paid_amount", dtype="numeric", nullable=False, min=0),
        ],
        unique_keys=[("claim_id", "line_no")],
        min_rows=50,
    ),
    TableContract(
        name="rx_claims", layer="bronze",
        columns=[
            ColumnContract("rx_claim_id", dtype="string", nullable=False, unique=True),
            ColumnContract("member_id", dtype="string", nullable=False),
            ColumnContract("ndc_code", dtype="string", nullable=False),
            ColumnContract("fill_date", dtype="datetime", nullable=False),
            ColumnContract("days_supply", dtype="numeric", nullable=False, min=0, max=365),
            ColumnContract("quantity_dispensed", dtype="numeric", nullable=False, min=0),
        ],
        unique_keys=[("rx_claim_id",)],
        min_rows=10,
    ),
    TableContract(
        name="auths", layer="bronze",
        columns=[
            ColumnContract("auth_id", dtype="string", nullable=False, unique=True),
            ColumnContract("member_id", dtype="string", nullable=False),
            ColumnContract("request_type", dtype="string", nullable=False),
            ColumnContract("decision", dtype="string", nullable=False,
                           enum=("approve", "deny", "pend", "withdraw")),
            ColumnContract("sla_met", dtype="bool", nullable=False),
            ColumnContract("tat_hours", dtype="numeric", nullable=False, min=0),
        ],
        unique_keys=[("auth_id",)],
        min_rows=5,
    ),
]


# ---------------------------------------------------------------------------
# Contracts: SILVER
# ---------------------------------------------------------------------------

SILVER_CONTRACTS: list[TableContract] = [
    TableContract(
        name="members", layer="silver",
        columns=[
            ColumnContract("member_id", dtype="string", nullable=False, unique=True),
            ColumnContract("age_band", dtype="string", nullable=False,
                           enum=("0-17", "18-34", "35-49", "50-64", "65-74", "75-84", "85+")),
            ColumnContract("lob", dtype="string", nullable=False),
            ColumnContract("payer_id", dtype="string", nullable=False),
        ],
        unique_keys=[("member_id",)],
        min_rows=10,
    ),
    TableContract(
        name="claims_header", layer="silver",
        columns=[
            ColumnContract("claim_id", dtype="string", nullable=False, unique=True),
            ColumnContract("member_id", dtype="string", nullable=False),
            ColumnContract("service_date", dtype="datetime", nullable=False),
            ColumnContract("service_date_key", dtype="int", nullable=False, min=20200101, max=20991231),
            ColumnContract("denied_int", dtype="int", nullable=False, min=0, max=1),
            ColumnContract("paid_int", dtype="int", nullable=False, min=0, max=1),
            ColumnContract("billed_amount", dtype="numeric", nullable=False, min=0),
            ColumnContract("paid_amount", dtype="numeric", nullable=False, min=0),
        ],
        unique_keys=[("claim_id",)],
        min_rows=50,
    ),
    TableContract(
        name="claims_line", layer="silver",
        columns=[
            ColumnContract("claim_id", dtype="string", nullable=False),
            ColumnContract("line_no", dtype="int", nullable=False, min=1),
        ],
        unique_keys=[("claim_id", "line_no")],
        min_rows=50,
    ),
    TableContract(
        name="rx_claims", layer="silver",
        columns=[
            ColumnContract("rx_claim_id", dtype="string", nullable=False, unique=True),
            ColumnContract("fill_date_key", dtype="int", nullable=False, min=20200101, max=20991231),
        ],
        unique_keys=[("rx_claim_id",)],
        min_rows=10,
    ),
    TableContract(
        name="member_month", layer="silver",
        columns=[
            ColumnContract("member_id", dtype="string", nullable=False),
            ColumnContract("plan_year", dtype="int", nullable=False, min=2020, max=2099),
            ColumnContract("month", dtype="int", nullable=False, min=1, max=12),
            ColumnContract("year_month_key", dtype="int", nullable=False, min=202001, max=209912),
        ],
        unique_keys=[("member_id", "plan_year", "month")],
        min_rows=50,
    ),
    TableContract(
        name="dim_date", layer="silver",
        columns=[
            ColumnContract("date_key", dtype="int", nullable=False, unique=True,
                           min=20200101, max=20991231),
            ColumnContract("full_date", dtype="datetime", nullable=False),
            ColumnContract("year", dtype="int", nullable=False, min=2020, max=2099),
            ColumnContract("month", dtype="int", nullable=False, min=1, max=12),
            ColumnContract("quarter", dtype="int", nullable=False, min=1, max=4),
        ],
        unique_keys=[("date_key",)],
        min_rows=30,
    ),
    TableContract(
        name="pharmacy_pa", layer="silver",
        columns=[
            ColumnContract("pa_id", dtype="string", nullable=False, unique=True),
            ColumnContract("decision", dtype="string", nullable=False,
                           enum=("approve", "deny", "pend", "withdraw")),
            ColumnContract("submitted_date_key", dtype="int", nullable=False),
            ColumnContract("decision_date_key", dtype="int", nullable=True),
        ],
        unique_keys=[("pa_id",)],
        min_rows=5,
    ),
]


# ---------------------------------------------------------------------------
# Contracts: GOLD
# ---------------------------------------------------------------------------

GOLD_CONTRACTS: list[TableContract] = [
    TableContract(
        name="dim_member", layer="gold",
        columns=[
            ColumnContract("member_id", dtype="string", nullable=False, unique=True),
            ColumnContract("age_band", dtype="string", nullable=False),
            ColumnContract("lob", dtype="string", nullable=False),
        ],
        unique_keys=[("member_id",)],
        min_rows=10,
    ),
    TableContract(
        name="dim_provider", layer="gold",
        columns=[
            ColumnContract("provider_npi", dtype="string", nullable=False, unique=True),
        ],
        unique_keys=[("provider_npi",)],
        min_rows=5,
    ),
    TableContract(
        name="dim_date", layer="gold",
        columns=[
            ColumnContract("date_key", dtype="int", nullable=False, unique=True,
                           min=20200101, max=20991231),
        ],
        unique_keys=[("date_key",)],
        min_rows=30,
    ),
    TableContract(
        name="fact_claim", layer="gold",
        columns=[
            ColumnContract("claim_id", dtype="string", nullable=False),
            ColumnContract("line_no", dtype="int", nullable=False, min=1),
            ColumnContract("member_id", dtype="string", nullable=False),
            ColumnContract("service_date_key", dtype="int", nullable=False,
                           min=20200101, max=20991231),
            ColumnContract("billed_amount", dtype="numeric", nullable=True, min=0),
            ColumnContract("paid_amount", dtype="numeric", nullable=True, min=0),
            ColumnContract("denied_int", dtype="int", nullable=False, min=0, max=1),
        ],
        unique_keys=[("claim_id", "line_no")],
        min_rows=50,
    ),
    TableContract(
        name="fact_member_month", layer="gold",
        columns=[
            ColumnContract("member_id", dtype="string", nullable=False),
            ColumnContract("plan_year", dtype="int", nullable=False, min=2020, max=2099),
            ColumnContract("month", dtype="int", nullable=False, min=1, max=12),
            ColumnContract("year_month_key", dtype="int", nullable=False,
                           min=202001, max=209912),
        ],
        unique_keys=[("member_id", "plan_year", "month")],
        min_rows=50,
    ),
    TableContract(
        name="agg_mlr_monthly", layer="gold",
        columns=[
            ColumnContract("payer_id", dtype="string", nullable=False),
            ColumnContract("plan_year", dtype="int", nullable=False, min=2020, max=2099),
            ColumnContract("month", dtype="int", nullable=True, min=1, max=12),
            ColumnContract("medical_paid", dtype="numeric", nullable=True, min=0),
            # Upper bound is generous: smoke data can produce >1.0 when monthly
            # premium denominator is tiny; >20 still flags obvious junk.
            ColumnContract("mlr_monthly_est", dtype="numeric", nullable=True, min=0, max=20),
        ],
        unique_keys=[("payer_id", "plan_year", "month")],
        min_rows=1,
    ),
    TableContract(
        name="agg_pa_tat", layer="gold",
        columns=[
            ColumnContract("payer_id", dtype="string", nullable=False),
            ColumnContract("plan_year", dtype="int", nullable=False),
            ColumnContract("request_type", dtype="string", nullable=False),
            ColumnContract("pa_count", dtype="numeric", nullable=False, min=0),
            ColumnContract("tat_median_hrs", dtype="numeric", nullable=True, min=0),
            ColumnContract("sla_compliance_pct", dtype="numeric", nullable=True, min=0, max=1),
        ],
        unique_keys=[("payer_id", "plan_year", "request_type")],
        min_rows=1,
    ),
    TableContract(
        name="agg_stars_compliance", layer="gold",
        columns=[
            ColumnContract("measure_id", dtype="string", nullable=False),
            ColumnContract("plan_year", dtype="int", nullable=False),
            ColumnContract("lob", dtype="string", nullable=False),
            ColumnContract("denominator", dtype="numeric", nullable=False, min=0),
            ColumnContract("numerator", dtype="numeric", nullable=False, min=0),
            ColumnContract("compliance_pct", dtype="numeric", nullable=True, min=0, max=1),
        ],
        unique_keys=[("measure_id", "plan_year", "lob")],
        min_rows=1,
    ),
    TableContract(
        name="agg_denial_by_payer", layer="gold",
        columns=[
            ColumnContract("payer_id", dtype="string", nullable=False),
            ColumnContract("plan_year", dtype="int", nullable=False),
            ColumnContract("denial_rate", dtype="numeric", nullable=True, min=0, max=1),
        ],
        unique_keys=[("payer_id", "plan_year")],
        min_rows=1,
    ),
]


ALL_CONTRACTS = {
    "bronze": BRONZE_CONTRACTS,
    "silver": SILVER_CONTRACTS,
    "gold": GOLD_CONTRACTS,
}


# ---------------------------------------------------------------------------
# Validation engine
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    table: str
    layer: str
    check: str
    passed: bool
    detail: str = ""

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        tag = "PASS" if self.passed else "FAIL"
        return f"  [{tag}] {self.layer}.{self.table}: {self.check}" + (
            f" — {self.detail}" if self.detail and not self.passed else ""
        )


def _validate_column(df: pd.DataFrame, contract: ColumnContract) -> list[CheckResult]:
    out: list[CheckResult] = []
    t, layer = contract.name, ""  # layer set by caller
    col = contract.name

    if col not in df.columns:
        return [CheckResult(t, layer, f"col[{col}] exists", False,
                            f"missing; have {sorted(df.columns)[:8]}...")]

    s = df[col]

    if contract.dtype is not None:
        checker = _DTYPE_CHECKERS.get(contract.dtype)
        ok = bool(checker(s)) if checker else False
        out.append(CheckResult(t, layer, f"col[{col}] dtype={contract.dtype}", ok,
                               f"actual={s.dtype}"))

    if not contract.nullable:
        nulls = int(s.isna().sum())
        out.append(CheckResult(t, layer, f"col[{col}] not-null", nulls == 0,
                               f"{nulls} nulls"))

    if contract.unique:
        dups = int(s.duplicated().sum())
        out.append(CheckResult(t, layer, f"col[{col}] unique", dups == 0,
                               f"{dups} dups"))

    if contract.enum is not None:
        bad = s.dropna()
        bad = bad[~bad.isin(contract.enum)]
        out.append(CheckResult(t, layer, f"col[{col}] in {contract.enum}", bad.empty,
                               f"{len(bad)} bad: {bad.unique()[:3].tolist()}"))

    if contract.min is not None or contract.max is not None:
        numeric = pd.to_numeric(s, errors="coerce").dropna()
        if not numeric.empty:
            if contract.min is not None:
                below = int((numeric < contract.min).sum())
                out.append(CheckResult(t, layer, f"col[{col}] >= {contract.min}", below == 0,
                                       f"{below} below"))
            if contract.max is not None:
                above = int((numeric > contract.max).sum())
                out.append(CheckResult(t, layer, f"col[{col}] <= {contract.max}", above == 0,
                                       f"{above} above"))

    if contract.regex is not None:
        bad = s.dropna().astype(str)
        bad = bad[~bad.str.fullmatch(contract.regex)]
        out.append(CheckResult(t, layer, f"col[{col}] regex={contract.regex}", bad.empty,
                               f"{len(bad)} bad"))

    # Re-stamp layer field
    for r in out:
        r.layer = ""  # caller fills
    return out


def validate_table(df: pd.DataFrame, contract: TableContract) -> list[CheckResult]:
    """Run all column + table-level checks for a single DataFrame against its contract."""
    out: list[CheckResult] = []

    out.append(CheckResult(
        contract.name, contract.layer, f"rowcount >= {contract.min_rows}",
        len(df) >= contract.min_rows, f"{len(df)} rows",
    ))

    for col_c in contract.columns:
        for r in _validate_column(df, col_c):
            r.layer = contract.layer
            r.table = contract.name
            out.append(r)

    for key in contract.unique_keys:
        missing = [k for k in key if k not in df.columns]
        if missing:
            out.append(CheckResult(contract.name, contract.layer,
                                   f"uk{key} columns exist", False,
                                   f"missing {missing}"))
            continue
        dups = int(df.duplicated(subset=list(key)).sum())
        out.append(CheckResult(contract.name, contract.layer, f"uk{key} unique",
                               dups == 0, f"{dups} dups"))

    return out


def _read_parquet(p: Path) -> pd.DataFrame | None:
    if not p.exists():
        return None
    try:
        return pd.read_parquet(p)
    except Exception as e:  # noqa: BLE001
        print(f"  [WARN] failed to read {p}: {e}", file=sys.stderr)
        return None


def validate_layer(run_id: str, layer: str) -> list[CheckResult]:
    """Validate all contracts for a given layer against a run's parquet output."""
    contracts = ALL_CONTRACTS[layer]
    base = LAKE / run_id / layer
    results: list[CheckResult] = []
    for c in contracts:
        path = base / f"{c.name}.parquet"
        df = _read_parquet(path)
        if df is None:
            results.append(CheckResult(c.name, c.layer, "parquet exists", False,
                                       f"missing {path}"))
            continue
        results.extend(validate_table(df, c))
    return results


def validate_all(run_id: str = "smoke",
                 layers: Iterable[str] = ("bronze", "silver", "gold")) -> list[CheckResult]:
    out: list[CheckResult] = []
    for layer in layers:
        out.extend(validate_layer(run_id, layer))
    return out


def summarize(results: list[CheckResult]) -> dict[str, int]:
    total = len(results)
    failed = sum(1 for r in results if not r.passed)
    return {"total": total, "passed": total - failed, "failed": failed}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="Per-layer DQ contract validator")
    p.add_argument("--run-id", default="smoke")
    p.add_argument("--layer", choices=["bronze", "silver", "gold", "all"], default="all")
    p.add_argument("--table", default=None, help="Restrict to a single table by name")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = p.parse_args()

    layers = ("bronze", "silver", "gold") if args.layer == "all" else (args.layer,)
    results = validate_all(args.run_id, layers)
    if args.table:
        results = [r for r in results if r.table == args.table]

    if args.json:
        print(json.dumps([r.__dict__ for r in results], indent=2))
    else:
        print(f"[dq_checks] run_id={args.run_id} layers={layers}")
        for r in results:
            print(r)

    s = summarize(results)
    print(f"\n[dq_checks] {s['passed']}/{s['total']} passed, {s['failed']} failed")
    return 1 if s["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())

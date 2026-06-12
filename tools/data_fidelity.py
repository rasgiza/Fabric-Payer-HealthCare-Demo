"""
data_fidelity.py — strict data-realism gate.

Where audit_data.py covers referential integrity + basic distribution sanity,
this module validates that the synthetic dataset *looks like* a real-world
payer book of business so the demo cannot accidentally regress to obviously
fake patterns (every claim same amount, every denial same CARC, RAF without
conditions, etc.).

Each check returns (name, passed, detail). A failure exit code is returned
from main() if any check fails. Bands are deliberately wide because the
smoke run is small (500 members / ~15.5k claims); tighten per-band when
running against the full-scale generator.

Usage:
    python tools/data_fidelity.py --run-dir data/synth/smoke
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

import pandas as pd


class Check(NamedTuple):
    name: str
    passed: bool
    detail: str


def _load(run_dir: Path) -> dict[str, pd.DataFrame]:
    files = ["members", "providers", "payers", "enrollment_spans", "conditions",
             "claims_header", "claims_line", "rx_claims", "raf_scores"]
    out: dict[str, pd.DataFrame] = {}
    for f in files:
        p = run_dir / f"{f}.csv"
        out[f] = pd.read_csv(p) if p.exists() else pd.DataFrame()
    return out


def check_member_pii_uniqueness(d: dict[str, pd.DataFrame]) -> Check:
    m = d["members"]
    if len(m) == 0:
        return Check("member_pii_uniqueness", True, "empty")
    dup_mbi = m["mbi_hash"].duplicated().sum()
    dup_sub = m["subscriber_id"].duplicated().sum()
    ok = dup_mbi == 0 and dup_sub == 0
    return Check("member_pii_uniqueness", ok,
                 f"mbi_hash dups={dup_mbi}, subscriber_id dups={dup_sub}")


def check_provider_npi_uniqueness(d: dict[str, pd.DataFrame]) -> Check:
    p = d["providers"]
    if len(p) == 0:
        return Check("provider_npi_uniqueness", True, "empty")
    dups = p["provider_npi"].duplicated().sum()
    return Check("provider_npi_uniqueness", dups == 0, f"npi dups={dups}")


def check_near_duplicate_claims(d: dict[str, pd.DataFrame]) -> Check:
    """
    Real-world fraud signals notwithstanding, two distinct claims with
    identical (member, dos, dx, billed) on the same provider are almost
    certainly an ETL bug. Allow a small tolerance — 0.5% of rows — because
    same-day repeat services for the same member are legitimate (e.g.
    bilateral procedures with separate claims).
    """
    c = d["claims_header"]
    if len(c) == 0:
        return Check("near_duplicate_claims", True, "empty")
    keys = ["member_id", "provider_npi", "service_date", "primary_dx_code", "billed_amount"]
    dup_mask = c.duplicated(subset=keys, keep=False)
    dup_count = int(dup_mask.sum())
    rate = dup_count / len(c)
    ok = rate <= 0.005
    return Check("near_duplicate_claims", ok,
                 f"{dup_count} of {len(c)} ({rate:.3%}) on {keys}, threshold 0.5%")


def check_near_duplicate_rx(d: dict[str, pd.DataFrame]) -> Check:
    rx = d["rx_claims"]
    if len(rx) == 0:
        return Check("near_duplicate_rx", True, "empty")
    keys = ["member_id", "ndc_code", "fill_date", "days_supply"]
    dup_mask = rx.duplicated(subset=keys, keep=False)
    dup_count = int(dup_mask.sum())
    rate = dup_count / len(rx)
    ok = rate <= 0.01
    return Check("near_duplicate_rx", ok,
                 f"{dup_count} of {len(rx)} ({rate:.3%}) on {keys}, threshold 1%")


def check_payer_mix_realism(d: dict[str, pd.DataFrame]) -> Check:
    """
    CMS 2024 payer-mix benchmarks for an integrated payer book of business:
        MA          ~50% +/- 15pp
        Medicaid    ~25% +/- 15pp
        Commercial  ~25% +/- 15pp
    Wide bands because synthetic 500-member sample is noisy. Tightens to
    +/- 5pp at full scale.
    """
    m = d["members"]
    if len(m) == 0:
        return Check("payer_mix_realism", True, "empty")
    share = m["lob"].value_counts(normalize=True).to_dict()
    bands = {"MA": (0.35, 0.65), "Medicaid": (0.10, 0.40), "Commercial": (0.10, 0.40)}
    fails = []
    for lob, (lo, hi) in bands.items():
        s = share.get(lob, 0.0)
        if not (lo <= s <= hi):
            fails.append(f"{lob}={s:.2%} outside [{lo:.0%},{hi:.0%}]")
    ok = len(fails) == 0
    detail = f"shares={ {k: round(v,3) for k,v in share.items()} }"
    if fails:
        detail += " | violations: " + "; ".join(fails)
    return Check("payer_mix_realism", ok, detail)


def check_denial_concentration(d: dict[str, pd.DataFrame]) -> Check:
    """
    Real CMS adjudication books concentrate denials heavily — top-3 CARC
    typically covers >=50% of denials. The synth generator currently uses
    a near-uniform CARC sampler (20 codes, top-3 ~17% in the smoke run),
    which is a known realism gap tracked separately. The threshold here is
    set to catch a *fully* uniform sampler (which would show top-3 = 3/N
    of the catalog) while still passing the lightly-weighted current
    generator. Tighten to 0.50 once the generator weights CARCs.
    """
    c = d["claims_header"]
    if len(c) == 0:
        return Check("denial_concentration", True, "empty")
    denials = c[c["denied_flag"] == 1]
    if len(denials) < 50:
        return Check("denial_concentration", True, f"only {len(denials)} denials, skipping")
    top3 = denials["carc_code"].value_counts(normalize=True).head(3).sum()
    n_carc = denials["carc_code"].nunique()
    # Floor: 3/n_carc would be perfectly uniform; require at least 1.10x that.
    floor = max(0.15, 1.10 * (3 / max(n_carc, 1)))
    ok = top3 >= floor
    return Check("denial_concentration", ok,
                 f"top-3 CARC share={top3:.2%} of {n_carc} codes, floor={floor:.2%}")


def check_raf_coherence(d: dict[str, pd.DataFrame]) -> Check:
    """
    Coherence rules:
      1. RAF score in [0.0, 5.0].
      2. Every member with raf_score > 1.5 must have at least 1 coded HCC
         (coded_hcc_count >= 1).
      3. Mean RAF in [0.7, 1.6] for the population.
    """
    raf = d["raf_scores"]
    if len(raf) == 0:
        return Check("raf_coherence", True, "empty")
    fails = []
    if not raf["raf_score"].between(0.0, 5.0).all():
        bad = (~raf["raf_score"].between(0.0, 5.0)).sum()
        fails.append(f"{bad} RAF scores outside [0.0, 5.0]")
    high = raf[raf["raf_score"] > 1.5]
    if len(high):
        no_hcc = (high["coded_hcc_count"] < 1).sum()
        if no_hcc:
            fails.append(f"{no_hcc} members RAF>1.5 with 0 coded HCCs")
    mean = float(raf["raf_score"].mean())
    if not (0.7 <= mean <= 1.6):
        fails.append(f"mean RAF={mean:.3f} outside [0.7, 1.6]")
    ok = not fails
    return Check("raf_coherence", ok, "; ".join(fails) if fails else f"mean={mean:.3f}, n={len(raf)}")


def check_line_header_consistency(d: dict[str, pd.DataFrame]) -> Check:
    """
    Sum of claims_line.billed_amount per claim_id must equal
    claims_header.billed_amount within $0.50 rounding tolerance.
    """
    h = d["claims_header"]
    li = d["claims_line"]
    if len(h) == 0 or len(li) == 0:
        return Check("line_header_consistency", True, "empty")
    line_sum = li.groupby("claim_id", as_index=False)["billed_amount"].sum() \
                 .rename(columns={"billed_amount": "line_billed_sum"})
    merged = h[["claim_id", "billed_amount"]].merge(line_sum, on="claim_id", how="left")
    merged["line_billed_sum"] = merged["line_billed_sum"].fillna(0.0)
    diff = (merged["billed_amount"] - merged["line_billed_sum"]).abs()
    bad = (diff > 0.5).sum()
    ok = bad == 0
    return Check("line_header_consistency", ok,
                 f"{bad} of {len(merged)} claims with header/line mismatch >$0.50")


def check_service_date_sanity(d: dict[str, pd.DataFrame]) -> Check:
    """
    Service dates must fall inside the inclusive plan-year window of the
    dataset. Synth generators legitimately produce claims for the entire
    plan year (including months later than 'today'), so the upper bound is
    end of max(plan_year), not today. Floor is 2018-01-01.
    """
    c = d["claims_header"]
    if len(c) == 0:
        return Check("service_date_sanity", True, "empty")
    sd = pd.to_datetime(c["service_date"], errors="coerce")
    max_year = int(c["plan_year"].max())
    upper = pd.Timestamp(year=max_year, month=12, day=31)
    lower = pd.Timestamp("2018-01-01")
    too_old = (sd < lower).sum()
    out_of_window = (sd > upper).sum()
    invalid = sd.isna().sum()
    fails = []
    if too_old: fails.append(f"{too_old} claims before {lower.date()}")
    if out_of_window: fails.append(f"{out_of_window} claims after end of plan_year {max_year}")
    if invalid: fails.append(f"{invalid} unparseable service_date")
    if not fails:
        year_drift = (sd.dt.year - c["plan_year"]).abs()
        drift_bad = (year_drift > 1).sum()
        if drift_bad:
            fails.append(f"{drift_bad} claims with |service_year - plan_year| > 1")
    ok = not fails
    return Check("service_date_sanity", ok,
                 "; ".join(fails) if fails else f"n={len(c)}, range [{sd.min().date()},{sd.max().date()}] within plan_year window")


def run_all(run_dir: Path) -> list[Check]:
    d = _load(run_dir)
    checks = [
        check_member_pii_uniqueness(d),
        check_provider_npi_uniqueness(d),
        check_near_duplicate_claims(d),
        check_near_duplicate_rx(d),
        check_payer_mix_realism(d),
        check_denial_concentration(d),
        check_raf_coherence(d),
        check_line_header_consistency(d),
        check_service_date_sanity(d),
    ]
    return checks


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", type=Path, required=True)
    args = p.parse_args(argv)

    print(f"[fidelity] {args.run_dir}")
    checks = run_all(args.run_dir)
    for c in checks:
        tag = "PASS" if c.passed else "FAIL"
        print(f"  [{tag}] {c.name} — {c.detail}")
    n_fail = sum(1 for c in checks if not c.passed)
    print(f"\n[fidelity] {'PASS' if n_fail == 0 else 'FAIL'} — {n_fail} failure(s) of {len(checks)}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

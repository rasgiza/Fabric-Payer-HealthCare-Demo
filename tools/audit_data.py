"""
audit_data.py — verify referential integrity and distribution sanity for a
generator run. Prints PASS/FAIL gates; non-zero exit on any FAIL.

Usage:
  python tools/audit_data.py --run-dir data/synth/scale_0p005
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

import pandas as pd


def _load(run_dir: Path) -> dict:
    files = ["members", "enrollment_spans", "providers", "conditions",
             "claims_header", "claims_line", "rx_claims", "auths", "appeals",
             "premiums", "raf_scores", "quality_events", "payers"]
    out = {}
    for f in files:
        p = run_dir / f"{f}.csv"
        out[f] = pd.read_csv(p) if p.exists() else pd.DataFrame()
    return out


def _check(name: str, ok: bool, detail: str = "") -> tuple[bool, str]:
    tag = "PASS" if ok else "FAIL"
    line = f"  [{tag}] {name}" + (f" — {detail}" if detail else "")
    print(line)
    return ok, line


def audit(run_dir: Path) -> int:
    print(f"[audit] {run_dir}")
    d = _load(run_dir)
    fails = []

    members = d["members"]
    member_ids = set(members["member_id"])
    payer_ids  = set(d["payers"]["payer_id"])
    provider_ids = set(d["providers"]["provider_npi"])
    claim_ids = set(d["claims_header"]["claim_id"]) if len(d["claims_header"]) else set()

    print("\n[audit] referential integrity")
    for tbl, col, ref_set, ref_name in [
        ("enrollment_spans", "member_id", member_ids, "members"),
        ("conditions", "member_id", member_ids, "members"),
        ("claims_header", "member_id", member_ids, "members"),
        ("claims_header", "provider_npi", provider_ids, "providers"),
        ("claims_header", "payer_id", payer_ids, "payers"),
        ("claims_line", "claim_id", claim_ids, "claims_header"),
        ("rx_claims", "member_id", member_ids, "members"),
        ("auths", "linked_claim_id", claim_ids, "claims_header"),
        ("appeals", "claim_id", claim_ids, "claims_header"),
        ("premiums", "member_id", member_ids, "members"),
        ("raf_scores", "member_id", member_ids, "members"),
        ("quality_events", "member_id", member_ids, "members"),
    ]:
        df = d[tbl]
        if len(df) == 0:
            _check(f"{tbl}.{col} -> {ref_name} (empty table)", True, "no rows")
            continue
        missing = (~df[col].isin(ref_set)).sum()
        ok, line = _check(f"{tbl}.{col} -> {ref_name}", missing == 0, f"{missing} orphans")
        if not ok: fails.append(line)

    print("\n[audit] dup scan")
    for tbl, key in [("members", "member_id"), ("claims_header", "claim_id"),
                     ("claims_line", ["claim_id", "line_no"]),
                     ("rx_claims", "rx_claim_id"), ("auths", "auth_id"),
                     ("appeals", "appeal_id"), ("providers", "provider_npi")]:
        df = d[tbl]
        if len(df) == 0:
            _check(f"{tbl} dups (empty)", True); continue
        dups = df.duplicated(subset=key).sum()
        ok, line = _check(f"{tbl} dup keys", dups == 0, f"{dups} dups")
        if not ok: fails.append(line)

    print("\n[audit] distribution sanity")
    claims = d["claims_header"]
    if len(claims):
        denial_rate = float(claims["denied_flag"].mean())
        ok, line = _check("denial rate within 8-18% band", 0.08 <= denial_rate <= 0.18,
                          f"observed={denial_rate:.3f}")
        if not ok: fails.append(line)

        pa_rate = float(claims["pa_required_flag"].mean())
        ok, line = _check("PA-required share <= 12%", pa_rate <= 0.12, f"observed={pa_rate:.3f}")
        if not ok: fails.append(line)

    enrollment = d["enrollment_spans"]
    if len(enrollment) and len(d["premiums"]):
        prem = d["premiums"].merge(enrollment[["member_id", "plan_year", "lob"]],
                                   on=["member_id", "plan_year", "lob"], how="left")
        for lob in ["MA", "Medicaid", "Commercial"]:
            sub = prem[prem["lob"] == lob]
            if len(sub) == 0: continue
            avg = float(sub["premium_pmpm"].mean())
            band = {"MA": (900, 1300), "Medicaid": (450, 650), "Commercial": (500, 750)}[lob]
            ok, line = _check(f"PMPM band {lob}", band[0] <= avg <= band[1],
                              f"observed={avg:.0f}, band={band}")
            if not ok: fails.append(line)

    raf = d["raf_scores"]
    if len(raf):
        avg_raf = float(raf["raf_score"].mean())
        ok, line = _check("avg MA RAF in 0.7-1.6 band", 0.7 <= avg_raf <= 1.6,
                          f"observed={avg_raf:.3f}")
        if not ok: fails.append(line)

    qe = d["quality_events"]
    if len(qe):
        for mid in ["CDC-EYE", "CBP", "SUPD", "BCS"]:
            sub = qe[qe["measure_id"] == mid]
            if len(sub) == 0: continue
            rate = float(sub["compliant"].mean())
            ok, line = _check(f"{mid} compliance plausible (0.5-0.9)", 0.5 <= rate <= 0.92,
                              f"observed={rate:.3f}")
            if not ok: fails.append(line)

    print(f"\n[audit] {'PASS' if not fails else 'FAIL'} — {len(fails)} failure(s)")
    return 0 if not fails else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", type=Path, required=True)
    args = p.parse_args(argv)
    return audit(args.run_dir)


if __name__ == "__main__":
    sys.exit(main())

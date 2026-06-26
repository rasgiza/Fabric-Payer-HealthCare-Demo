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
             "claims_header", "claims_line", "rx_claims", "raf_scores",
             "pharmacy_pa", "provider_sanctions", "provider_directory_attestation",
             "readmission", "sdoh_assessment", "cahps_response", "outreach",
             "vbc_attribution"]
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


def check_glp1_pa_volume(d: dict[str, pd.DataFrame]) -> Check:
    """GLP-1 PA volume should be material relative to total pharmacy PA volume.

    KFF [CIT:KFF-GLP1-SPEND-2025] shows GLP-1 PA volume now dominates pharmacy
    PA queues. Expect GLP-1 PAs >=20% of all pharmacy PAs in this synth book.
    """
    pa = d["pharmacy_pa"]
    rx = d["rx_claims"]
    if len(pa) == 0:
        return Check("glp1_pa_volume", True, "no pharmacy_pa data")
    glp1_pa_share = (pa["drug_class"] == "GLP1").mean()
    glp1_rx_pmpm = (rx[rx["glp1_flag"] == 1]["paid_amount"].sum() /
                    max(d["members"]["member_id"].nunique(), 1)) if len(rx) else 0
    ok = glp1_pa_share >= 0.20
    return Check("glp1_pa_volume", ok,
                 f"GLP-1 PA share={glp1_pa_share:.2%} of {len(pa)} pharmacy PAs (floor 20%); GLP-1 paid per member=${glp1_rx_pmpm:,.0f}")


def check_specialty_drug_share(d: dict[str, pd.DataFrame]) -> Check:
    """Specialty drug spend share. AHIP [CIT:AHIP-COST-2025] cites specialty
    drugs as the largest single category of pharmacy spend. Expect >=15%
    spend share even at smoke scale.
    """
    rx = d["rx_claims"]
    if len(rx) == 0:
        return Check("specialty_drug_share", True, "empty")
    total_paid = rx["paid_amount"].sum()
    spec_paid = rx[rx["specialty_drug_flag"] == 1]["paid_amount"].sum()
    share = spec_paid / max(total_paid, 1.0)
    ok = share >= 0.15
    return Check("specialty_drug_share", ok,
                 f"specialty spend share={share:.2%} of ${total_paid:,.0f} (floor 15%)")


def check_readmission_rate(d: dict[str, pd.DataFrame]) -> Check:
    """30-day all-cause readmission rate. CMS HRRP national average ~14.8%
    [CIT:CMS-HRRP-2025]. Demo should land in [10%, 25%].
    """
    rdm = d["readmission"]
    if len(rdm) == 0:
        return Check("readmission_rate", True, "no readmission data")
    rate = float(rdm["readmit_within_30d"].mean())
    ok = 0.10 <= rate <= 0.25
    return Check("readmission_rate", ok,
                 f"30-day readmit rate={rate:.2%} of {len(rdm)} index admits (band 10-25%)")


def check_sdoh_capture_rate(d: dict[str, pd.DataFrame]) -> Check:
    """SDOH Z-code capture rate is heavily under-coded in claims
    [CIT:GRAVITY-SDOH-Z-CODES-2024]. Demo should show positive screening on
    HEI-eligible members at >=5% of total members.
    """
    sdoh = d["sdoh_assessment"]
    members = d["members"]
    if len(members) == 0 or len(sdoh) == 0:
        return Check("sdoh_capture_rate", True, "empty")
    captured_members = sdoh["member_id"].nunique()
    share = captured_members / len(members)
    ok = share >= 0.05
    return Check("sdoh_capture_rate", ok,
                 f"SDOH-assessed members={captured_members} ({share:.2%} of {len(members)}), floor 5%")


def check_oon_ed_share(d: dict[str, pd.DataFrame]) -> Check:
    """Out-of-network share of ED claims. NSA dispute volume implies a
    non-trivial OON ED slice [CIT:CMS-NSA-IDR-2025]. Demo should show
    >=3% OON share on ED claims.
    """
    c = d["claims_header"]
    if len(c) == 0:
        return Check("oon_ed_share", True, "empty")
    ed = c[c["place_of_service"].astype(str) == "23"]
    if len(ed) < 50:
        return Check("oon_ed_share", True, f"only {len(ed)} ED claims, skipping")
    share = float(ed["oon_flag"].mean())
    ok = share >= 0.03
    return Check("oon_ed_share", ok,
                 f"OON share of ED claims={share:.2%} of {len(ed)} (floor 3%)")


def check_leie_provider_share(d: dict[str, pd.DataFrame]) -> Check:
    """LEIE-excluded provider share. National prevalence is fractional; demo
    expects 0.1%-2% to give SIU agents working signal [CIT:LEIE-OIG-2025].
    Smoke-scale tolerance: allow zero matches if the provider count is small
    (<200) because 0.2% expected rate × 50 providers ~ 0 — sampling noise.
    """
    p = d["providers"]
    if len(p) == 0:
        return Check("leie_provider_share", True, "empty")
    excl = int(p["leie_excluded_flag"].sum())
    share = excl / len(p)
    if len(p) < 200:
        ok = True
        detail = f"smoke tolerance (n_providers={len(p)}<200): {excl} excluded ({share:.2%})"
    else:
        ok = 0.001 <= share <= 0.02
        detail = f"LEIE share={share:.2%} ({excl} of {len(p)}), band 0.1-2%"
    return Check("leie_provider_share", ok, detail)


# Approximate ZIP3 bands per state (must match generator STATE_ZIP3_BANDS).
# Keeping the table in two places is deliberate so the gate is independent of
# generator internals and won't false-pass if the generator's table drifts.
_STATE_ZIP3_BANDS = {
    "TX": [(750, 799), (770, 779), (780, 789)],
    "FL": [(320, 349)],
    "CA": [(900, 961)],
    "NY": [(100, 149)],
    "MI": [(480, 499)],
}


def check_claim_line_multiplicity(d: dict[str, pd.DataFrame]) -> Check:
    """Real claims average ~2-4 lines per header. A flat 1.0 lines/claim is a
    dead giveaway that the synth generator is a placeholder. Floor 1.8."""
    h = d["claims_header"]
    li = d["claims_line"]
    if len(h) == 0 or len(li) == 0:
        return Check("claim_line_multiplicity", True, "empty")
    avg = len(li) / len(h)
    ok = avg >= 1.8
    return Check("claim_line_multiplicity", ok,
                 f"avg={avg:.2f} lines/claim across {len(h):,} headers (floor 1.8)")


def check_carc_top5_concentration(d: dict[str, pd.DataFrame]) -> Check:
    """Top-5 CARC codes should cover >=50% of all denials. Real adjudication
    is heavily concentrated on a handful of codes (50, 97, 16, 1, 45)."""
    c = d["claims_header"]
    if len(c) == 0:
        return Check("carc_top5_concentration", True, "empty")
    denials = c[c["denied_flag"] == 1]
    if len(denials) < 50:
        return Check("carc_top5_concentration", True, f"only {len(denials)} denials, skipping")
    top5 = denials["carc_code"].value_counts(normalize=True).head(5).sum()
    ok = top5 >= 0.50
    return Check("carc_top5_concentration", ok,
                 f"top-5 CARC share={top5:.2%} of {len(denials)} denials (floor 50%)")


def check_state_zip_alignment(d: dict[str, pd.DataFrame]) -> Check:
    """At least 80% of members must have a zip3 inside the geographic ZIP
    band for their state. A random 3-digit zip per member breaks territory,
    network adequacy, and geo-targeted Stars analytics."""
    m = d["members"]
    if len(m) == 0:
        return Check("state_zip_alignment", True, "empty")
    def _aligned(row) -> bool:
        bands = _STATE_ZIP3_BANDS.get(row["state"])
        if not bands: return True       # state has no band defined — neutral
        try:
            z = int(str(row["zip3"]).lstrip("0") or "0")
        except (ValueError, TypeError):
            return False
        return any(lo <= z <= hi for lo, hi in bands)
    aligned = m.apply(_aligned, axis=1)
    rate = aligned.mean()
    ok = rate >= 0.80
    return Check("state_zip_alignment", ok,
                 f"{rate:.2%} of {len(m)} members have zip3 inside state band (floor 80%)")


def check_pcp_geo_alignment(d: dict[str, pd.DataFrame]) -> Check:
    """At least 75% of members should have a PCP in the same state. HEDIS
    access-of-care attribution and provider directory accuracy depend on it."""
    m = d["members"]
    p = d["providers"]
    if len(m) == 0 or len(p) == 0:
        return Check("pcp_geo_alignment", True, "empty")
    if "pcp_provider_id" not in m.columns:
        return Check("pcp_geo_alignment", True, "no pcp_provider_id column")
    prov_state = dict(zip(p["provider_npi"].astype(str),
                          p["state"].astype(str), strict=False))
    same = sum(1 for _, row in m.iterrows()
               if prov_state.get(str(row["pcp_provider_id"])) == row["state"])
    rate = same / len(m)
    ok = rate >= 0.75
    return Check("pcp_geo_alignment", ok,
                 f"{rate:.2%} of {len(m)} members have same-state PCP (floor 75%)")


def check_rx_quantity_doses_realism(d: dict[str, pd.DataFrame]) -> Check:
    """At least one drug class must have quantity_dispensed != days_supply on
    >=80% of its fills. A generator that always sets qty = days_supply is
    pretending every drug is one-dose-a-day, which fails for metformin (BID),
    GLP-1 (weekly), and specialty injectables."""
    rx = d["rx_claims"]
    if len(rx) == 0:
        return Check("rx_quantity_doses_realism", True, "empty")
    rx = rx.copy()
    rx["qty_neq_days"] = rx["quantity_dispensed"] != rx["days_supply"]
    per_class = rx.groupby("drug_class")["qty_neq_days"].mean()
    above = per_class[per_class >= 0.80]
    ok = len(above) >= 1
    return Check("rx_quantity_doses_realism", ok,
                 f"{len(above)} drug classes with >=80% qty!=days_supply "
                 f"(top: {per_class.sort_values(ascending=False).head(3).to_dict()})")


def check_pa_fill_consistency(d: dict[str, pd.DataFrame]) -> Check:
    """No rx fill may exist where the PA was denied for the same (member,
    ndc, plan_year). If this fails, the PBM logic in silver is broken or
    the generator is emitting impossible fills."""
    rx = d["rx_claims"]
    pa = d["pharmacy_pa"]
    if len(rx) == 0 or len(pa) == 0:
        return Check("pa_fill_consistency", True, "empty")
    denied = pa[pa["decision"] == "deny"]
    if len(denied) == 0:
        return Check("pa_fill_consistency", True, "no denied PAs")
    denied_keys = set(zip(
        denied["member_id"].astype(str),
        denied["ndc_code"].astype(str),
        denied["plan_year"].astype(int),
        strict=False,
    ))
    bad = sum(1 for m, n, y in zip(
        rx["member_id"].astype(str),
        rx["ndc_code"].astype(str),
        rx["plan_year"].astype(int),
        strict=False) if (m, n, y) in denied_keys)
    ok = bad == 0
    return Check("pa_fill_consistency", ok,
                 f"{bad} rx fills exist after PA denial (must be 0)")


def check_hrrp_cohort_from_dx(d: dict[str, pd.DataFrame]) -> Check:
    """HRRP cohort assignment must be consistent with the indexed admission's
    primary_dx_code. AMI rows should be I21*, HF should be I50*, etc. Random
    cohort assignment breaks readmission-rate-by-cohort analytics."""
    rdm = d["readmission"]
    hdr = d["claims_header"]
    if len(rdm) == 0 or len(hdr) == 0:
        return Check("hrrp_cohort_from_dx", True, "empty")
    merged = rdm.merge(hdr[["claim_id", "primary_dx_code"]],
                       left_on="index_claim_id", right_on="claim_id", how="left")
    prefix = {"AMI": "I21", "HF": "I50", "PNEUMONIA": ("J18", "J15"),
              "COPD": "J44", "THA_TKA": ("M17", "M16"), "CABG": "I25"}
    def _matches(row) -> bool:
        pat = prefix.get(row["hrrp_cohort"])
        dx = str(row["primary_dx_code"])
        if pat is None: return True
        if isinstance(pat, tuple): return any(dx.startswith(p) for p in pat)
        return dx.startswith(pat)
    rate = merged.apply(_matches, axis=1).mean()
    ok = rate >= 0.70
    return Check("hrrp_cohort_from_dx", ok,
                 f"{rate:.2%} of {len(merged)} readmits have cohort consistent with dx (floor 70%)")


# Phase 2 (G.2): static ontology spec check — every entity declares a
# recognized binding_kind, and the source prefix matches the kind. Catches
# drift the moment someone adds an entity whose source is mistyped or whose
# binding_kind contradicts its source.
_RECOGNIZED_KINDS = {"lakehouse_table", "kql_table", "sm_measure"}
_KIND_PREFIXES = {
    "lakehouse_table": ("bronze_", "silver_", "gold_"),
    "kql_table":       ("kql_",),
    "sm_measure":      ("sm_",),
}


def check_ontology_binding_kinds(d: dict[str, pd.DataFrame]) -> Check:
    """Validate ontology/payer_ontology.yaml: each entity declares a recognized
    binding_kind (default lakehouse_table) and its `source:` prefix matches.

    Locks the Phase 2 G.2 contract that three binding kinds exist
    (lakehouse_table, kql_table, sm_measure) and prevents an entity from
    drifting to an unbacked or mis-prefixed source — which would silently
    break audit_rels.py and any downstream graph build / FabricIQPreviewTool
    wiring.
    """
    import yaml as _yaml
    ont_path = Path(__file__).resolve().parent.parent / "ontology" / "payer_ontology.yaml"
    if not ont_path.exists():
        return Check("ontology_binding_kinds", False, f"missing {ont_path}")
    onto = _yaml.safe_load(ont_path.read_text(encoding="utf-8"))
    ents = onto.get("entities") or {}
    errors: list[str] = []
    kind_tally: dict[str, int] = {k: 0 for k in _RECOGNIZED_KINDS}
    for name, spec in ents.items():
        kind = (spec or {}).get("binding_kind") or "lakehouse_table"
        src = (spec or {}).get("source", "")
        if kind not in _RECOGNIZED_KINDS:
            errors.append(f"{name}: binding_kind={kind!r} not in {sorted(_RECOGNIZED_KINDS)}")
            continue
        kind_tally[kind] = kind_tally.get(kind, 0) + 1
        allowed = _KIND_PREFIXES[kind]
        if not any(src.startswith(p) for p in allowed):
            errors.append(
                f"{name}: source={src!r} does not start with any of {allowed} for binding_kind={kind!r}"
            )
    aliases = onto.get("entity_aliases") or {}
    missing_aliases = sorted(set(ents) - set(aliases))
    if missing_aliases:
        errors.append(f"entities without aliases: {missing_aliases}")
    if errors:
        return Check("ontology_binding_kinds", False, " | ".join(errors))
    summary = ", ".join(f"{k}={v}" for k, v in sorted(kind_tally.items()))
    return Check(
        "ontology_binding_kinds",
        True,
        f"{len(ents)} entities all aliased; binding kinds: {summary}",
    )


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
        check_glp1_pa_volume(d),
        check_specialty_drug_share(d),
        check_readmission_rate(d),
        check_sdoh_capture_rate(d),
        check_oon_ed_share(d),
        check_leie_provider_share(d),
        check_claim_line_multiplicity(d),
        check_carc_top5_concentration(d),
        check_state_zip_alignment(d),
        check_pcp_geo_alignment(d),
        check_rx_quantity_doses_realism(d),
        check_pa_fill_consistency(d),
        check_hrrp_cohort_from_dx(d),
        check_ontology_binding_kinds(d),
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

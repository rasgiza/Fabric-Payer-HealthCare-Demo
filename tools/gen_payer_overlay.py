"""
gen_payer_overlay.py — synthetic payer-shaped data generator.

Produces a deterministic payer dataset (members, enrollment, claims, Rx, auths,
appeals, premiums, providers, RAF, quality compliance) calibrated to public
industry distributions. Either run standalone (self-contained synthetic base)
or layer on top of Synthea CSVs by passing --synthea-dir.

Output: CSVs under data/synth/<run_id>/ ready for Phase 2 bronze ingest.

Default scale=1.0 ≈ 100K members. Use --scale 0.005 for a 500-member smoke test.
"""

from __future__ import annotations
import argparse
import hashlib
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REF = Path(__file__).resolve().parent.parent / "data" / "reference"
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "synth"

LOB_MIX = {"MA": 0.45, "Medicaid": 0.30, "Commercial": 0.20, "Dual": 0.05}
PRODUCT_MIX_BY_LOB = {
    "MA":         {"HMO": 0.55, "PPO": 0.40, "PFFS": 0.05},
    "Medicaid":   {"HMO": 0.85, "EPO": 0.15},
    "Commercial": {"PPO": 0.45, "HMO": 0.25, "HDHP": 0.20, "EPO": 0.10},
    "Dual":       {"DSNP": 1.00},
}
STATE_MIX = {"TX": 0.25, "FL": 0.22, "CA": 0.22, "NY": 0.18, "MI": 0.13}
RACE_MIX = {"White": 0.58, "Black": 0.14, "Hispanic": 0.18, "Asian": 0.06, "Other": 0.04}

PCP_SPECIALTIES = ["Family Medicine", "Internal Medicine", "Pediatrics", "Geriatrics"]
SPECIALIST_SPECIALTIES = ["Cardiology", "Endocrinology", "Nephrology", "Pulmonology",
                          "Oncology", "Psychiatry", "Orthopedics", "Neurology",
                          "Gastroenterology", "Ophthalmology", "Dermatology", "Radiology"]

CPT_ENCOUNTER = {
    "99213": ("Office visit, established patient (low)", 95.0),
    "99214": ("Office visit, established patient (moderate)", 145.0),
    "99215": ("Office visit, established patient (high)", 205.0),
    "99203": ("Office visit, new patient (low)", 130.0),
    "99204": ("Office visit, new patient (moderate)", 195.0),
    "99284": ("ED visit (high severity)", 525.0),
    "99285": ("ED visit (highest severity)", 825.0),
    "99223": ("Initial inpatient admission, comprehensive", 285.0),
    "92012": ("Eye exam, established patient", 110.0),
    "G0438": ("Annual Wellness Visit, initial", 175.0),
    "G0439": ("Annual Wellness Visit, subsequent", 145.0),
    "82947": ("Glucose, blood test", 12.0),
    "83036": ("HbA1c", 28.0),
    "80061": ("Lipid panel", 35.0),
    "77067": ("Screening mammography", 175.0),
    "45378": ("Colonoscopy, diagnostic", 920.0),
    "G0121": ("Colorectal cancer screening, average risk", 825.0),
    "93000": ("EKG", 65.0),
    "93306": ("Echocardiogram", 425.0),
    "27447": ("Total knee arthroplasty", 18500.0),
    "29881": ("Knee arthroscopy with meniscectomy", 5200.0),
    "70551": ("MRI brain without contrast", 1850.0),
    "72148": ("MRI lumbar without contrast", 1450.0),
    "97110": ("Therapeutic exercises (PT)", 65.0),
}
PA_REQUIRED_CPTS = {"27447", "29881", "70551", "72148", "93306"}
INPATIENT_CPTS = {"99223", "27447"}

DRUG_CLASS = {
    "MAH-PDC": [("RAS-LISINOPRIL", "Lisinopril 10mg", 18.0), ("RAS-LOSARTAN", "Losartan 50mg", 22.0)],
    "MAD-PDC": [("DM-METFORMIN", "Metformin 500mg", 14.0), ("DM-EMPAGLIFLOZIN", "Empagliflozin 10mg", 525.0)],
    "MAC-PDC": [("STATIN-ATORVA", "Atorvastatin 20mg", 12.0), ("STATIN-ROSUVA", "Rosuvastatin 10mg", 28.0)],
    "SPC-PDC": [("AP-RISPERIDONE", "Risperidone 1mg", 32.0), ("AP-OLANZAPINE", "Olanzapine 5mg", 88.0)],
}

LOB_TO_PAYER_FILTER = {
    "MA": ["MA"], "Dual": ["MA"],
    "Medicaid": ["Medicaid"], "Commercial": ["Commercial"],
}
PREMIUM_PMPM = {"MA": 1100.0, "Dual": 1450.0, "Medicaid": 540.0, "Commercial": 620.0}


@dataclass
class GenConfig:
    scale: float
    seed: int
    start_year: int
    n_years: int
    out: Path
    synthea_dir: Path | None


def _mbi_hash(member_int: int, salt: str = "demo") -> str:
    return hashlib.sha256(f"{salt}:{member_int}".encode()).hexdigest()[:11].upper()


def _pick(rng: np.random.Generator, mapping: dict, n: int) -> np.ndarray:
    keys = list(mapping.keys())
    p = np.array(list(mapping.values()))
    p = p / p.sum()
    return rng.choice(keys, size=n, p=p)


def _load_reference():
    return {
        "payers": pd.read_csv(REF / "payers.csv"),
        "carc": pd.read_csv(REF / "carc_codes.csv"),
        "hedis": pd.read_csv(REF / "hedis_my2026_measures.csv"),
        "stars_cuts": pd.read_csv(REF / "cms_stars_2026_cutpoints.csv"),
        "hcc": pd.read_csv(REF / "hcc_v28_sample.csv"),
        "conditions": pd.read_csv(REF / "conditions_prevalence.csv"),
    }


# ============================================================================
# MEMBERS
# ============================================================================

def gen_members(cfg: GenConfig, rng: np.random.Generator, ref: dict) -> pd.DataFrame:
    n = max(int(100_000 * cfg.scale), 50)
    lob = _pick(rng, LOB_MIX, n)
    state = _pick(rng, STATE_MIX, n)
    race = _pick(rng, RACE_MIX, n)
    sex = rng.choice(["F", "M"], size=n, p=[0.54, 0.46])

    age = np.empty(n, dtype=int)
    for i, l in enumerate(lob):
        if l == "MA":      age[i] = int(rng.normal(73, 7))
        elif l == "Dual":  age[i] = int(rng.normal(70, 9))
        elif l == "Medicaid":  age[i] = int(rng.normal(33, 18))
        else:              age[i] = int(rng.normal(42, 14))
    age = np.clip(age, 1, 99)

    today = date(cfg.start_year + cfg.n_years - 1, 12, 31)
    dob = [today - timedelta(days=int(a * 365.25 + rng.integers(0, 365))) for a in age]

    products = []
    for l in lob:
        products.append(np.random.default_rng(rng.integers(0, 2**32)).choice(
            list(PRODUCT_MIX_BY_LOB[l].keys()),
            p=list(PRODUCT_MIX_BY_LOB[l].values())))

    payers = ref["payers"]
    payer_ids = []
    for l, st in zip(lob, state):
        eligible = payers[payers["lob"].isin(LOB_TO_PAYER_FILTER[l]) &
                          payers["market_states"].str.contains(st)]
        if len(eligible) == 0:
            eligible = payers[payers["lob"].isin(LOB_TO_PAYER_FILTER[l])]
        payer_ids.append(eligible.sample(1, random_state=int(rng.integers(0, 2**31)))["payer_id"].iloc[0])

    member_ids = [f"M{1_000_000 + i:08d}" for i in range(n)]
    plan_year = cfg.start_year

    df = pd.DataFrame({
        "member_id": member_ids,
        "mbi_hash": [_mbi_hash(1_000_000 + i) for i in range(n)],
        "subscriber_id": [f"SUB{1_000_000 + i:08d}" for i in range(n)],
        "lob": lob,
        "product": products,
        "state": state,
        "race_ethnicity": race,
        "sex": sex,
        "age_at_year_end": age,
        "dob_year": [d.year for d in dob],
        "zip3": [f"{rng.integers(100, 1000):03d}" for _ in range(n)],
        "payer_id": payer_ids,
        "plan_id": [f"PLN-{p[-3:]}-{i % 8 + 1:02d}" for i, p in enumerate(products)],
        "pcp_provider_id": [f"PRV-{rng.integers(10000, 99999)}" for _ in range(n)],
        "effective_year": plan_year,
        "sdoh_housing_unstable": rng.random(n) < 0.08,
        "sdoh_food_insecure":     rng.random(n) < 0.12,
        "sdoh_transport_barrier": rng.random(n) < 0.10,
    })
    return df


# ============================================================================
# ENROLLMENT SPANS (member-month grain via expansion)
# ============================================================================

def gen_enrollment(cfg: GenConfig, rng: np.random.Generator, members: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, m in members.iterrows():
        for yr in range(cfg.start_year, cfg.start_year + cfg.n_years):
            churn_month = rng.integers(1, 18)
            if churn_month <= 12 and rng.random() < 0.13:
                start_m = 1; end_m = int(churn_month)
                term_reason = rng.choice(["voluntary_disenroll", "moved_oos", "lost_eligibility", "death"],
                                         p=[0.55, 0.20, 0.20, 0.05])
            else:
                start_m = 1; end_m = 12; term_reason = None
            rows.append({
                "member_id": m["member_id"], "plan_year": yr,
                "start_month": start_m, "end_month": end_m,
                "member_months": end_m - start_m + 1,
                "termination_reason": term_reason,
                "lob": m["lob"], "product": m["product"], "payer_id": m["payer_id"],
            })
    return pd.DataFrame(rows)


# ============================================================================
# PROVIDERS
# ============================================================================

def gen_providers(cfg: GenConfig, rng: np.random.Generator) -> pd.DataFrame:
    n = max(int(5_000 * cfg.scale), 50)
    npis = [f"NPI-{1_000_000_000 + i:010d}" for i in range(n)]
    is_pcp = rng.random(n) < 0.45
    spec = [rng.choice(PCP_SPECIALTIES) if pcp else rng.choice(SPECIALIST_SPECIALTIES) for pcp in is_pcp]
    state = _pick(rng, STATE_MIX, n)
    return pd.DataFrame({
        "provider_npi": npis,
        "provider_name": [f"Provider {i}" for i in range(n)],
        "specialty_type": spec,
        "is_pcp": is_pcp,
        "state": state,
        "in_network_flag": rng.random(n) < 0.92,
        "apm_tier": rng.choice([1, 2, "3a", "3b", 4], size=n, p=[0.30, 0.35, 0.18, 0.12, 0.05]),
        "gold_carded_flag": rng.random(n) < 0.04,
    })


# ============================================================================
# CONDITIONS (per-member, drives downstream claims/Rx/RAF/HEDIS)
# ============================================================================

def gen_conditions(rng: np.random.Generator, members: pd.DataFrame, ref: dict) -> pd.DataFrame:
    cond_ref = ref["conditions"]
    rows = []
    for _, m in members.iterrows():
        age = m["age_at_year_end"]; lob = m["lob"]
        prev_col = {"MA": "prevalence_ma", "Dual": "prevalence_ma",
                    "Medicaid": "prevalence_medicaid", "Commercial": "prevalence_commercial"}[lob]
        for _, c in cond_ref.iterrows():
            base = c[prev_col]
            age_factor = max(0.2, 1 + (age - c["age_skew"]) / 100.0)
            p = min(0.95, base * age_factor)
            if rng.random() < p:
                rows.append({
                    "member_id": m["member_id"],
                    "condition_code": c["condition_code"],
                    "icd10": c["icd10"],
                    "hcc_v28": c["hcc_v28"] if pd.notna(c["hcc_v28"]) else None,
                    "first_seen_year": int(rng.integers(2018, 2026)),
                })
    return pd.DataFrame(rows)


# ============================================================================
# CLAIMS (header + line) and PHARMACY
# ============================================================================

def gen_claims(cfg: GenConfig, rng: np.random.Generator, members: pd.DataFrame,
               providers: pd.DataFrame, conditions: pd.DataFrame, ref: dict):
    carc = ref["carc"]
    pcp_ids = providers[providers["is_pcp"]]["provider_npi"].tolist() or providers["provider_npi"].tolist()
    spec_ids = providers[~providers["is_pcp"]]["provider_npi"].tolist() or providers["provider_npi"].tolist()

    headers, lines = [], []
    member_cond_map = conditions.groupby("member_id")["condition_code"].apply(list).to_dict()
    claim_idx = 0
    for _, m in members.iterrows():
        mid = m["member_id"]
        member_conds = member_cond_map.get(mid, [])
        n_chronic = len(member_conds)
        for yr in range(cfg.start_year, cfg.start_year + cfg.n_years):
            n_visits = int(rng.poisson(2 + n_chronic * 1.6))
            n_visits = min(n_visits, 50)
            for _ in range(n_visits):
                claim_idx += 1
                claim_id = f"CLM-{claim_idx:010d}"
                month = int(rng.integers(1, 13)); day = int(rng.integers(1, 28))
                dos = date(yr, month, day)
                is_inpatient = rng.random() < 0.04
                is_ed = rng.random() < 0.06
                is_pa = (not is_inpatient) and rng.random() < 0.05
                if is_inpatient:
                    cpt = rng.choice(list(INPATIENT_CPTS))
                elif is_ed:
                    cpt = rng.choice(["99284", "99285"])
                elif is_pa:
                    cpt = rng.choice(list(PA_REQUIRED_CPTS))
                else:
                    cpt = rng.choice(["99213", "99214", "99215", "99203", "99204",
                                      "G0438", "G0439", "92012", "82947", "83036",
                                      "80061", "77067", "45378", "G0121", "93000"])
                provider = rng.choice(spec_ids if cpt in PA_REQUIRED_CPTS or is_inpatient else pcp_ids)
                pos = "21" if is_inpatient else ("23" if is_ed else "11")

                base = CPT_ENCOUNTER.get(cpt, ("Unknown", 100.0))[1]
                billed = base * float(rng.uniform(1.5, 2.4))
                allowed = base * float(rng.uniform(0.8, 1.05))
                denied = rng.random() < 0.135
                carc_code = carc.sample(1, weights=[1]*len(carc),
                                        random_state=int(rng.integers(0, 2**31)))["carc_code"].iloc[0] if denied else None
                if denied:
                    paid = 0.0; member_liability = 0.0
                else:
                    member_cost_share = float(rng.uniform(0.0, 0.25))
                    member_liability = round(allowed * member_cost_share, 2)
                    paid = round(allowed - member_liability, 2)

                primary_dx = (rng.choice(member_conds) if member_conds and rng.random() < 0.7
                              else rng.choice(["Z00.00", "Z23", "R51", "M54.5", "J06.9"]))

                headers.append({
                    "claim_id": claim_id, "member_id": mid, "provider_npi": provider,
                    "payer_id": m["payer_id"], "plan_year": yr, "service_date": dos,
                    "claim_type": "institutional" if is_inpatient else "professional",
                    "place_of_service": pos,
                    "primary_dx_code": primary_dx,
                    "billed_amount": round(billed, 2), "allowed_amount": round(allowed, 2),
                    "paid_amount": paid, "member_liability": member_liability,
                    "denied_flag": denied, "carc_code": carc_code,
                    "pa_required_flag": cpt in PA_REQUIRED_CPTS,
                    "lob": m["lob"],
                })
                lines.append({
                    "claim_id": claim_id, "line_no": 1, "cpt_hcpcs": cpt,
                    "units": 1, "modifier": None,
                    "billed_amount": round(billed, 2), "allowed_amount": round(allowed, 2),
                    "paid_amount": paid,
                })
    return pd.DataFrame(headers), pd.DataFrame(lines)


def gen_pharmacy(cfg: GenConfig, rng: np.random.Generator, members: pd.DataFrame,
                 conditions: pd.DataFrame, providers: pd.DataFrame) -> pd.DataFrame:
    pcp_ids = providers[providers["is_pcp"]]["provider_npi"].tolist() or providers["provider_npi"].tolist()
    cond_to_drugclass = {
        "DIABETES": "MAD-PDC", "DIABETES_COMP": "MAD-PDC",
        "HTN": "MAH-PDC", "HLD": "MAC-PDC", "CAD": "MAC-PDC",
        "SCHIZOPHRENIA": "SPC-PDC", "BIPOLAR": "SPC-PDC",
    }
    member_cond = conditions.groupby("member_id")["condition_code"].apply(set).to_dict()
    rows = []
    rx_idx = 0
    for _, m in members.iterrows():
        mid = m["member_id"]
        cs = member_cond.get(mid, set())
        for c in cs:
            klass = cond_to_drugclass.get(c)
            if not klass: continue
            ndc, drug_name, unit_cost = DRUG_CLASS[klass][int(rng.integers(0, len(DRUG_CLASS[klass])))]
            adherent_member = rng.random() < 0.78
            for yr in range(cfg.start_year, cfg.start_year + cfg.n_years):
                n_fills = 11 if adherent_member else int(rng.integers(3, 9))
                for f in range(n_fills):
                    rx_idx += 1
                    fill_date = date(yr, min(12, f + 1), int(rng.integers(1, 28)))
                    days_supply = 30 if rng.random() < 0.7 else 90
                    rows.append({
                        "rx_claim_id": f"RX-{rx_idx:010d}", "member_id": mid,
                        "ndc_code": ndc, "drug_name": drug_name, "drug_class": klass,
                        "fill_date": fill_date, "days_supply": days_supply,
                        "quantity_dispensed": days_supply,
                        "prescriber_npi": rng.choice(pcp_ids),
                        "billed_amount": round(unit_cost * days_supply * 1.4, 2),
                        "paid_amount": round(unit_cost * days_supply, 2),
                        "formulary_tier": int(rng.integers(1, 5)),
                        "plan_year": yr, "payer_id": m["payer_id"],
                    })
    return pd.DataFrame(rows)


# ============================================================================
# AUTHS / APPEALS
# ============================================================================

def gen_auths(rng: np.random.Generator, claims: pd.DataFrame) -> pd.DataFrame:
    pa_claims = claims[claims["pa_required_flag"]].copy()
    rows = []
    for _, c in pa_claims.iterrows():
        sub = pd.Timestamp(c["service_date"]) - pd.Timedelta(days=int(rng.integers(2, 14)))
        is_expedited = rng.random() < 0.12
        sla_hours = 72 if is_expedited else 168
        tat_hours = float(rng.gamma(2.2, 18 if is_expedited else 36))
        decision = "approve" if rng.random() < 0.78 else "deny"
        rows.append({
            "auth_id": f"AUTH-{c['claim_id'][4:]}",
            "member_id": c["member_id"], "provider_npi": c["provider_npi"],
            "payer_id": c["payer_id"], "plan_year": c["plan_year"],
            "submitted_at": sub.date(),
            "decision_at": (sub + pd.Timedelta(hours=tat_hours)).date(),
            "decision": decision,
            "request_type": "expedited" if is_expedited else "standard",
            "tat_hours": round(tat_hours, 1), "sla_hours": sla_hours,
            "sla_met": tat_hours <= sla_hours,
            "submitted_via_fhir": rng.random() < 0.18,
            "linked_claim_id": c["claim_id"],
        })
    return pd.DataFrame(rows)


def gen_appeals(rng: np.random.Generator, claims: pd.DataFrame, ref: dict) -> pd.DataFrame:
    denied = claims[claims["denied_flag"]].copy()
    rows = []
    carc = ref["carc"].set_index("carc_code")["typical_overturn_rate"].to_dict()
    for _, c in denied.iterrows():
        if rng.random() < 0.32:
            ot_rate = carc.get(c["carc_code"], 0.30)
            level = int(rng.choice([1, 2, 3], p=[0.70, 0.22, 0.08]))
            rows.append({
                "appeal_id": f"APL-{c['claim_id'][4:]}",
                "claim_id": c["claim_id"], "member_id": c["member_id"],
                "level": level, "carc_code": c["carc_code"],
                "filed_date": pd.Timestamp(c["service_date"]) + pd.Timedelta(days=int(rng.integers(7, 60))),
                "decision": "overturn" if rng.random() < ot_rate else "uphold",
                "peer_to_peer_flag": level == 1 and rng.random() < 0.35,
                "plan_year": c["plan_year"],
            })
    return pd.DataFrame(rows)


def gen_premium(cfg: GenConfig, rng: np.random.Generator, enrollment: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, e in enrollment.iterrows():
        pmpm = PREMIUM_PMPM[e["lob"]] * float(rng.uniform(0.95, 1.08))
        rows.append({
            "member_id": e["member_id"], "plan_year": e["plan_year"],
            "lob": e["lob"], "payer_id": e["payer_id"],
            "member_months": e["member_months"],
            "premium_pmpm": round(pmpm, 2),
            "premium_total": round(pmpm * e["member_months"], 2),
        })
    return pd.DataFrame(rows)


# ============================================================================
# RISK ADJUSTMENT (RAF) and QUALITY (HEDIS / Stars compliance)
# ============================================================================

def gen_raf(rng: np.random.Generator, members: pd.DataFrame, conditions: pd.DataFrame,
            ref: dict) -> pd.DataFrame:
    hcc = ref["hcc"].set_index("hcc_v28")["raf_coefficient"].to_dict()
    member_hccs = (conditions[conditions["hcc_v28"].notna()]
                   .groupby("member_id")["hcc_v28"].apply(set).to_dict())
    rows = []
    for _, m in members.iterrows():
        if m["lob"] not in ("MA", "Dual"): continue
        all_hccs = member_hccs.get(m["member_id"], set())
        coded_hccs = {h for h in all_hccs if rng.random() < 0.78}
        suspect_hccs = all_hccs - coded_hccs
        demo_raf = 0.45 + (m["age_at_year_end"] - 65) * 0.012
        raf = max(0.30, demo_raf + sum(hcc.get(h, 0.0) for h in coded_hccs))
        rows.append({
            "member_id": m["member_id"], "plan_year": 2026,
            "demographic_raf": round(demo_raf, 4),
            "coded_hcc_count": len(coded_hccs),
            "suspect_hcc_count": len(suspect_hccs),
            "coded_hccs": ";".join(sorted(coded_hccs)),
            "suspect_hccs": ";".join(sorted(suspect_hccs)),
            "raf_score": round(raf, 4),
        })
    return pd.DataFrame(rows)


def gen_quality(rng: np.random.Generator, members: pd.DataFrame, conditions: pd.DataFrame,
                rx: pd.DataFrame, claims: pd.DataFrame, ref: dict) -> pd.DataFrame:
    cond = conditions.groupby("member_id")["condition_code"].apply(set).to_dict()
    rx_by_member_class = (rx.groupby(["member_id", "drug_class"])["days_supply"].sum()
                          .reset_index() if len(rx) else pd.DataFrame(columns=["member_id", "drug_class", "days_supply"]))
    cpt_by_member = claims.groupby("member_id")["claim_id"].count().to_dict()
    measures = ref["hedis"]
    rows = []
    for _, m in members.iterrows():
        cs = cond.get(m["member_id"], set())
        for _, meas in measures.iterrows():
            mid_lob = m["lob"]; applic = meas["lob_applicability"]
            if mid_lob not in applic: continue
            mid = meas["measure_id"]
            eligible = False; compliant = False
            if mid in ("CDC-EYE", "CDC-HBA1C"):
                eligible = "DIABETES" in cs or "DIABETES_COMP" in cs
                compliant = eligible and rng.random() < 0.71
            elif mid == "CBP":
                eligible = "HTN" in cs and m["age_at_year_end"] >= 18
                compliant = eligible and rng.random() < 0.72
            elif mid == "SUPD":
                eligible = ("DIABETES" in cs or "DIABETES_COMP" in cs) and 40 <= m["age_at_year_end"] <= 75
                compliant = eligible and rng.random() < 0.83
            elif mid == "BCS":
                eligible = m["sex"] == "F" and 50 <= m["age_at_year_end"] <= 74
                compliant = eligible and rng.random() < 0.74
            elif mid == "COL":
                eligible = 45 <= m["age_at_year_end"] <= 75
                compliant = eligible and rng.random() < 0.66
            elif mid == "CCS":
                eligible = m["sex"] == "F" and 21 <= m["age_at_year_end"] <= 64
                compliant = eligible and rng.random() < 0.70
            elif mid in ("MAH-PDC", "MAD-PDC", "MAC-PDC", "SPC-PDC"):
                eligible_class_map = {"MAH-PDC": "HTN", "MAD-PDC": "DIABETES",
                                      "MAC-PDC": "HLD", "SPC-PDC": "SCHIZOPHRENIA"}
                eligible = eligible_class_map[mid] in cs and m["lob"] == "MA"
                if eligible:
                    sub = rx_by_member_class[(rx_by_member_class["member_id"] == m["member_id"]) &
                                             (rx_by_member_class["drug_class"] == mid)]
                    days = int(sub["days_supply"].sum()) if len(sub) else 0
                    compliant = days >= int(0.80 * 365)
            elif mid == "CMR":
                eligible = m["lob"] == "MA" and m["age_at_year_end"] >= 65 and len(cs) >= 3
                compliant = eligible and rng.random() < 0.76
            elif mid == "FMC":
                eligible = m["lob"] in ("MA", "Medicaid") and len(cs) >= 2
                compliant = eligible and rng.random() < 0.62
            elif mid == "PCR":
                eligible = m["lob"] == "MA" and cpt_by_member.get(m["member_id"], 0) > 8
                compliant = eligible and rng.random() < 0.91
            elif mid == "TRC":
                eligible = m["lob"] == "MA" and cpt_by_member.get(m["member_id"], 0) > 6
                compliant = eligible and rng.random() < 0.68
            if eligible:
                rows.append({"member_id": m["member_id"], "measure_id": mid,
                             "plan_year": 2026, "eligible": True, "compliant": compliant,
                             "lob": m["lob"]})
    return pd.DataFrame(rows)


# ============================================================================
# DRIVER
# ============================================================================

def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--scale", type=float, default=1.0,
                   help="Scale factor; 1.0=100K members, 0.005=500 (smoke test)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--start-year", type=int, default=2022)
    p.add_argument("--years", type=int, default=5)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--synthea-dir", type=Path, default=None,
                   help="Optional Synthea CSV output dir; not required")
    p.add_argument("--run-id", type=str, default=None)
    args = p.parse_args(argv)

    run_id = args.run_id or f"scale_{args.scale}".replace(".", "p")
    out = args.out / run_id
    out.mkdir(parents=True, exist_ok=True)

    cfg = GenConfig(scale=args.scale, seed=args.seed,
                    start_year=args.start_year, n_years=args.years,
                    out=out, synthea_dir=args.synthea_dir)
    rng = np.random.default_rng(cfg.seed)
    ref = _load_reference()

    print(f"[gen] scale={cfg.scale} seed={cfg.seed} years={cfg.n_years} out={out}")

    print("[gen] members...");      members  = gen_members(cfg, rng, ref);      members.to_csv(out / "members.csv", index=False)
    print(f"  -> {len(members):,}")
    print("[gen] enrollment...");   enroll   = gen_enrollment(cfg, rng, members); enroll.to_csv(out / "enrollment_spans.csv", index=False)
    print(f"  -> {len(enroll):,}")
    print("[gen] providers...");    provs    = gen_providers(cfg, rng);          provs.to_csv(out / "providers.csv", index=False)
    print(f"  -> {len(provs):,}")
    pcp_npis = provs[provs["is_pcp"]]["provider_npi"].tolist() or provs["provider_npi"].tolist()
    members["pcp_provider_id"] = rng.choice(pcp_npis, size=len(members))
    members.to_csv(out / "members.csv", index=False)
    print("[gen] conditions...");   conds    = gen_conditions(rng, members, ref); conds.to_csv(out / "conditions.csv", index=False)
    print(f"  -> {len(conds):,}")
    print("[gen] claims...");       hdrs, lines = gen_claims(cfg, rng, members, provs, conds, ref)
    hdrs.to_csv(out / "claims_header.csv", index=False); lines.to_csv(out / "claims_line.csv", index=False)
    print(f"  -> {len(hdrs):,} headers, {len(lines):,} lines")
    print("[gen] pharmacy...");     rx       = gen_pharmacy(cfg, rng, members, conds, provs); rx.to_csv(out / "rx_claims.csv", index=False)
    print(f"  -> {len(rx):,}")
    print("[gen] auths...");        auths    = gen_auths(rng, hdrs);             auths.to_csv(out / "auths.csv", index=False)
    print(f"  -> {len(auths):,}")
    print("[gen] appeals...");      appeals  = gen_appeals(rng, hdrs, ref);      appeals.to_csv(out / "appeals.csv", index=False)
    print(f"  -> {len(appeals):,}")
    print("[gen] premium...");      prem     = gen_premium(cfg, rng, enroll);    prem.to_csv(out / "premiums.csv", index=False)
    print(f"  -> {len(prem):,}")
    print("[gen] raf...");          raf      = gen_raf(rng, members, conds, ref); raf.to_csv(out / "raf_scores.csv", index=False)
    print(f"  -> {len(raf):,}")
    print("[gen] quality...");      qual     = gen_quality(rng, members, conds, rx, hdrs, ref); qual.to_csv(out / "quality_events.csv", index=False)
    print(f"  -> {len(qual):,}")

    payers = ref["payers"]; payers.to_csv(out / "payers.csv", index=False)
    print(f"[gen] DONE -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

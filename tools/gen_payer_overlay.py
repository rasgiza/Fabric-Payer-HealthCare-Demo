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
    "GLP1":    [("GLP1-SEMA", "Ozempic 1mg", 935.0), ("GLP1-TIRZ", "Mounjaro 5mg", 1095.0), ("GLP1-WEGO", "Wegovy 2.4mg", 1350.0)],
    "SPECIALTY-IMM": [("IMM-ADAL", "Humira 40mg", 6850.0), ("IMM-USTE", "Stelara 90mg", 24500.0)],
}

# IRA Maximum Fair Price (MFP) negotiated drugs effective plan year 2026.
# Reference: CMS-DRUG-NEGOTIATION-2026.
IRA_NEGOTIATED_NDC = {"DM-EMPAGLIFLOZIN", "IMM-USTE"}
GLP1_NDC = {"GLP1-SEMA", "GLP1-TIRZ", "GLP1-WEGO"}
SPECIALTY_NDC = {"IMM-ADAL", "IMM-USTE", "DM-EMPAGLIFLOZIN"}

GRAVITY_SDOH_DOMAINS = ["food_insecurity", "housing_instability", "transport_barrier",
                        "financial_strain", "social_isolation"]
HRRP_COHORTS = ["AMI", "COPD", "HF", "PNEUMONIA", "CABG", "THA_TKA"]

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
    for l, st in zip(lob, state, strict=False):
        eligible = payers[payers["lob"].isin(LOB_TO_PAYER_FILTER[l]) &
                          payers["market_states"].str.contains(st)]
        if len(eligible) == 0:
            eligible = payers[payers["lob"].isin(LOB_TO_PAYER_FILTER[l])]
        payer_ids.append(eligible.sample(1, random_state=int(rng.integers(0, 2**31)))["payer_id"].iloc[0])

    member_ids = [f"M{1_000_000 + i:08d}" for i in range(n)]
    plan_year = cfg.start_year

    # CMS Health Equity Index cohort eligibility (low-income subsidy / dual-eligible
    # OR disability). LIS/DE share is high in Dual and Medicaid, low in Commercial.
    lis_de_flag = np.array([
        rng.random() < {"Dual": 1.0, "Medicaid": 0.55, "MA": 0.18, "Commercial": 0.03}[lob_i]
        for lob_i in lob
    ])
    disability_flag = np.array([
        rng.random() < {"Dual": 0.42, "Medicaid": 0.18, "MA": 0.12, "Commercial": 0.04}[lob_i]
        for lob_i in lob
    ])

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
        # 2026 equity + parity attributes
        "lis_de_flag": lis_de_flag,
        "disability_flag": disability_flag,
        "hei_eligible_flag": lis_de_flag | disability_flag,
        "re_l_collection_method": rng.choice(
            ["self_reported", "indirect_estimated", "unknown"], size=n, p=[0.62, 0.28, 0.10]),
        "sogi_collected_flag": rng.random(n) < 0.34,
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
    in_network = rng.random(n) < 0.92
    vbc_eligible = is_pcp & (rng.random(n) < 0.35)
    return pd.DataFrame({
        "provider_npi": npis,
        "provider_name": [f"Provider {i}" for i in range(n)],
        "specialty_type": spec,
        "is_pcp": is_pcp,
        "state": state,
        "in_network_flag": in_network,
        "apm_tier": rng.choice([1, 2, "3a", "3b", 4], size=n, p=[0.30, 0.35, 0.18, 0.12, 0.05]),
        "gold_carded_flag": rng.random(n) < 0.04,
        # 2026 governance / sanctions / VBC attributes
        "leie_excluded_flag": rng.random(n) < 0.002,
        "vbc_contract_id": [f"VBC-{i % 12 + 1:03d}" if v else None for i, v in enumerate(vbc_eligible)],
        "vbc_risk_arrangement": [rng.choice(["upside_only", "two_sided"]) if v else None for v in vbc_eligible],
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

                # Network status: most claims in-network; ~8% out-of-network. NSA
                # Section 116 cost-sharing protections attach when OON AND emergent
                # OR when provider directory was stale (we proxy here, full join in silver).
                oon_flag = rng.random() < 0.08
                nsa_eligible = (oon_flag and is_ed) or (
                    oon_flag and not is_inpatient and rng.random() < 0.20)
                # Two-Midnight rule applies to MA inpatient stays under CMS-4201-F.
                two_midnight_flag = bool(is_inpatient and m["lob"] in ("MA", "Dual")
                                         and rng.random() < 0.82)

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
                    "oon_flag": oon_flag,
                    "nsa_eligible_flag": nsa_eligible,
                    "two_midnight_flag": two_midnight_flag,
                    "service_line": "inpatient" if is_inpatient else ("ed" if is_ed else "office"),
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

    def _emit_fill(mid, payer_id, klass, ndc, drug_name, unit_cost, yr, month, days_supply, prescriber):
        nonlocal rx_idx
        rx_idx += 1
        rows.append({
            "rx_claim_id": f"RX-{rx_idx:010d}", "member_id": mid,
            "ndc_code": ndc, "drug_name": drug_name, "drug_class": klass,
            "fill_date": date(yr, month, int(rng.integers(1, 28))),
            "days_supply": days_supply,
            "quantity_dispensed": days_supply,
            "prescriber_npi": prescriber,
            "billed_amount": round(unit_cost * days_supply * 1.4, 2),
            "paid_amount": round(unit_cost * days_supply, 2),
            "formulary_tier": int(rng.integers(1, 5)),
            "plan_year": yr, "payer_id": payer_id,
            "glp1_flag": ndc in GLP1_NDC,
            "ira_negotiated_flag": ndc in IRA_NEGOTIATED_NDC,
            "specialty_drug_flag": ndc in SPECIALTY_NDC,
        })

    for _, m in members.iterrows():
        mid = m["member_id"]
        cs = member_cond.get(mid, set())
        prescriber = rng.choice(pcp_ids)
        # Chronic-class adherence fills — pace one per month so dedup keys are unique.
        for c in cs:
            klass = cond_to_drugclass.get(c)
            if not klass:
                continue
            ndc, drug_name, unit_cost = DRUG_CLASS[klass][int(rng.integers(0, len(DRUG_CLASS[klass])))]
            adherent_member = rng.random() < 0.78
            for yr in range(cfg.start_year, cfg.start_year + cfg.n_years):
                n_fills = 11 if adherent_member else int(rng.integers(3, 9))
                for f in range(n_fills):
                    days_supply = 30 if rng.random() < 0.7 else 90
                    month = min(12, f + 1)
                    _emit_fill(mid, m["payer_id"], klass, ndc, drug_name, unit_cost,
                               yr, month, days_supply, prescriber)
        # GLP-1 fills: diabetics ~28% on therapy, plus obesity-indicated ~4% of remaining.
        is_diabetic = bool(cs & {"DIABETES", "DIABETES_COMP"})
        on_glp1 = (is_diabetic and rng.random() < 0.28) or (not is_diabetic and rng.random() < 0.04)
        if on_glp1:
            ndc, drug_name, unit_cost = DRUG_CLASS["GLP1"][int(rng.integers(0, 3))]
            for yr in range(max(cfg.start_year, 2024), cfg.start_year + cfg.n_years):
                n_fills = int(rng.integers(4, 12))
                for f in range(n_fills):
                    month = min(12, f + 1)
                    _emit_fill(mid, m["payer_id"], "GLP1", ndc, drug_name, unit_cost,
                               yr, month, 30, prescriber)
        # Specialty / biologic: ~1.5% of members.
        if rng.random() < 0.015:
            ndc, drug_name, unit_cost = DRUG_CLASS["SPECIALTY-IMM"][int(rng.integers(0, 2))]
            for yr in range(cfg.start_year, cfg.start_year + cfg.n_years):
                n_fills = int(rng.integers(6, 13))
                for f in range(n_fills):
                    month = min(12, f + 1)
                    _emit_fill(mid, m["payer_id"], "SPECIALTY-IMM", ndc, drug_name,
                               unit_cost, yr, month, 30, prescriber)
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
# 2026 industry expansion: PA on pharmacy, LEIE sanctions, directory attestation,
# HRRP readmissions, Gravity SDOH, CAHPS, outreach, VBC attribution.
# ============================================================================

def gen_pharmacy_pa(rng: np.random.Generator, rx: pd.DataFrame,
                    providers: pd.DataFrame) -> pd.DataFrame:
    """PA decisions for GLP-1 and specialty drug fills.

    GLP-1 PA volume is currently the largest pharmacy-PA queue across MA + Commercial
    books [CIT:KFF-GLP1-SPEND-2025] [CIT:AMA-PA-SURVEY-2024].
    """
    if len(rx) == 0:
        return pd.DataFrame(columns=["pa_id", "member_id", "ndc_code", "drug_class",
                                     "submitted_at", "decision_at", "decision",
                                     "indication", "approval_rate_bucket", "plan_year"])
    pa_targets = rx[rx["glp1_flag"] | rx["specialty_drug_flag"]]
    if len(pa_targets) == 0:
        return pd.DataFrame()
    # One PA per (member, drug, year) — collapse fills.
    first_fills = (pa_targets.sort_values("fill_date")
                   .groupby(["member_id", "ndc_code", "plan_year"], as_index=False)
                   .first())
    rows = []
    for idx, r in first_fills.iterrows():
        is_glp1 = r["glp1_flag"]
        # Diabetes indication approves at ~88%; obesity at ~52% (highly variable by plan).
        indication = rng.choice(["diabetes", "obesity"], p=[0.62, 0.38]) if is_glp1 else "specialty"
        approval_p = {"diabetes": 0.88, "obesity": 0.52, "specialty": 0.74}[indication]
        decision = "approve" if rng.random() < approval_p else "deny"
        sub = pd.Timestamp(r["fill_date"]) - pd.Timedelta(days=int(rng.integers(2, 10)))
        tat_hours = float(rng.gamma(2.5, 28))
        rows.append({
            "pa_id": f"PHA-{idx:010d}",
            "member_id": r["member_id"],
            "ndc_code": r["ndc_code"],
            "drug_class": r["drug_class"],
            "submitted_at": sub.date(),
            "decision_at": (sub + pd.Timedelta(hours=tat_hours)).date(),
            "decision": decision,
            "indication": indication,
            "approval_rate_bucket": "high" if approval_p > 0.7 else "low",
            "plan_year": int(r["plan_year"]),
        })
    return pd.DataFrame(rows)


def gen_provider_sanctions(rng: np.random.Generator,
                           providers: pd.DataFrame) -> pd.DataFrame:
    """OIG-LEIE-style provider exclusion list. Federal health programs may not pay
    for items or services furnished by excluded individuals/entities [CIT:LEIE-OIG-2025].
    """
    excluded = providers[providers["leie_excluded_flag"]]
    if len(excluded) == 0:
        return pd.DataFrame(columns=["sanction_id", "provider_npi", "exclusion_type",
                                     "exclusion_date", "reinstatement_eligible_date",
                                     "source"])
    rows = []
    types = ["1128(a)(1)_program-related_conviction",
             "1128(b)(4)_license_revocation",
             "1128(b)(7)_fraud_kickbacks",
             "1128(a)(3)_felony_health_care_fraud"]
    for idx, p in excluded.iterrows():
        excl_date = date(2023 + int(rng.integers(0, 3)),
                         int(rng.integers(1, 13)), int(rng.integers(1, 28)))
        rows.append({
            "sanction_id": f"SAN-{idx:08d}",
            "provider_npi": p["provider_npi"],
            "exclusion_type": rng.choice(types),
            "exclusion_date": excl_date,
            "reinstatement_eligible_date": excl_date + timedelta(days=int(rng.integers(1825, 3650))),
            "source": "OIG-LEIE",
        })
    return pd.DataFrame(rows)


def gen_provider_directory_attestation(rng: np.random.Generator,
                                       providers: pd.DataFrame) -> pd.DataFrame:
    """NSA Section 116 requires verification at least every 90 days.

    We emit the most recent attestation per provider. ~12% are stale (>90 days),
    creating cost-sharing-protection liability [CIT:CMS-NSA-116-DIRECTORY].
    """
    today = date(2026, 6, 30)
    rows = []
    for _, p in providers.iterrows():
        is_stale = rng.random() < 0.12
        age_days = int(rng.integers(91, 240)) if is_stale else int(rng.integers(1, 90))
        last_verified = today - timedelta(days=age_days)
        rows.append({
            "provider_npi": p["provider_npi"],
            "attestation_method": rng.choice(["roster_file", "portal_attest", "outbound_call"],
                                             p=[0.55, 0.30, 0.15]),
            "last_verified_date": last_verified,
            "age_days": age_days,
            "stale_flag": is_stale,
            "directory_status": "active" if p["in_network_flag"] else "termed",
        })
    return pd.DataFrame(rows)


def gen_readmission(rng: np.random.Generator, claims_header: pd.DataFrame) -> pd.DataFrame:
    """30-day all-cause readmissions on HRRP cohorts [CIT:CMS-HRRP-2025].

    Approximated from inpatient claims; ~14.8% national baseline, varied by cohort.
    """
    inpatient = claims_header[claims_header["place_of_service"] == "21"].copy()
    if len(inpatient) == 0:
        return pd.DataFrame(columns=["readmit_id", "member_id", "index_claim_id",
                                     "hrrp_cohort", "index_dis_date", "readmit_date",
                                     "days_to_readmit", "readmit_within_30d",
                                     "plan_year"])
    rows = []
    for idx, c in inpatient.iterrows():
        cohort = rng.choice(HRRP_COHORTS, p=[0.18, 0.16, 0.24, 0.20, 0.12, 0.10])
        readmit_p = {"AMI": 0.17, "COPD": 0.20, "HF": 0.22, "PNEUMONIA": 0.16,
                     "CABG": 0.12, "THA_TKA": 0.05}[cohort]
        readmit = rng.random() < readmit_p
        days = int(rng.integers(2, 30)) if readmit else None
        rows.append({
            "readmit_id": f"RDM-{idx:010d}",
            "member_id": c["member_id"],
            "index_claim_id": c["claim_id"],
            "hrrp_cohort": cohort,
            "index_dis_date": c["service_date"],
            "readmit_date": (pd.Timestamp(c["service_date"]) + pd.Timedelta(days=days)).date()
                            if days else None,
            "days_to_readmit": days,
            "readmit_within_30d": readmit,
            "plan_year": c["plan_year"],
        })
    return pd.DataFrame(rows)


def gen_sdoh_assessment(rng: np.random.Generator, members: pd.DataFrame) -> pd.DataFrame:
    """Gravity Project SDOH domain captures (ICD-10 Z-codes Z55-Z65)
    [CIT:GRAVITY-SDOH-Z-CODES-2024].
    """
    domain_to_member_flag = {
        "food_insecurity":     "sdoh_food_insecure",
        "housing_instability": "sdoh_housing_unstable",
        "transport_barrier":   "sdoh_transport_barrier",
        "financial_strain":    None,
        "social_isolation":    None,
    }
    z_codes = {
        "food_insecurity":     "Z59.41",
        "housing_instability": "Z59.811",
        "transport_barrier":   "Z59.82",
        "financial_strain":    "Z59.86",
        "social_isolation":    "Z60.2",
    }
    rows = []
    for _, m in members.iterrows():
        capture_p = 0.18 if (m["hei_eligible_flag"] or m["lob"] == "Medicaid") else 0.06
        if rng.random() > capture_p:
            continue
        for domain, flag in domain_to_member_flag.items():
            base = bool(m[flag]) if flag else False
            positive = (base and rng.random() < 0.85) or (not base and rng.random() < 0.05)
            if not positive and rng.random() > 0.30:
                continue
            rows.append({
                "member_id": m["member_id"],
                "domain": domain,
                "assessment_date": date(2026, int(rng.integers(1, 13)), int(rng.integers(1, 28))),
                "positive_screen": positive,
                "z_code": z_codes[domain],
                "intervention_referred": positive and rng.random() < 0.62,
                "plan_year": 2026,
            })
    return pd.DataFrame(rows)


def gen_cahps_response(rng: np.random.Generator, members: pd.DataFrame) -> pd.DataFrame:
    """CAHPS member-experience survey response. Sample ~12% of MA members."""
    rows = []
    ma_members = members[members["lob"].isin(["MA", "Dual"])]
    sampled = ma_members.sample(frac=0.12, random_state=42) if len(ma_members) else ma_members
    for _, m in sampled.iterrows():
        rows.append({
            "response_id": f"CAHPS-{m['member_id']}-2026",
            "member_id": m["member_id"],
            "survey_year": 2026,
            "rating_health_plan": int(rng.integers(6, 11)),
            "rating_personal_doctor": int(rng.integers(6, 11)),
            "rating_specialist": int(rng.integers(5, 11)),
            "getting_needed_care": rng.choice(["always", "usually", "sometimes", "never"],
                                              p=[0.55, 0.32, 0.10, 0.03]),
            "getting_care_quickly": rng.choice(["always", "usually", "sometimes", "never"],
                                               p=[0.48, 0.34, 0.14, 0.04]),
            "customer_service": rng.choice(["always", "usually", "sometimes", "never"],
                                           p=[0.51, 0.33, 0.12, 0.04]),
        })
    return pd.DataFrame(rows)


def gen_outreach(rng: np.random.Generator, members: pd.DataFrame) -> pd.DataFrame:
    """Care-management outreach events (gap-closure, HEDIS reminders, post-discharge)."""
    rows = []
    for _, m in members.iterrows():
        n = int(rng.poisson(2.4 if m["lob"] in ("MA", "Dual") else 1.2))
        for _ in range(n):
            channel = rng.choice(["sms", "ivr", "live_call", "secure_msg", "letter"],
                                 p=[0.30, 0.22, 0.18, 0.20, 0.10])
            outcome = rng.choice(["completed", "no_response", "opted_out"],
                                 p=[0.42, 0.50, 0.08])
            rows.append({
                "member_id": m["member_id"],
                "outreach_date": date(2026, int(rng.integers(1, 13)), int(rng.integers(1, 28))),
                "channel": channel,
                "purpose": rng.choice(["hedis_gap", "post_discharge", "med_adherence",
                                       "awv_reminder", "sdoh_followup"]),
                "outcome": outcome,
                "plan_year": 2026,
            })
    return pd.DataFrame(rows)


def gen_vbc_attribution(rng: np.random.Generator, members: pd.DataFrame,
                        providers: pd.DataFrame) -> pd.DataFrame:
    """Member-to-VBC-provider attribution snapshots."""
    vbc_provs = providers[providers["vbc_contract_id"].notna()]
    if len(vbc_provs) == 0:
        return pd.DataFrame(columns=["member_id", "provider_npi", "vbc_contract_id",
                                     "attribution_method", "effective_year",
                                     "risk_arrangement"])
    rows = []
    for _, m in members.iterrows():
        # ~40% of MA + Medicaid members attributed; lower in Commercial.
        attrib_p = {"MA": 0.45, "Dual": 0.40, "Medicaid": 0.35, "Commercial": 0.18}[m["lob"]]
        if rng.random() > attrib_p:
            continue
        chosen = vbc_provs.sample(1, random_state=int(rng.integers(0, 2**31)))
        p = chosen.iloc[0]
        rows.append({
            "member_id": m["member_id"],
            "provider_npi": p["provider_npi"],
            "vbc_contract_id": p["vbc_contract_id"],
            "attribution_method": rng.choice(["plurality_pcp", "primary_care_visit", "assigned"],
                                             p=[0.55, 0.30, 0.15]),
            "effective_year": 2026,
            "risk_arrangement": p["vbc_risk_arrangement"],
        })
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

    print("[gen] pharmacy_pa...");           pha     = gen_pharmacy_pa(rng, rx, provs);                     pha.to_csv(out / "pharmacy_pa.csv", index=False)
    print(f"  -> {len(pha):,}")
    print("[gen] provider_sanctions...");    sanc    = gen_provider_sanctions(rng, provs);                  sanc.to_csv(out / "provider_sanctions.csv", index=False)
    print(f"  -> {len(sanc):,}")
    print("[gen] directory_attestation..."); attest  = gen_provider_directory_attestation(rng, provs);      attest.to_csv(out / "provider_directory_attestation.csv", index=False)
    print(f"  -> {len(attest):,}")
    print("[gen] readmission...");           rdm     = gen_readmission(rng, hdrs);                          rdm.to_csv(out / "readmission.csv", index=False)
    print(f"  -> {len(rdm):,}")
    print("[gen] sdoh_assessment...");       sdoh    = gen_sdoh_assessment(rng, members);                   sdoh.to_csv(out / "sdoh_assessment.csv", index=False)
    print(f"  -> {len(sdoh):,}")
    print("[gen] cahps_response...");        cahps   = gen_cahps_response(rng, members);                    cahps.to_csv(out / "cahps_response.csv", index=False)
    print(f"  -> {len(cahps):,}")
    print("[gen] outreach...");              outr    = gen_outreach(rng, members);                          outr.to_csv(out / "outreach.csv", index=False)
    print(f"  -> {len(outr):,}")
    print("[gen] vbc_attribution...");       vbc     = gen_vbc_attribution(rng, members, provs);            vbc.to_csv(out / "vbc_attribution.csv", index=False)
    print(f"  -> {len(vbc):,}")

    payers = ref["payers"]; payers.to_csv(out / "payers.csv", index=False)
    print(f"[gen] DONE -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

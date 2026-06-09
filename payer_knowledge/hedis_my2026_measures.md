# HEDIS MY2026 Measure Reference

Source: NCQA HEDIS MY2026 Volume 2 Technical Specifications [CIT:NCQA-HEDIS-MY2026]. Detailed measure rows in `data/reference/hedis_my2026_measures.csv`.

## Triple-weighted measures (Stars 2026)

These count 3x toward the contract-level Stars rating per CMS 2026 Tech Notes [CIT:CMS-STARS-2026-TN]:

| Measure | Description | Denominator |
|---|---|---|
| **CBP** | Controlling High Blood Pressure | Members 18-85 with HTN |
| **HBD** | Hemoglobin A1c Control for Diabetes | Members 18-75 with diabetes |
| **EED** | Eye Exam for Diabetics | Members 18-75 with diabetes |
| **MAH/MAD/MAC** | PDC ≥ 80% on hypertension / diabetes / cholesterol | Continuous Rx fills |

## Hybrid measures (require chart-chase)

- **COL** - Colorectal Cancer Screening
- **BCS-E** - Breast Cancer Screening
- **CCS** - Cervical Cancer Screening (revised MY2026 with HPV stand-alone test)
- **CDC-HBA1C** - HbA1c Control hybrid component

Hybrid measures pull supplemental data via TEFCA QHIN exchange where available [CIT:ONC-TEFCA-2024].

## Measure year vs rating year

Critical nuance for StarsAgent narration:
- **Measurement year (MY)** = year clinical events occur (e.g., MY2026)
- **Rating year (RY)** = year CMS publishes Stars (e.g., RY2028 uses MY2026 data)
- Cut-points published in CMS Tech Notes lag MY by 2 years

## Members reachable for closure

For "open gap" questions, members are *reachable* if:
- Active eligibility through closure window (typically 60-90 days remaining)
- No member opt-out flag on outreach
- Last contact within 12 months

The semantic model exposes `[HEDISMemberCount]` (denominator) and `[HEDISCompliantEvents]` (numerator); compliance % is `[HEDISCompliancePct]`.

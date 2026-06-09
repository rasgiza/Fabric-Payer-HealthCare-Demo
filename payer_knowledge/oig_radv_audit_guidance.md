# OIG MA Risk Adjustment Audit Guidance

Source: OIG Office of Inspector General Medicare Advantage RA audits [CIT:OIG-MA-RA-AUDIT-2024] + GAO MA improper-payment reports [CIT:GAO-MA-IMPROPER-2024].

## RADV (Risk Adjustment Data Validation) overview

CMS RADV is the formal audit process where a sample of submitted HCC diagnoses is validated against medical-record evidence. Findings can result in:

- Targeted recovery (PY-specific repayments)
- Extrapolated recovery (CMS finalized 2023 rule extending extrapolation to all RADV audits)
- OIG referral for civil/criminal action in egregious cases

## Top OIG findings (2022-2024)

The four highest-impact OIG findings on MA RA audits:

1. **Acute stroke** (HCC 100/V24 → HCC 100/V28) - frequently coded from imaging without supporting neuro encounter
2. **Major depressive disorder** (HCC 58 V24) - frequently coded without psychiatric evaluation
3. **Vascular disease** (HCC 108 V24) - dropped from V28 entirely
4. **Cancer historical codes** - "history of" codes used as active where Z-code applies

## Documentation gold standard (MEAT)

Every submitted HCC must be supported by:
- **M**onitor - current evaluation of the condition (labs, vitals, imaging)
- **E**valuate - clinical assessment in the note
- **A**ssess - medical decision-making documented
- **T**reat - active treatment plan (medication, referral, etc.)

A diagnosis with only "history of" or appearing only on a problem list **fails MEAT** and is unsupported.

## Audit-risk score (calculated)

The `Audit-Risk Score` measure (concept; built from claim-level signals):
- % of submitted HCCs with no qualifying encounter type within the data-collection year
- % of HCCs that historical years coded but current year did not (suspects implying intermittent under-coding)
- % of HCCs concentrated in <3 providers per member (single-provider risk)

Higher = greater RADV exposure.

## Agent guidance

- When asked "which providers have the highest unsupported diagnosis rate" - report the % only; never name a provider as "fraudulent" (that's a legal conclusion).
- When asked to "add HCC X to all diabetic members" - REFUSE and cite OIG audit risk.
- Improper payment estimates use the 6-7% national MA improper-payment baseline [CIT:GAO-MA-IMPROPER-2024] as the floor for narration.

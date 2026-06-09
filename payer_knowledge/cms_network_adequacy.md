# CMS Network Adequacy Standards

Source: CMS network adequacy rules + CY2024 Medicare Advantage updates.

## Time-and-distance (T&D) standards

CMS sets time-and-distance standards by provider type and county classification. NetworkAgent uses these for adequacy assessment.

### County classifications
- **Large Metro** - core-based statistical areas with population >1M
- **Metro** - 250K-1M
- **Micro** - 50K-250K
- **Rural** - non-CBSA

### Sample standards (PCP)
| County type | Max time (min) | Max distance (mi) | Min providers |
|---|---|---|---|
| Large Metro | 10 | 5 | 2 |
| Metro | 15 | 10 | 2 |
| Micro | 30 | 20 | 2 |
| Rural | 40 | 30 | 1 |
| CEAC | 70 | 60 | 1 |

(Specialist standards looser; oncology/cardiology/etc. each have their own table.)

## Provider-types covered (50+)

Primary Care, Allergy, Cardiology, Dermatology, ENT, Gastroenterology, General Surgery, Gynecology, Infectious Diseases, Nephrology, Neurology, Neurosurgery, OB-GYN, Oncology - Medical/Hematology, Oncology - Radiation/Surgical, Ophthalmology, Orthopedic Surgery, Otolaryngology, Plastic Surgery, Psychiatry, Pulmonary, Rheumatology, Urology, Vascular Surgery, Hospital - Acute, Hospital - Critical Access, Hospital - Psychiatric, ASC, SNF, Home Health, Hospice, ESRD, ...

## Adequacy testing

Per Medicare Advantage Provider Directory and Network Adequacy rules, plans must:
1. File HSD (Health Service Delivery) tables annually
2. Meet T&D in ≥90% of beneficiaries per county-by-provider-type cell
3. Submit corrective action plans for any failing cells

## Agent guidance

- Use `[InNetworkClaimsPct]` as proxy for in-network utilization (not a replacement for HSD adequacy testing).
- For "are we adequate" questions, narrate at the county+specialty cell level when possible.
- Refuse to estimate adequacy without authoritative provider-directory data; route to NetworkOps team.

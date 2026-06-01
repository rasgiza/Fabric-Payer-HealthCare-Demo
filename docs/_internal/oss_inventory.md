# OSS Inventory — lift vs author decisions

Per Phase 0c step 12. For each open-source asset we depend on, decide whether to **LIFT** (use as-is or with light adaptation) or **AUTHOR** (build new, possibly seeded by reading the OSS as reference).

| Asset | URL | License | Decision | Rationale |
|---|---|---|---|---|
| **sempy_labs report examples** | github.com/microsoft/semantic-link-labs | MIT | **LIFT** | Phase 4 — adopt their `report` API patterns directly for scripted page/visual creation. |
| **fabric-samples healthcare accelerator** | github.com/microsoft/fabric-samples | MIT | **LIFT (reference)** | Read for medallion patterns, KQL update-policy templates; not used as-is because it is provider-shaped. |
| **NCQA HEDIS value sets (VSAC/NLM)** | vsac.nlm.nih.gov | NLM Use Agreement | **LIFT** | Use VSAC OIDs to build `dim_hedis_value_set`; do not redistribute the value-set definitions, only OID references. |
| **Synthea base** | github.com/synthetichealth/synthea | Apache-2.0 | **LIFT** | Phase 1 — base patient/encounter generator. |
| **Synthea payer-export module** | github.com/synthetichealth/synthea/wiki/Module-Builder | Apache-2.0 | **LIFT (reference) + AUTHOR** | Lift the module pattern; author payer-overlay (claims/auth/appeals/RA/quality) ourselves because Synthea's payer module is too thin for our shape. |
| **public CMS-HCC V28 + RxHCC crosswalks** | cms.gov/medicare/health-plans/medicareadvtgspecratestats/risk-adjustors-items/cms-hcc-software | CMS public-use | **LIFT** | Phase 1 step 5 — direct download of the V28 mapping table; no transformation. [CIT:CMS-HCC-V28-2026] |
| **CARC / RARC code lists** | x12.org / wpc-edi.com | X12-licensed; WPC public reference | **LIFT (public values)** | Build `dim_carc` from the publicly-published code list; do not include any X12 implementation guide content. |
| **CMS Stars cut-point CSVs** | cms.gov/medicare/health-plans/medicareadvtgspecratestats/medicare-advantagepart-d-contract-and-enrollment-data | CMS public-use | **LIFT** | Phase 1 step 6 — seed Stars rollup with current published cut-points. [CIT:CMS-STARS-2026-TN] |
| **Sample 837/835 EDI files (test data)** | washington-publishing-co (sample files) | sample / educational | **AUTHOR** | We synthesize 837/835-shaped flat tables in `gen_payer_overlay.py` rather than carrying raw EDI; closer to gold-schema fit. |
| **NHCAA cost-of-fraud reports** | nhcaa.org | report (licensed) | **CITE ONLY** | Reference in `citations.yaml`, never redistribute. [CIT:NHCAA-FRAUD-COST] |
| **fabric-cicd** | pypi.org/project/fabric-cicd | MIT | **LIFT** | Phase 7 — primary deployment tool. |
| **fabric-launcher** | github.com/microsoft/fabric-launcher | MIT | **LIFT** | Phase 7 — launcher pattern lifted from prior phase2 work. |
| **PQA measure specs** | pqaalliance.org | spec (licensed) | **CITE ONLY** | Reference; the actual numerator/denominator logic is implemented from public summary docs. [CIT:PQA-MEASURES-2025] |
| **HCP-LAN APM framework** | hcp-lan.org | public framework | **LIFT (categorization only)** | Use category 1–4 nomenclature; cite primary source. [CIT:HCP-LAN-APM-2024] |
| **AMA prior-auth survey data** | ama-assn.org | report (licensed summaries available) | **CITE ONLY** | Cite published headline numbers. [CIT:AMA-PA-SURVEY-2024] |
| **fabric-samples GraphQL example** | github.com/microsoft/fabric-samples | MIT | **LIFT (reference)** | Phase 3 ontology agent — pattern for graph traversal. |
| **OIG Work Plan** | oig.hhs.gov/reports-and-publications/workplan | public | **CITE ONLY** | Drives SIU pain points and refusal framing. [CIT:OIG-WORKPLAN-2025] |
| **GAO MA improper-payment reports** | gao.gov | public | **CITE ONLY** | Drives RA improper-payment narrative. [CIT:GAO-MA-IMPROPER-2024] |
| **CMS-0057-F final rule text** | federalregister.gov | public | **CITE ONLY** | UM agent grounding. [CIT:CMS-0057-F] |
| **CMS NSA IDR public reports** | cms.gov/nosurprises | public | **CITE ONLY** | CFO and Network agent grounding. [CIT:CMS-NSA-IDR-2025] |
| **NCQA HEDIS MY2026 spec** | ncqa.org | spec (licensed) | **CITE ONLY** | Stars + RA agent grounding (numerator/denominator implementations done from public summaries). [CIT:NCQA-HEDIS-MY2026] |

## Licensing posture

- This repo is **Apache-2.0** (Phase 0a decision).
- All **LIFT** items above are MIT, Apache-2.0, or government public-use — compatible with redistribution under Apache-2.0.
- All **CITE ONLY** items are referenced via citation IDs; no content is redistributed.
- All **AUTHOR** items are original work in this repo.

## Open items

- VSAC OID redistribution rules — confirm with NLM that publishing OIDs (not value contents) in `citations.yaml` is permitted; current assumption: yes (OIDs are public identifiers).
- CARC code list redistribution — using only the publicly-published code-and-description, never X12 IG narrative; assumed safe.

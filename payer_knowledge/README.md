# payer_knowledge

Foundry Knowledge Base for the 7 payer data agents. Phase 7 indexes this folder
via Azure AI Search and attaches it to each agent as a `knowledge_source` per
`data_agents/<Agent>.DataAgent/binding.yaml`.

Authoritative reference data lives in CSV form under `data/reference/` (used at
ETL time and surfaced as dim tables in the gold layer). The markdown docs in
this folder add industry framing, definitions, and citation context that the
agents need at narration time.

## Inventory

| Doc | Used by | Source |
|---|---|---|
| carc_reference.md | CFOAgent, SIUAgent | data/reference/carc_codes.csv + WPC X12 |
| hfma_glossary.md | CFOAgent | HFMA RCM Outlook 2025 [CIT:HFMA-RCM-OUTLOOK-2025] |
| hedis_my2026_measures.md | StarsAgent | data/reference/hedis_my2026_measures.csv + NCQA HEDIS MY2026 Vol 2 |
| stars_2026_cutpoints.md | StarsAgent | data/reference/cms_stars_2026_cutpoints.csv + CMS 2026 Tech Notes |
| hcc_v28_weights.md | RiskAdjustmentAgent | data/reference/hcc_v28_sample.csv + CMS-HCC V28 Announcement |
| oig_radv_audit_guidance.md | RiskAdjustmentAgent | OIG MA RA audit reports [CIT:OIG-MA-RA-AUDIT-2024] |
| nhcaa_fraud_schemes.md | SIUAgent | NHCAA fraud cost reports [CIT:NHCAA-FRAUD-COST] |
| kff_high_cost_methodology.md | CareMgmtAgent | KFF high-cost member analysis [CIT:KFF-HIGH-COST-2024] |
| sdoh_hcp_lan_framework.md | CareMgmtAgent | HCP-LAN APM framework + SDOH integration |
| hcp_lan_apm_framework.md | NetworkAgent | HCP-LAN APM categories [CIT:HCP-LAN-APM-2024] |
| cms_network_adequacy.md | NetworkAgent | CMS time-and-distance standards |
| cms_0057_f_pa_rule.md | UMAgent | CMS-0057-F PA Interop Final Rule [CIT:CMS-0057-F] |
| ama_prior_auth_survey.md | UMAgent | AMA prior-auth survey [CIT:AMA-PA-SURVEY-2024] |

All citation IDs resolve to entries in `citations.yaml` at the repo root.

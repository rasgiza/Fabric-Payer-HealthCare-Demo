# CARC / RARC Reference

Authoritative CARC code list lives in `data/reference/carc_codes.csv` and is loaded into `dim_carc` at silver-stage ETL.

## High-impact CARC families (used by CFOAgent + SIUAgent)

### Missing-information family (CARC 16, 50, 197)
- **16** - Claim/service lacks information or has submission/billing error(s).
- **50** - These are non-covered services because this is not deemed a 'medical necessity' by the payer.
- **197** - Precertification/authorization/notification/pre-treatment absent.

These three drive >40% of denied dollars on professional claims per [CIT:CHC-DENIAL-INDEX-2025]. The semantic model exposes `[MissingInfoDenials]` filtered to CARC IN {"16","50","197"}.

### Coverage / eligibility family
- **22** - This care may be covered by another payer per coordination of benefits.
- **24** - Charges are covered under a capitation agreement/managed care plan.
- **27** - Expenses incurred after coverage terminated.

### Payment integrity family (used by SIUAgent)
- **96** - Non-covered charge(s).
- **B16** - 'New Patient' qualifications were not met.
- **B7** - This provider was not certified/eligible to be paid for this procedure/service on this date of service.

## Appeal overturn benchmarks
- Industry overturn rate on appealed denials: 41-56% [CIT:CHC-DENIAL-INDEX-2025].
- Peer-to-peer overturn on PA denials: ~39% [CIT:AMA-PA-SURVEY-2024].

## Agent guidance
- Always cite the canonical CARC short text from `dim_carc` not paraphrased descriptions.
- For multi-CARC denials, group by **primary** CARC; note secondary in narration.
- Never recommend a recoding action; route to revenue-integrity workflow instead.

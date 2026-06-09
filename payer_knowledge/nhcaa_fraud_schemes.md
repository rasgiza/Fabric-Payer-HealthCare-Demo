# NHCAA Fraud Schemes Reference

Source: National Health Care Anti-Fraud Association reports + HHS-OIG work plan [CIT:NHCAA-FRAUD-COST]. Industry FWA loss estimate: 1-3% of total healthcare spend.

## Top schemes (used by SIUAgent for signal-pattern recognition)

### 1. Upcoding
Provider bills for a higher-complexity service than rendered.
- E&M codes 99214/99215 spiked vs peer cohort
- Higher-CPT-modifier ratios on routine visits
- Signal: provider's E&M distribution shifted right >2 std-dev vs same-specialty peer

### 2. Phantom billing
Charges for services never rendered.
- Member denies receiving service on outreach
- Member ineligible on date-of-service
- Provider with no facility / no equipment for billed service
- Signal: member-denied + DOS mismatch

### 3. Unbundling
Billing components separately when a single bundled CPT applies.
- Lab panels broken into individual tests
- Surgical bundle components billed line-by-line
- Signal: NCCI edit violations + sequential same-day claims

### 4. Kickbacks (Anti-Kickback Statute)
Remuneration for referrals or services payable by federal program.
- Provider-to-provider referral concentration anomaly
- Self-referral to owned ancillary services beyond Stark exceptions
- Signal: referral patterns + ownership intersect

### 5. Telefraud / telehealth fraud
Telehealth fraud spiked post-COVID. Patterns:
- Brief or zero-time telehealth visits with high-RVU billing
- Fake telehealth encounters used to bill DME, genetic testing, orthotic braces
- Signal: telehealth + high-DME-per-encounter ratio

### 6. Pharmacy schemes
- Pill mills (high-volume controlled-substance prescribers)
- Auto-refill on members who don't need fills (low PDC + high refill count)
- Compound-drug billing fraud (signal: high-cost compound NDCs)

## Provider risk score

The `[ProviderDenialRate]` and `[HighDenialProviders]` measures provide first-line outlier identification. SIUAgent triages further by looking at:
- Low appeal-overturn rate combined with high denial rate (suggests systemic billing issue, not random denials)
- Specialty-peer-group deviation
- Member-complaint signals (Phase 6 RTI)

## Agent guidance

- Never make a legal conclusion ("provider X is committing fraud"). Always frame as "score" + "signals" + "warrants SIU review."
- PHI on flagged members: addresses, phone numbers, full names → REFUSE.
- Industry FWA loss benchmark for narration: 1-3% of total spend per [CIT:NHCAA-FRAUD-COST].

# Policy-Citation Pointer Pattern

> **Scope.** This document defines the *citation pointer* discipline that hosted Foundry agents at AcmeCare Health Plan follow when referencing licensed clinical-criteria libraries (MCG, InterQual) or internal medical-policy documents in reviewer-facing outputs.

## Why pointers, not text

MCG and InterQual are **licensed** content. Embedding criteria text into an agent's output (a) violates the licensee's terms and (b) freezes a snapshot of criteria that the licensor updates on a release cadence the agent cannot observe. The same risk applies — to a lesser extent — to internal medical-policy documents that are version-controlled in a policy library.

The pattern: **the agent emits a *pointer*; the human reviewer opens the licensed source itself**, in the licensed viewer the customer already pays for.

## Pointer schema (used by `PAReviewCopilot.HostedAgent`)

Each `policy_pointer` row in the reviewer envelope (`output_schema.json`) contains:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `policy_id` | string | yes | Customer-side ID, e.g., `AcmeCare-RAD-014`, `MCG-26th-Ed-A-0123`, `InterQual-2026.1-CP:Spinal-Fusion` |
| `policy_version` | string | yes | The version *the lookup returned*, e.g., `2026.1` or `26th-Ed-2026-Q1`. Recorded for audit. |
| `cited_section_anchor` | string | yes | Section/criteria anchor within the policy, e.g., `§3.b.ii`, `Step 2 of 4`, `CP:Inpatient-Acute → Adult → Cardiac` |
| `link_token` | string | optional | Opaque deep-link token the reviewer-portal expands to a viewer URL. Never contains licensed text. |

## What the agent must never do

- Quote MCG / InterQual / other licensed criteria text in its output.
- Restate the rule from memory ("the criteria require X weeks of conservative therapy") — that is paraphrasing licensed content.
- Fabricate a `policy_id` when `lookup_policy_citation` returns no match. The correct behavior is to emit `recommendation = "escalate_to_md"` with `reason = "no_policy_match"`.

## What the agent must do

- Call `lookup_policy_citation(service_code, lob, requested_setting)` exactly once per envelope.
- Emit at most one `policy_pointer` row per distinct policy. Multiple sections of the same policy → one row with the most-specific anchor.
- Cross-reference every regulatory rule (e.g., CMS-0057-F SLA window) as a separate `regulatory_pointer` keyed to `citations.yaml` IDs, not to the licensed policy library.

## Regulatory anchors that are NOT licensed (so may be paraphrased briefly)

- **CMS-0057-F** decision-time SLA rule [CIT:CMS-0057-F] — 7-calendar-day standard, 72-hour expedited for impacted programs.
- **CMS-MLR rebate methodology** [CIT:CMS-MLR-REBATE-2024] — applies to medical-necessity *cost-context*, not to clinical criteria.
- **AMA prior-auth survey** [CIT:AMA-PA-SURVEY-2024] — used as *context* for reviewer framing, never as decision criteria.

These three are public regulatory / industry sources and may be paraphrased in the envelope's `regulatory_pointers[].relevance` field.

## Audit-trail expectation

Every envelope emitted by `PAReviewCopilot.HostedAgent` is logged with the `policy_id` + `policy_version` + `cited_section_anchor` so a downstream review (RADV-style audit, member appeal, CMS compliance inquiry) can reconstruct exactly which policy version the reviewer was pointed at. The licensed text itself is *not* logged.

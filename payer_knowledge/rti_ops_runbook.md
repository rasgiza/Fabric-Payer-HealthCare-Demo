# RTI Ops Runbook (PayerRT_Copilot knowledge source)

This is the operator-facing runbook for the **AcmeCare Real-Time Insights (RTI) ops desk**. It is the only non-regulatory document `PayerRT_Copilot` is grounded against and is intentionally short -- the copilot's job is to read live KQL windows, not to recite policy. Operator-facing language matches the field names emitted by NB_RTI_02 / NB_RTI_03 / NB_RTI_04 so a copilot envelope is byte-comparable to a dashboard cell.

## Persona map

| Persona  | Live KQL source notebook            | Live KQL table            | Activator rule it backs        |
|----------|-------------------------------------|---------------------------|--------------------------------|
| UM       | NB_RTI_02_PA_Latency                | `auth_lifecycle`          | `pa_denial_rate_spike`         |
| CareMgmt | NB_RTI_03_ADT_Outreach              | `adt_admissions`          | (none -- copilot-only path)    |
| SIU      | NB_RTI_04_SIU_Intake_Scoring        | `claim_arrivals`          | `siu_intake_score_alert`       |

If the operator's question doesn't map to a persona above, the copilot must classify `persona="Unknown"` and `recommendation="monitor"`.

## Recommendation map

The 4-value `recommendation` enum is intentionally non-adjudicative. Mapping rules:

- `dispatch_outreach`     -> CareMgmt only. Triggers an outreach work-item, never an automated call.
- `open_pa_investigation` -> UM only. Routes to **PA-Latency-Audit**, NOT a denial path. Requires `CMS-0057-F` regulatory pointer.
- `open_siu_case`         -> SIU only. Creates an **SIU-Intake-Triage** work-item; never opens a fraud case directly.
- `monitor`               -> any persona. Either no signal in window or the signal is below the rule threshold.

## Window conventions

- All `lookback_min` values are integer minutes, 15..1440. Default per persona:
  - UM:       240 (4h) -- aligns with NB_RTI_02 default.
  - CareMgmt: 180 (3h) -- aligns with NB_RTI_03 default.
  - SIU:       60 (1h) -- aligns with NB_RTI_04 default.
- `is_expedited=true` filters UM evidence to the 72h SLA cohort (per CMS-0057-F). When the operator names "urgent" / "expedited" / "STAT", set `is_expedited=true`.

## Threshold defaults

| Field                | Default | Mirror of                          |
|----------------------|---------|------------------------------------|
| `score_threshold`    | 0.6     | NB_RTI_04 parameter                |
| PA breach_rate cut   | 0.20    | Activator `pa_denial_rate_spike`   |
| PA min decisions     | 50      | Activator `pa_denial_rate_spike`   |
| CareMgmt gap count   | 5       | RUNBOOK convention                 |

If the operator overrides any of these, surface the override verbatim in `rationale_snippets`.

## PHI minimization

The copilot's evidence block returns aggregate counts and percentiles only. No `member_id`, `provider_id`, `payer_id`, `claim_id`, or facility name is ever included in the envelope -- the operator drills into those via the work-item, not via the copilot reply. If a delegating-tool reply contains an identifier, drop it before emitting.

## Routing targets (operator system)

| `routing_targets[].channel`    | `routing_targets[].work_item` | When                                                  |
|--------------------------------|-------------------------------|-------------------------------------------------------|
| `UM Director Teams`            | `PA-Latency-Audit`            | UM + `open_pa_investigation`                          |
| `CareMgmt Outreach Queue`      | `ADT-72h-Followup`            | CareMgmt + `dispatch_outreach`                        |
| `SIU Triage Queue`             | `SIU-Intake-Triage`           | SIU + `open_siu_case`                                 |
| (none)                         | (none)                        | Any persona + `monitor`                               |

Channels are queues, never individuals. If the operator asks for a person, decline and route to the queue.

## Out-of-scope

If the question concerns:
- A specific PA case at decision time -> escalate to `PAReviewCopilot`.
- Member-level care-plan ownership -> delegate via `ask_care_mgmt_agent`.
- Provider pattern history -> delegate via `ask_siu_agent`.
- Finance / Stars / Network -> `persona="Unknown"`, `reason="out_of_rti_scope"`.

## Regulatory hooks

- `CMS-0057-F` -- decision-time SLA framing for UM. MUST be in `regulatory_pointers` whenever `recommendation="open_pa_investigation"`.
- All other citations are optional and must resolve in `citations.yaml`.

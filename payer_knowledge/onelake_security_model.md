# OneLake security model — primer for the Payer demo

This is the security primer the demo's agents cite when asked
*"who can see this data?"* It is descriptive of how this repo lays out
OneLake permissions, not a generic Microsoft Fabric security tutorial.

## Three permission layers (in order of evaluation)

| Layer | Granularity | Where granted | Demo default |
|---|---|---|---|
| **Workspace role** | Workspace-wide | Fabric workspace settings | Admin: deploy SP only. Member: BI devs. Contributor: agent devs. Viewer: read-only analysts. |
| **Item permission** | Per item (lakehouse / SM / agent) | Item share dialog | Each lakehouse shared explicitly; SM "Read + Build" granted to BI users; data agents shared to persona group. |
| **OneLake RBAC** | Per folder under `Files/`, per table under `Tables/` | OneLake data access roles | Persona-scoped read on `lh_gold_curated.Tables/*`; deny on `lh_bronze_raw.Tables/*` for analysts. |

A request that fails ANY of the three layers is denied. The narrowest
layer wins. This is the same evaluation order whether the caller is a
notebook, a Power BI report, a Fabric data agent, or a Foundry hosted
agent calling via project MSI.

## Lakehouse separation in this demo

The demo deliberately uses four lakehouses (not one) so that role-based
access matches the medallion:

| Lakehouse | Sensitivity | Who reads it |
|---|---|---|
| `lh_bronze_raw` | High (raw PII surrogate keys present) | Deploy SP + medallion NBs only |
| `lh_silver_stage` | High | Medallion NBs only |
| `lh_silver_ods` | Medium | NB_03_Gold + audit tooling |
| `lh_gold_curated` | Lower (key columns hidden via SM, surrogate keys obscured) | Persona group reads via SM; data agents read directly for SQL surface |

A persona analyst group ("Payer-Stars-Analysts") gets:
- Workspace role: Viewer.
- Item perm: Read on `PayerAnalytics` SM, Read on `StarsAgent` data agent.
- OneLake RBAC: explicit deny on `lh_bronze_raw` / `lh_silver_*`,
  read on `lh_gold_curated.Tables/{fact_quality_event,agg_stars_compliance,dim_hedis_measure,...}`.

## Agent identity flow

All Foundry hosted agents in this repo authenticate with
**project managed identity** (`auth: project_msi` in `agent.yaml`). The
hosted agent then calls Fabric data agents via the Fabric Data Agent
Tool, which uses the Foundry project's MSI for OBO to the workspace.

```
End user (Entra)
   │
   ▼
Foundry hosted agent (PAReviewCopilot)
   │   project MSI = "fp_pa_reviewer_msi"
   │   Granted: Cognitive Services User on Foundry project,
   │            Member role on Fabric workspace (via group),
   │            OneLake RBAC read on policy KB blob (if needed)
   ▼
function-tool call → Fabric data agent (UMAgent)
   │   Uses project MSI's workspace permission
   ▼
DAX against PayerAnalytics SM
   │   SM enforces RLS roles
   ▼
Direct Lake read on lh_gold_curated
   │   OneLake RBAC checked
   ▼
Result rows
```

If the project MSI lacks ANY layer (workspace role, item permission,
OneLake folder/table RBAC), the call fails with a 403 at the lowest
denying layer — the agent sees an error envelope, not partial data.

## Sensitivity labels

Every artifact in [workspace/](../workspace/) inherits its sensitivity
from the lakehouse the SM Direct-Lake-binds to:
- `lh_bronze_raw` / `lh_silver_*` → **Highly Confidential / Internal** label.
- `lh_gold_curated` → **Confidential / Internal** label.
- `PayerAnalytics` SM → inherits Confidential from `lh_gold_curated`.
- Power BI reports → inherit Confidential from `PayerAnalytics`.
- `payer_knowledge/*.md` (Foundry IQ KB) → **Public** label
  (public sources only — CMS rules, AMA surveys, OIG guidance, etc.).

Sensitivity labels travel with the data when exported (CSV, XLSX, PDF
from Power BI). The labels are NOT a permission gate by themselves —
they are an information-protection signal that DLP policies act on.

## Row-Level Security (RLS) in the semantic model

`PayerAnalytics` SM ships with two RLS roles:
- **PayerScope**: filters `dim_payer[payer_id]` so an analyst sees only
  the payers in their assignment table.
- **StateScope**: filters `dim_geography[state]` so a regional analyst
  sees only their states.

The roles are inactive in dev (everyone sees everything for demo
clarity). The deploy script `tools/deploy.py --env prod` activates them
via `--enable-rls`.

## Audit replay

Every read on the gold lakehouse + every agent invocation is logged:
- Medallion writes → `lh_gold_curated.audit_log` (via NB_01/NB_02/NB_03 hooks).
- Agent calls → `data/lakehouse/<run_id>/audit/agent_calls/agent_calls.parquet`
  locally, or `lh_gold_curated.agent_calls` Delta in production.

Both logs capture `user_principal` (resolved from the calling identity),
`git_sha` (deploy version), and a SHA-256 of any prompt / response. This
is sufficient for an audit replay: given a `run_id`, the auditor can
reconstruct what each persona saw and how the agent responded.

See [tools/audit_log.py](../tools/audit_log.py) +
[tools/agent_audit.py](../tools/agent_audit.py) for the schema details.

## What this demo does NOT enforce (yet)

- **Customer-managed keys (CMK)** — uses platform-managed encryption.
  Customers who require CMK on the lakehouses must add a Key Vault
  reference at workspace creation time.
- **VNet egress** — workspace defaults to public endpoints. Customers
  who require private endpoints must enable workspace private link
  before running `tools/deploy.py`.
- **Purview integration** — sensitivity labels are applied but not yet
  pushed into a Purview scan. Phase 7 adds a Purview connector.

These are documented as Phase 7 follow-ups, not blockers for the Tier 3
jumpstart.

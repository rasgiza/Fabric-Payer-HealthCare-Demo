# Foundry IQ + Fabric IQ — Connection setup

This is the concrete setup for the two grounding surfaces in
[ARCHITECTURE_LAYERED.md](ARCHITECTURE_LAYERED.md). Both live in the
same Foundry project; they differ in connection type and binding.

Prerequisites:
- An Azure AI Foundry project (any region supporting
  `azure-ai-projects>=2.2.0`).
- A Fabric workspace deployed by `tools/deploy.py` (this repo).
- A managed identity ("project MSI") on the Foundry project with:
  - **Cognitive Services User** on the Foundry project resource.
  - **Member** on the Fabric workspace (so it can read SM, data agents,
    ontology, lakehouses).
  - **Reader** on the OneLake folders backing `payer_knowledge/`
    (for Foundry IQ KB ingest).

Run these via `DefaultAzureCredential` (az login locally, or workload
identity / pod identity in CI).

---

## Foundry IQ — `PAReviewCopilot` knowledge-source setup

Foundry IQ ingests unstructured Markdown / PDF / HTML into a Foundry
project's embedded vector store. The hosted agent then attaches the
store as a `knowledge_sources` list in its `agent.yaml`.

### 1. Upload `payer_knowledge/` to the project vector store

`tools/foundry_iq_setup.py` (Phase 3, forthcoming) wraps this. The
manual equivalent is:

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from pathlib import Path

project = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT"],
    credential=DefaultAzureCredential(),
)
kb_files = sorted(Path("payer_knowledge").glob("*.md"))
file_ids = [project.files.upload(p).id for p in kb_files]
store = project.vector_stores.create(
    name="payer_knowledge_v1",
    file_ids=file_ids,
)
print("vector_store_id =", store.id)
```

Pin the resulting `vector_store_id` in the Foundry project (one per
release tag — e.g., `payer_knowledge_v1`, `payer_knowledge_v2`).

### 2. Attach to PAReviewCopilot

Edit `data_agents/PAReviewCopilot.HostedAgent/agent.yaml`:

```yaml
knowledge_sources:
  - payer_knowledge/cms_0057_f_pa_rule.md
  - payer_knowledge/ama_prior_auth_survey.md
  # ... (the agent's deploy_data_agents.py resolves these to file_ids
  # against the pinned vector_store_id at deploy time)
```

`tools/deploy_data_agents.py` resolves the file paths to file IDs in
the vector store and passes them to the Foundry Responses API call.

### 3. Output schema enforcement

The hosted agent always returns the locked
`output_schema.json` envelope so groundedness ≥4 can be evaluated
offline:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["recommendation", "citations"],
  "properties": {
    "recommendation": {
      "enum": ["approve", "pend_for_p2p", "deny_for_criteria_not_met", "refuse"]
    },
    "citations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["doc", "section"],
        "properties": {"doc": {"type": "string"}, "section": {"type": "string"}}
      }
    }
  }
}
```

`tools/run_evals.py` asserts that every recommendation is in the enum
and every citation `doc` exists in `payer_knowledge/`.

---

## Fabric IQ — `PayerRT_Copilot` 3-connection setup

Fabric IQ is the `FabricIQPreviewTool` (`azure-ai-projects>=2.2.0`). It
exposes Fabric items to a hosted agent through three distinct
connection IDs, one per source kind. This separation enforces the
"binding cannot cross lanes" rule.

### Connection 1 — Ontology graph

```bash
az resource create \
  --resource-type "Microsoft.MachineLearningServices/workspaces/connections" \
  --name "conn-payer-ontology" \
  --parent "workspaces/<foundry-project>" \
  --resource-group "<rg>" \
  --properties "{
    \"category\": \"FabricGraph\",
    \"target\": \"<fabric-workspace-id>/ontologies/Payer_Ontology\",
    \"authType\": \"ManagedIdentity\"
  }"
```

Pin the resource ID into the project secrets as `CONN_ID_ONTOLOGY`.

### Connection 2 — Data-agent router

```bash
az resource create \
  --resource-type "Microsoft.MachineLearningServices/workspaces/connections" \
  --name "conn-payer-data-agents" \
  --parent "workspaces/<foundry-project>" \
  --resource-group "<rg>" \
  --properties "{
    \"category\": \"FabricDataAgentRouter\",
    \"target\": \"<fabric-workspace-id>\",
    \"authType\": \"ManagedIdentity\"
  }"
```

Pin as `CONN_ID_DATA_AGENT`. The router connection auto-discovers all
`*.DataAgent` items in the workspace (CFO, Stars, RA, SIU, CareMgmt,
Network, UM, ClaimsRawExplorer when added in Phase 4).

### Connection 3 — Semantic model (DAX surface)

```bash
az resource create \
  --resource-type "Microsoft.MachineLearningServices/workspaces/connections" \
  --name "conn-payer-analytics-sm" \
  --parent "workspaces/<foundry-project>" \
  --resource-group "<rg>" \
  --properties "{
    \"category\": \"FabricSemanticModel\",
    \"target\": \"<fabric-workspace-id>/semanticModels/PayerAnalytics\",
    \"authType\": \"ManagedIdentity\"
  }"
```

Pin as `CONN_ID_SEMANTIC_MODEL`.

### Wire the three connections into PayerRT_Copilot

`tools/fabric_iq_tool.py` (Phase 3, forthcoming) wraps this. The
manual equivalent:

```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FabricIQPreviewTool
from azure.identity import DefaultAzureCredential
import os

project = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT"],
    credential=DefaultAzureCredential(),
)
fabric_iq = FabricIQPreviewTool(
    connection_ids=[
        os.environ["CONN_ID_ONTOLOGY"],
        os.environ["CONN_ID_DATA_AGENT"],
        os.environ["CONN_ID_SEMANTIC_MODEL"],
    ],
)
agent = project.agents.create_agent(
    model="gpt-4.1-mini",
    name="PayerRT_Copilot",
    instructions=open(
        "data_agents/PayerRT_Copilot.HostedAgent/aiInstructions.md"
    ).read(),
    tools=fabric_iq.definitions,
    tool_resources=fabric_iq.resources,
)
```

Add `fabric_iq_preview` as the 4th entry in
`data_agents/PayerRT_Copilot.HostedAgent/tool_schemas.json` so
`tools/run_evals.py` can assert tool-call accuracy against it.

---

## RBAC matrix — least-privilege summary

| Identity | Foundry project | Fabric workspace | Lakehouse data | KB blob |
|---|---|---|---|---|
| Project MSI (PAReviewCopilot + PayerRT_Copilot) | Cognitive Services User | Member | OneLake Reader on `lh_gold_curated.Tables/*` only | Reader on `payer_knowledge/` |
| End user (Entra group "Payer-Ops") | none | none (delegated via OBO from the agent) | none directly | none directly |
| Deploy SP | Contributor on project resource | Admin (one-time) | none after deploy | Storage Blob Data Contributor (upload only) |

The end user never has direct RBAC on the data — they always go through
the hosted agent's project MSI. This makes audit replay
straightforward: every `lh_gold_curated.audit_log` row's
`user_principal` is the agent's MSI, and the upstream `agent_calls` row
captures the original Entra user via the OBO chain.

---

## Smoke test

After both connection setups complete, run:

```bash
python tools/run_evals.py --agent PAReviewCopilot
python tools/run_evals.py --agent PayerRT_Copilot
```

Both must return groundedness ≥4 and tool_call_accuracy ≥1 on every
case. If either fails, check the order: workspace role → item perm →
OneLake RBAC. The narrowest layer is the most common cause.

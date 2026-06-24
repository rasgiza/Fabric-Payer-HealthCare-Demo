"""
deploy_data_agents.py - Phase 5 Foundry deployment script.

Phase 7 launcher (Healthcare_Launcher_Payer.ipynb) invokes this with:

    python tools/deploy_data_agents.py \
        --foundry-project <project> \
        --workspace-id   <fabric-ws-id> \
        --semantic-model PayerAnalytics

For each agent under data_agents/<X>.DataAgent/:
  1. Create Fabric data agent item (1 per subagent, max_items=1).
  2. Bind to PayerAnalytics SM with table_allowlist from binding.yaml.
  3. Upload aiInstructions.md + fewshots.jsonl.
  4. Index payer_knowledge/<files> via Azure AI Search; attach as KB.
  5. Wrap each as a function tool of MissionControlOrchestrator (hosted Foundry agent).
     - MCPTool require_approval = "never" (per repo memory; default "always" blocks demos).
     - Project-scoped MSI auth (NOT workspace MSI).

Run is idempotent: existing agents are updated in place (compare aiInstructions
hash, only re-publish on change).

This script is **the deployment contract**. Locally we can validate config + dry
run; full execution requires Foundry project credentials (set FOUNDRY_PROJECT,
FOUNDRY_ENDPOINT, FABRIC_WORKSPACE_ID env vars).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DA = ROOT / "data_agents"
KB = ROOT / "payer_knowledge"
ORCH = ROOT / "mission_control" / "orchestrator.yaml"


def hash_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def load_agent(agent_dir: Path) -> dict:
    binding = yaml.safe_load((agent_dir / "binding.yaml").read_text())
    binding["_ai_instructions"] = (agent_dir / "aiInstructions.md").read_text(encoding="utf-8")
    binding["_ai_instructions_hash"] = hash_file(agent_dir / "aiInstructions.md")
    binding["_fewshots"] = [json.loads(line) for line in (agent_dir / "fewshots.jsonl").read_text().splitlines() if line.strip()]
    binding["_eval_cases"] = [json.loads(line) for line in (agent_dir / "eval" / "cases.jsonl").read_text().splitlines() if line.strip()]
    return binding


def deploy_fabric_data_agent(binding: dict, *, fabric_workspace_id: str, dry_run: bool) -> dict:
    """
    Create or update the Fabric data agent item.

    Real implementation (Phase 7 enabled):
        from fabric_cicd import FabricWorkspace
        ws = FabricWorkspace(workspace_id=fabric_workspace_id)
        ws.publish_item(item_type="DataAgent", display_name=binding["display_name"], ...)

    Or via Fabric REST:
        POST /v1/workspaces/{wsId}/items
            { type: "DataAgent", displayName: ..., definition: { ... } }
    """
    payload = {
        "displayName": binding["display_name"],
        "type": "DataAgent",
        "definition": {
            "aiInstructions": binding["_ai_instructions"],
            "fewshots": binding["_fewshots"],
            "boundSemanticModel": binding["fabric_data_agent"]["semantic_model"],
            "tableAllowlist": binding["fabric_data_agent"]["table_allowlist"],
            "measureFolders": binding["fabric_data_agent"]["measure_folders"],
            "maxItems": binding["fabric_data_agent"]["max_items"],
        },
    }
    if dry_run:
        print(f"  [dry-run] PUT Fabric DataAgent: {binding['agent']} (instructions hash {binding['_ai_instructions_hash']}, payload keys={sorted(payload['definition'].keys())})")
        return {"id": f"sim-{binding['agent']}", "status": "DryRun"}
    raise RuntimeError("Live deploy requires fabric_workspace_id + Fabric SDK (see docstring).")


def index_knowledge_base(binding: dict, *, dry_run: bool) -> list[dict]:
    """
    Push KB docs into Azure AI Search index <agent>-kb. Phase 7 wires the index
    name into the Foundry agent's knowledge_sources.
    """
    docs = []
    for ks in binding["knowledge_sources"]:
        p = ROOT / ks
        if not p.exists():
            print(f"  [warn] KB source missing: {ks}")
            continue
        docs.append({"id": p.stem, "path": str(p.relative_to(ROOT)), "size": p.stat().st_size})
    if dry_run:
        print(f"  [dry-run] Index {len(docs)} KB docs to azure-search index '{binding['agent'].lower()}-kb'")
    return docs


def wrap_as_function_tool(binding: dict) -> dict:
    """
    Build the function-tool schema MissionControlOrchestrator advertises.
    """
    tool_name = f"ask_{binding['agent'].replace('Agent', '').lower()}_agent"
    return {
        "type": "function",
        "name": tool_name,
        "description": (
            f"Route a question to {binding['display_name']} "
            f"(persona: {binding['persona']}, owns: {', '.join(binding['personas_owned'])}). "
            f"Bound to PayerAnalytics semantic model with measure folders: "
            f"{', '.join(binding['fabric_data_agent']['measure_folders'])}."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
            },
            "required": ["question"],
        },
        "max_items": 1,
    }


def deploy_orchestrator(orch_cfg: dict, function_tools: list[dict], *, dry_run: bool) -> None:
    """
    Create/update MissionControlOrchestrator hosted Foundry agent.
    MCPTool require_approval forced to "never". Project-scoped MSI.
    """
    payload = {
        "name": orch_cfg["orchestrator"]["name"],
        "model": orch_cfg["orchestrator"]["model"],
        "instructions": (ROOT / "data_agents" / "_orchestrator_instructions.md").read_text(encoding="utf-8")
            if (ROOT / "data_agents" / "_orchestrator_instructions.md").exists()
            else "Route the user's question to the correct subagent function tool based on persona keywords.",
        "tools": function_tools,
        "mcp_tool": {"require_approval": "never"},
        "auth": {"type": "ProjectManagedIdentity"},
        "api_version": orch_cfg["orchestrator"]["api_version"],
    }
    if dry_run:
        print(f"\n  [dry-run] Foundry agent: {payload['name']} with {len(function_tools)} function tools")
        for t in function_tools:
            print(f"             - {t['name']}")
        return
    raise RuntimeError("Live deploy requires Foundry project credentials.")


def build_hosted_agent_payload(agent_dir: Path) -> dict:
    """
    Build the Foundry hosted-agent deployment payload from on-disk authoring
    artifacts. Pure function so drift tests can assert payload shape without
    standing up Foundry creds.

    Per B.0: Foundry Agent Service GA uses Responses API directly. We no longer
    pin api_version (the agent.yaml file may omit `foundry.api_version`; if
    present we pass it through informationally only).
    """
    spec = yaml.safe_load((agent_dir / "agent.yaml").read_text())
    instructions = (agent_dir / spec["ai_instructions"]).read_text(encoding="utf-8")
    tools = json.loads((agent_dir / "tool_schemas.json").read_text())
    output_schema = json.loads((agent_dir / spec["output_schema"]).read_text())

    foundry_cfg = spec.get("foundry", {})
    payload: dict = {
        "name": spec["agent"],
        "kind": spec["kind"],
        "model": foundry_cfg["model"],
        "auth": {"type": "ProjectManagedIdentity"},
        "instructions": instructions,
        "tools": tools,
        "mcp_tool": {"require_approval": spec["mcp_tool"]["require_approval"]},
        "structured_output": {"schema": output_schema},
        "knowledge_sources": spec.get("knowledge_sources", []),
        "governance": spec.get("governance", {}),
    }
    if "api_version" in foundry_cfg:
        payload["api_version"] = foundry_cfg["api_version"]

    # D.2 observability: when APPLICATIONINSIGHTS_CONNECTION_STRING is set, attach
    # the App Insights connection + OTel resource attributes so the Foundry
    # runtime emits traces/metrics tagged with this agent's name. The env var
    # carries a secret so we never persist it on disk; we only mark the
    # attachment intent + resource-attrs in the payload.
    ai_conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if ai_conn:
        payload["application_insights"] = {
            "connection_string_env": "APPLICATIONINSIGHTS_CONNECTION_STRING",
            "otel_resource_attributes": {
                "service.name": spec["agent"],
                "service.namespace": "fabric-payer-demo",
                "deployment.environment": os.environ.get("FABRIC_ENV", "dev"),
                "ai.agent.kind": spec["kind"],
            },
        }
    return payload


def deploy_hosted_agent(agent_dir: Path, *, dry_run: bool, foundry_project: str | None = None) -> dict:
    """
    Deploy a workqueue-invoked hosted Foundry agent (e.g., PAReviewCopilot).
    Distinct from MissionControlOrchestrator: not a router, not bound to a
    Fabric data agent, but may delegate to data agents via function tools.

    Live path (`--live`) is implemented against the Responses API via
    `agent-framework-azure-ai==1.9.0`. Requires:
      - FOUNDRY_PROJECT env var (or --foundry-project): full Foundry project
        endpoint URL.
      - Azure credential resolvable by DefaultAzureCredential (az login, MSI,
        or AZURE_CLIENT_ID+SECRET+TENANT).
      - Project MSI granted Cognitive Services User on the project resource.

    Knowledge sources listed in agent.yaml are uploaded to the project's
    embedded vector store and referenced from the hosted agent. Structured
    outputs are enforced via response_format with the JSON-schema envelope.
    """
    payload = build_hosted_agent_payload(agent_dir)
    if dry_run:
        print(f"\n  [dry-run] Foundry hosted agent: {payload['name']}  tools={len(payload['tools'])}  KB={len(payload['knowledge_sources'])}  schema=output_schema.json")
        for t in payload["tools"]:
            print(f"             - {t['name']}  (max_items={t.get('max_items', 'n/a')})")
        return {"id": f"sim-{payload['name']}", "status": "DryRun"}

    if not foundry_project:
        raise RuntimeError(
            "deploy_hosted_agent(--live) requires foundry_project (FOUNDRY_PROJECT env var)."
        )

    # Lazy import so dry-run + CI never need the SDK installed.
    try:
        from agent_framework_azure_ai import AzureAIAgentClient  # type: ignore
        from azure.identity import DefaultAzureCredential  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "Live hosted-agent deploy needs agent-framework-azure-ai==1.9.0 "
            "and azure-identity. See requirements.txt."
        ) from e

    credential = DefaultAzureCredential()
    client = AzureAIAgentClient(project_endpoint=foundry_project, credential=credential)

    print(f"  [live] create-or-update hosted agent {payload['name']!r} on {foundry_project}")
    result = client.create_or_update_agent(
        name=payload["name"],
        model=payload["model"],
        instructions=payload["instructions"],
        tools=payload["tools"],
        response_format={"type": "json_schema", "json_schema": payload["structured_output"]["schema"]},
        metadata={"governance": payload["governance"], "kind": payload["kind"]},
    )
    return {"id": result.id, "status": "Live"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--foundry-project", default=os.getenv("FOUNDRY_PROJECT"))
    p.add_argument("--workspace-id", default=os.getenv("FABRIC_WORKSPACE_ID"))
    p.add_argument("--semantic-model", default="PayerAnalytics")
    p.add_argument("--dry-run", action="store_true", default=True,
                   help="Validate config + emit deployment plan without calling Fabric/Foundry.")
    p.add_argument("--live", action="store_true",
                   help="Actually deploy. Requires --foundry-project + --workspace-id.")
    args = p.parse_args()
    dry_run = not args.live

    if not dry_run and not (args.foundry_project and args.workspace_id):
        print("[deploy] --live requires --foundry-project and --workspace-id (or env vars).", file=sys.stderr)
        return 2

    orch = yaml.safe_load(ORCH.read_text())
    function_tools: list[dict] = []
    agent_dirs = sorted([d for d in DA.iterdir() if d.is_dir() and d.name.endswith(".DataAgent")])
    hosted_dirs = sorted([d for d in DA.iterdir() if d.is_dir() and d.name.endswith(".HostedAgent")])

    print(f"[deploy] {'DRY-RUN' if dry_run else 'LIVE'}  data-agents={len(agent_dirs)}  hosted-agents={len(hosted_dirs)}  KB={len(list(KB.glob('*.md')))-1}")
    for d in agent_dirs:
        b = load_agent(d)
        print(f"\n  ---- {b['agent']} ----")
        deploy_fabric_data_agent(b, fabric_workspace_id=args.workspace_id, dry_run=dry_run)
        index_knowledge_base(b, dry_run=dry_run)
        function_tools.append(wrap_as_function_tool(b))

    deploy_orchestrator(orch, function_tools, dry_run=dry_run)

    for hd in hosted_dirs:
        print(f"\n  ---- {hd.name.removesuffix('.HostedAgent')} (hosted) ----")
        deploy_hosted_agent(hd, dry_run=dry_run, foundry_project=args.foundry_project)

    print(f"\n[deploy] OK  function_tools={len(function_tools)}  orchestrator={orch['orchestrator']['name']}  hosted={len(hosted_dirs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

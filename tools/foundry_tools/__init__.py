"""
Function-tool stubs invoked by PAReviewCopilot (Foundry hosted agent).

These modules implement the two non-delegating tools declared in
`data_agents/PAReviewCopilot.HostedAgent/tool_schemas.json`:

  - `get_pa_packet(pa_id)` — fetch the structured PA packet for a case id.
  - `lookup_policy_citation(service_code, lob, requested_setting)` — resolve
    the governing medical-policy pointer (NOT licensed-criteria text).

The two delegating tools (`ask_um_agent`, `ask_risk_agent`) are NOT implemented
here: they route through Foundry's function-tool runtime to the upstream
Fabric DataAgents (`UMAgent`, `RiskAdjustmentAgent`) via project-scoped MSI.

Production wiring: deploy these stubs as a Foundry Custom MCP server hosted
on Azure Functions (`/runtime/webhooks/mcp`) and bind them to the hosted
agent. v1 ships the stubs so signatures + governance contracts are pinned
in source; v1.1 wires the real backends (claims DB for `get_pa_packet`,
policy library for `lookup_policy_citation`).
"""

from __future__ import annotations

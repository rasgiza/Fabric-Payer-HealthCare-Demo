"""
query_fabric_iq — Foundry function-tool stub for PayerRT_Copilot.

Schema source of truth: `data_agents/PayerRT_Copilot.HostedAgent/tool_schemas.json`.
The signature here MUST match the JSON-schema parameters declared there.

Wraps the Fabric IQ preview tool (`azure-ai-projects>=2.2.0` ships
`FabricIQPreviewTool`). At deploy time, `tools/fabric_iq_tool.py`
configures the underlying tool with three connection ids:
  * conn-payerrt-ontology      — Payer_Ontology Fabric Graph
  * conn-payerrt-data-agent    — Fabric data agent router (default UMAgent
                                 surface; routes to CareMgmtAgent + SIUAgent
                                 based on persona keywords)
  * conn-payerrt-semantic-model — PayerAnalytics semantic model surface

This stub returns a deterministic shell so dry-run envelopes validate
end-to-end. v1.1 wires the real Foundry runtime client.
"""

from __future__ import annotations

from typing import Any

_ALLOWED_SCOPES = {"ontology", "data_agent", "semantic_model", "all"}


def query_fabric_iq(question: str, scope: str) -> dict[str, Any]:
    """Issue an ontology-grounded question to FabricIQPreviewTool.

    Args:
        question: natural-language question; the IQ tool resolves entities
            and routes the query through the configured connections.
        scope: which IQ surface(s) to consult — one of ``ontology``,
            ``data_agent``, ``semantic_model``, or ``all``.

    Returns:
        Dict with keys: question, scope, entities_resolved, surfaces_consulted,
        answer_envelope, citations.

    PHI guardrail: the returned envelope must NEVER contain raw member or
    provider identifiers; the IQ tool is responsible for redacting them
    against the ontology's PHI tags. This stub returns an empty payload so
    the schema validates with no leak.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError(
            f"query_fabric_iq: question must be non-empty str, got {question!r}"
        )
    if scope not in _ALLOWED_SCOPES:
        raise ValueError(
            f"query_fabric_iq: scope must be one of {sorted(_ALLOWED_SCOPES)}, got {scope!r}"
        )
    return {
        "question": question,
        "scope": scope,
        "entities_resolved": [],
        "surfaces_consulted": [scope] if scope != "all" else sorted(_ALLOWED_SCOPES - {"all"}),
        "answer_envelope": {"text": "", "structured": {}},
        "citations": [],
    }

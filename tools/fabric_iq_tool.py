"""
fabric_iq_tool.py — thin wrapper around `azure-ai-projects.FabricIQPreviewTool`.

Phase 3 (G.3) deploy-time helper. PayerRT_Copilot's `query_fabric_iq` function
tool calls FabricIQPreviewTool with **three** connection ids to give the RTI
ops copilot a single grounded entry point covering ontology, data agents,
and the semantic model.

The three connection types — as documented in
``docs/FOUNDRY_CONNECTION_SETUP.md`` (Phase 1) — are:

* ``FabricGraph``         → Payer_Ontology Fabric Graph item (entity / relationship
                            resolution against the ontology built in Phase 2)
* ``FabricDataAgentRouter`` → routes a question to one of UMAgent / CareMgmtAgent
                              / SIUAgent based on persona keywords (replaces
                              the three ``ask_*_agent`` delegating tools at the
                              IQ-routing layer; the explicit tools remain as
                              the explicit fallback path)
* ``FabricSemanticModel``   → PayerAnalytics SM DAX surface (so IQ can pull
                              measure values like MeasureMLR / MeasurePMPM the
                              Phase 2 ontology entities expose)

The tool's connection ids are resolved from environment variables so the
Bicep/azd template can inject them at deploy time without baking them into
source:

    FABRIC_IQ_CONN_ONTOLOGY        — required
    FABRIC_IQ_CONN_DATA_AGENT      — required
    FABRIC_IQ_CONN_SEMANTIC_MODEL  — required

A ``--dry-run`` mode produces the configured ``FabricIQPreviewTool`` payload
without requiring ``azure-ai-projects`` to be installed; CI uses this to
lock the shape.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any

_REQUIRED_CONN_ENVS = (
    "FABRIC_IQ_CONN_ONTOLOGY",
    "FABRIC_IQ_CONN_DATA_AGENT",
    "FABRIC_IQ_CONN_SEMANTIC_MODEL",
)


@dataclass(frozen=True)
class FabricIqConfig:
    """Resolved connection bundle for one FabricIQPreviewTool instance."""

    ontology_connection_id: str
    data_agent_connection_id: str
    semantic_model_connection_id: str

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> FabricIqConfig:
        env = env if env is not None else dict(os.environ)
        missing = [name for name in _REQUIRED_CONN_ENVS if not env.get(name)]
        if missing:
            raise RuntimeError(
                f"fabric_iq_tool: missing required env vars {missing}. "
                "Set them from the azd template or `az resource create` output "
                "(see docs/FOUNDRY_CONNECTION_SETUP.md)."
            )
        return cls(
            ontology_connection_id=env["FABRIC_IQ_CONN_ONTOLOGY"],
            data_agent_connection_id=env["FABRIC_IQ_CONN_DATA_AGENT"],
            semantic_model_connection_id=env["FABRIC_IQ_CONN_SEMANTIC_MODEL"],
        )

    def to_payload(self) -> dict[str, Any]:
        """Shape attached to the hosted-agent deployment payload."""
        return {
            "tool_type": "FabricIQPreviewTool",
            "connections": [
                {"kind": "FabricGraph", "connection_id": self.ontology_connection_id},
                {"kind": "FabricDataAgentRouter", "connection_id": self.data_agent_connection_id},
                {"kind": "FabricSemanticModel", "connection_id": self.semantic_model_connection_id},
            ],
        }


def make_tool(config: FabricIqConfig | None = None) -> Any:
    """Return a configured ``FabricIQPreviewTool`` for the hosted agent runtime.

    Lazy-imports ``azure.ai.projects.models.FabricIQPreviewTool`` so this
    module loads cleanly in environments that don't have the preview SDK
    installed (CI, offline tests).
    """
    cfg = config or FabricIqConfig.from_env()
    try:
        from azure.ai.projects.models import FabricIQPreviewTool  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised only with the live SDK
        raise RuntimeError(
            "azure-ai-projects>=2.2.0 with FabricIQPreviewTool is not installed. "
            "Install it in the deploy environment or run with --dry-run."
        ) from exc

    return FabricIQPreviewTool(
        ontology_connection_id=cfg.ontology_connection_id,
        data_agent_connection_id=cfg.data_agent_connection_id,
        semantic_model_connection_id=cfg.semantic_model_connection_id,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Render the FabricIQPreviewTool configuration payload.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve config from env and print the payload JSON without instantiating the SDK class.",
    )
    args = p.parse_args(argv)

    try:
        cfg = FabricIqConfig.from_env()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    payload = cfg.to_payload()
    if args.dry_run:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    try:
        make_tool(cfg)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 3

    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

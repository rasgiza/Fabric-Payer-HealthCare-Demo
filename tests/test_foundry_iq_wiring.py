"""Phase 3 (G.3) — drift tests for FabricIQPreviewTool + Foundry IQ setup helpers.

These cover the two Phase 3 deploy-time modules without requiring the
``azure-ai-projects`` SDK or live Azure credentials:

* ``tools/fabric_iq_tool.py`` — config resolution from env vars + payload shape.
* ``tools/foundry_iq_setup.py`` — dry-run plan against PAReviewCopilot's
  on-disk ``agent.yaml`` ``knowledge_sources:`` list.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_fabric_iq_config_from_env_resolves_three_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import fabric_iq_tool

    monkeypatch.setenv("FABRIC_IQ_CONN_ONTOLOGY",       "conn-ont-1")
    monkeypatch.setenv("FABRIC_IQ_CONN_DATA_AGENT",     "conn-da-2")
    monkeypatch.setenv("FABRIC_IQ_CONN_SEMANTIC_MODEL", "conn-sm-3")
    cfg = fabric_iq_tool.FabricIqConfig.from_env()
    assert cfg.ontology_connection_id == "conn-ont-1"
    assert cfg.data_agent_connection_id == "conn-da-2"
    assert cfg.semantic_model_connection_id == "conn-sm-3"


def test_fabric_iq_config_from_env_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import fabric_iq_tool

    for v in ("FABRIC_IQ_CONN_ONTOLOGY", "FABRIC_IQ_CONN_DATA_AGENT", "FABRIC_IQ_CONN_SEMANTIC_MODEL"):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(RuntimeError, match="missing required env vars"):
        fabric_iq_tool.FabricIqConfig.from_env()


def test_fabric_iq_payload_lists_three_kinds() -> None:
    from tools import fabric_iq_tool

    cfg = fabric_iq_tool.FabricIqConfig(
        ontology_connection_id="o",
        data_agent_connection_id="d",
        semantic_model_connection_id="s",
    )
    payload = cfg.to_payload()
    assert payload["tool_type"] == "FabricIQPreviewTool"
    kinds = {c["kind"] for c in payload["connections"]}
    assert kinds == {"FabricGraph", "FabricDataAgentRouter", "FabricSemanticModel"}


def test_fabric_iq_dry_run_cli_prints_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import fabric_iq_tool

    monkeypatch.setenv("FABRIC_IQ_CONN_ONTOLOGY",       "o")
    monkeypatch.setenv("FABRIC_IQ_CONN_DATA_AGENT",     "d")
    monkeypatch.setenv("FABRIC_IQ_CONN_SEMANTIC_MODEL", "s")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fabric_iq_tool.main(["--dry-run"])
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert payload["tool_type"] == "FabricIQPreviewTool"
    assert len(payload["connections"]) == 3


def test_foundry_iq_setup_dry_run_plans_pareview_kb() -> None:
    from tools import foundry_iq_setup

    agent_dir = REPO_ROOT / "data_agents" / "PAReviewCopilot.HostedAgent"
    plan = foundry_iq_setup._plan_uploads(agent_dir)
    assert plan["agent_name"] == "PAReviewCopilot"
    assert plan["vector_store_name"] == "PAReviewCopilot_kb"
    assert len(plan["files"]) >= 1, "PAReviewCopilot must declare at least one knowledge_source"
    for f in plan["files"]:
        assert (REPO_ROOT / f["path"]).is_file(), f"missing file: {f['path']}"
        assert len(f["sha256"]) == 64, f"sha256 wrong length on {f['path']}"


def test_foundry_iq_setup_cli_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import foundry_iq_setup

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = foundry_iq_setup.main([])
    assert rc == 0
    out = buf.getvalue()
    assert "DRY-RUN plan for PAReviewCopilot" in out
    assert "vector_store_name: PAReviewCopilot_kb" in out


def test_foundry_iq_setup_apply_without_endpoint_returns_2(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools import foundry_iq_setup

    monkeypatch.delenv("AZURE_AI_PROJECT_ENDPOINT", raising=False)
    err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", err)
    rc = foundry_iq_setup.main(["--apply"])
    assert rc == 2
    assert "AZURE_AI_PROJECT_ENDPOINT" in err.getvalue()

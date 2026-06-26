"""C.5 drift tests -- PayerRT_Copilot hosted Foundry agent + 3 KQL stubs + live wiring.

Mirrors `tests/test_pareviewcopilot_shape.py`. Locks the deploy contract:
  - agent.yaml is on the Responses API (no api_version pin per B.0).
  - The 3 KQL function-tool stubs match `tool_schemas.json` parameters.
  - Delegating tools (`ask_um_agent`, `ask_care_mgmt_agent`, `ask_siu_agent`)
    reference DataAgent folders that actually exist under `workspace/`.
  - Cited regulatory ids (CMS-0057-F) resolve in `citations.yaml`.
  - Knowledge sources exist on disk.
  - `tools.deploy_data_agents.build_hosted_agent_payload()` produces the
    expected payload shape for this agent.
  - The live deploy path is import-clean (dry-run is the default).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = REPO_ROOT / "data_agents" / "PayerRT_Copilot.HostedAgent"


@pytest.fixture(scope="module")
def agent_yaml() -> dict:
    return yaml.safe_load((AGENT_DIR / "agent.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tool_schemas() -> list[dict]:
    return json.loads((AGENT_DIR / "tool_schemas.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def output_schema() -> dict:
    return json.loads((AGENT_DIR / "output_schema.json").read_text(encoding="utf-8"))


def test_agent_yaml_uses_responses_api(agent_yaml: dict) -> None:
    foundry = agent_yaml["foundry"]
    assert "api_version" not in foundry, (
        f"PayerRT_Copilot.agent.yaml still pins api_version={foundry.get('api_version')!r}. "
        "B.0 mandates Responses API (no api_version pin)."
    )
    assert foundry["model"] == "gpt-4.1-mini"
    assert foundry["auth"] == "project_msi"


def test_tool_stubs_match_schema(tool_schemas: list[dict]) -> None:
    """Each non-delegating tool in tool_schemas.json has a Python stub whose
    function signature matches the declared JSON-schema parameters."""
    from tools.foundry_tools import (
        get_emergency_admit_worklist,
        get_pa_latency_window,
        get_siu_suspect_claims,
        query_fabric_iq,
    )

    impls = {
        "get_pa_latency_window":        get_pa_latency_window.get_pa_latency_window,
        "get_emergency_admit_worklist": get_emergency_admit_worklist.get_emergency_admit_worklist,
        "get_siu_suspect_claims":       get_siu_suspect_claims.get_siu_suspect_claims,
        "query_fabric_iq":              query_fabric_iq.query_fabric_iq,
    }
    for schema in tool_schemas:
        name = schema["name"]
        if name not in impls:
            continue  # delegating tools route via Foundry, no Python stub
        fn = impls[name]
        sig_params = list(inspect.signature(fn).parameters)
        schema_params = list(schema["parameters"]["properties"].keys())
        assert sig_params == schema_params, (
            f"tool {name!r}: Python signature {sig_params} != schema params {schema_params}"
        )
        required = schema["parameters"].get("required", [])
        for r in required:
            assert r in sig_params, f"tool {name!r}: required schema param {r!r} missing from Python signature"


def test_get_pa_latency_window_validates() -> None:
    from tools.foundry_tools.get_pa_latency_window import get_pa_latency_window

    out = get_pa_latency_window(240, is_expedited=True)
    # PHI-minimization: aggregates and percentiles only
    forbidden = {"member_id", "member_hash", "provider_id", "auth_id"}
    assert not (forbidden & set(out.keys())), f"PHI leak: {forbidden & set(out.keys())}"
    assert set(["p50_hours", "p90_hours", "p99_hours", "breach_count", "breach_rate", "decisions"]).issubset(out.keys())
    with pytest.raises(ValueError, match="lookback_min"):
        get_pa_latency_window(0)
    with pytest.raises(ValueError, match="lookback_min"):
        get_pa_latency_window(2000)


def test_get_emergency_admit_worklist_validates() -> None:
    from tools.foundry_tools.get_emergency_admit_worklist import get_emergency_admit_worklist

    out = get_emergency_admit_worklist(720, priority_only="high")
    forbidden = {"member_id", "member_hash", "facility_id", "adt_event_id"}
    assert not (forbidden & set(out.keys())), f"PHI leak: {forbidden & set(out.keys())}"
    assert "without_outreach_count" in out
    with pytest.raises(ValueError, match="lookback_min"):
        get_emergency_admit_worklist(10)
    with pytest.raises(ValueError, match="priority_only"):
        get_emergency_admit_worklist(720, priority_only="critical")


def test_get_siu_suspect_claims_validates() -> None:
    from tools.foundry_tools.get_siu_suspect_claims import get_siu_suspect_claims

    out = get_siu_suspect_claims(60, score_threshold=0.6)
    forbidden = {"claim_id", "provider_id", "payer_id", "member_id"}
    assert not (forbidden & set(out.keys())), f"PHI leak: {forbidden & set(out.keys())}"
    assert "suspect_count" in out
    assert "max_intake_score" in out
    with pytest.raises(ValueError, match="lookback_min"):
        get_siu_suspect_claims(10, 0.6)
    with pytest.raises(ValueError, match="score_threshold"):
        get_siu_suspect_claims(60, 1.5)


def test_query_fabric_iq_validates() -> None:
    from tools.foundry_tools.query_fabric_iq import query_fabric_iq

    out = query_fabric_iq("what is current PA latency?", scope="all")
    forbidden = {"member_id", "member_hash", "provider_id", "auth_id", "claim_id"}
    leak = forbidden & set(out.keys())
    assert not leak, f"PHI leak in query_fabric_iq response: {leak}"
    assert out["scope"] == "all"
    assert set(out["surfaces_consulted"]) == {"ontology", "data_agent", "semantic_model"}
    assert "answer_envelope" in out and "citations" in out
    with pytest.raises(ValueError, match="question"):
        query_fabric_iq("", scope="all")
    with pytest.raises(ValueError, match="scope"):
        query_fabric_iq("x", scope="bogus")


def test_delegating_tools_resolve_to_existing_dataagents(agent_yaml: dict) -> None:
    """`ask_um_agent` -> UMAgent, `ask_care_mgmt_agent` -> CareMgmtAgent,
    `ask_siu_agent` -> SIUAgent. All three upstream DataAgents must exist
    as workspace items (B.3 shipped them)."""
    workspace = REPO_ROOT / "workspace"
    for tool in agent_yaml["tools"]:
        upstream = tool.get("upstream_agent")
        if not upstream:
            continue
        upstream_dir = workspace / f"{upstream}.DataAgent"
        assert upstream_dir.is_dir(), (
            f"agent.yaml tool {tool['name']!r} declares upstream_agent={upstream!r} "
            f"but {upstream_dir} does not exist under workspace/"
        )


def test_three_delegating_tools_present(agent_yaml: dict) -> None:
    """C.5 contract: copilot covers UM + CareMgmt + SIU. All three delegating
    tools must be wired."""
    upstreams = {t.get("upstream_agent") for t in agent_yaml["tools"] if t.get("upstream_agent")}
    assert upstreams == {"UMAgent", "CareMgmtAgent", "SIUAgent"}


def test_regulatory_citations_resolve(agent_yaml: dict) -> None:
    citations = yaml.safe_load((REPO_ROOT / "citations.yaml").read_text(encoding="utf-8"))
    ids = {c["id"] for c in citations["citations"]}
    assert "CMS-0057-F" in ids, "citations.yaml missing CMS-0057-F"


def test_knowledge_sources_exist(agent_yaml: dict) -> None:
    for ks in agent_yaml["knowledge_sources"]:
        p = REPO_ROOT / ks
        assert p.is_file(), f"knowledge_source missing on disk: {ks}"


def test_rti_runbook_is_a_knowledge_source(agent_yaml: dict) -> None:
    """C.5 ships payer_knowledge/rti_ops_runbook.md as a new KB doc dedicated
    to this copilot. Locking the wiring prevents accidental KB drift."""
    assert "payer_knowledge/rti_ops_runbook.md" in agent_yaml["knowledge_sources"]


def test_build_hosted_agent_payload_shape() -> None:
    from tools.deploy_data_agents import build_hosted_agent_payload

    payload = build_hosted_agent_payload(AGENT_DIR)
    assert payload["name"] == "PayerRT_Copilot"
    assert payload["kind"] == "foundry_hosted_agent"
    assert payload["model"] == "gpt-4.1-mini"
    assert payload["auth"] == {"type": "ProjectManagedIdentity"}
    assert payload["mcp_tool"] == {"require_approval": "never"}
    assert payload["governance"]["phi_minimization"] == "required"
    assert payload["governance"]["decision_authority"] == "deny"
    assert payload["governance"]["audit_log"] == "required"
    assert len(payload["tools"]) == 7  # 3 KQL + 3 delegating + 1 FabricIQ wrapper (Phase 3 G.3)
    assert payload["structured_output"]["schema"]["title"] == "RTIOpsEnvelope"
    assert "api_version" not in payload


def test_recommendation_enum_locked(output_schema: dict) -> None:
    """C.5 contract: routing-only enum. No adjudicative values allowed."""
    rec = output_schema["properties"]["recommendation"]
    assert set(rec["enum"]) == {
        "dispatch_outreach",
        "open_pa_investigation",
        "open_siu_case",
        "monitor",
    }


def test_persona_enum_locked(output_schema: dict) -> None:
    persona = output_schema["properties"]["persona"]
    assert set(persona["enum"]) == {"UM", "CareMgmt", "SIU", "Unknown"}


def test_deploy_hosted_agent_dry_run_is_safe() -> None:
    from tools.deploy_data_agents import deploy_hosted_agent

    result = deploy_hosted_agent(AGENT_DIR, dry_run=True)
    assert result["status"] == "DryRun"
    assert result["id"] == "sim-PayerRT_Copilot"


def test_deploy_hosted_agent_live_requires_project() -> None:
    from tools.deploy_data_agents import deploy_hosted_agent

    with pytest.raises(RuntimeError, match="foundry_project"):
        deploy_hosted_agent(AGENT_DIR, dry_run=False, foundry_project=None)

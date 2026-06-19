"""B.4 drift tests — PAReviewCopilot hosted Foundry agent + tool stubs + live wiring.

Complements `tests/test_hosted_agent_artifacts.py` (which validates artifact
shape + governance flags). These tests lock the deploy contract:
  - agent.yaml is on the Responses API (no api_version pin per B.0).
  - Function-tool stub signatures match `tool_schemas.json` parameters.
  - Delegating tools (`ask_um_agent`, `ask_risk_agent`) reference DataAgent
    folders that actually exist under `workspace/`.
  - Cited regulatory ids (CMS-0057-F, AMA-PA-SURVEY-2024) resolve in
    `citations.yaml`.
  - Knowledge sources exist on disk.
  - `tools.deploy_data_agents.build_hosted_agent_payload()` produces the
    expected payload shape.
  - The live deploy path is import-clean (`agent_framework_azure_ai` is
    lazy-imported and dry-run is the default).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = REPO_ROOT / "data_agents" / "PAReviewCopilot.HostedAgent"


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
    """B.0 decision: Foundry Agent Service GA uses Responses API. Classic
    api_version 2026-04-01-preview retires 2027-03-31."""
    foundry = agent_yaml["foundry"]
    assert "api_version" not in foundry, (
        f"PAReviewCopilot.agent.yaml still pins api_version={foundry.get('api_version')!r}. "
        "B.0 mandates Responses API (no api_version pin)."
    )
    assert foundry["model"] == "gpt-4.1-mini"
    assert foundry["auth"] == "project_msi"


def test_tool_stubs_match_schema(tool_schemas: list[dict]) -> None:
    """Each non-delegating tool in tool_schemas.json has a Python stub whose
    function signature matches the declared JSON-schema parameters."""
    from tools.foundry_tools import get_pa_packet, lookup_policy_citation

    impls = {
        "get_pa_packet": get_pa_packet.get_pa_packet,
        "lookup_policy_citation": lookup_policy_citation.lookup_policy_citation,
    }
    for schema in tool_schemas:
        name = schema["name"]
        if name not in impls:
            continue  # delegating tools (ask_um_agent/ask_risk_agent) deploy via Foundry routing, no Python stub
        fn = impls[name]
        sig_params = list(inspect.signature(fn).parameters)
        schema_params = list(schema["parameters"]["properties"].keys())
        assert sig_params == schema_params, (
            f"tool {name!r}: Python signature {sig_params} != schema params {schema_params}"
        )
        required = schema["parameters"].get("required", [])
        for r in required:
            assert r in sig_params, f"tool {name!r}: required schema param {r!r} missing from Python signature"


def test_lookup_policy_citation_enum_enforcement() -> None:
    """Pointer-not-text discipline: enum values from tool_schemas must be
    enforced at the stub boundary."""
    from tools.foundry_tools.lookup_policy_citation import lookup_policy_citation

    # happy path
    out = lookup_policy_citation("72148", "MA", "outpatient")
    assert out["policy_id"]
    assert out["policy_version"]
    assert out["cited_section_anchor"]
    # negative: bad lob
    with pytest.raises(ValueError, match="lob"):
        lookup_policy_citation("72148", "Medicare", "outpatient")
    # negative: bad setting
    with pytest.raises(ValueError, match="requested_setting"):
        lookup_policy_citation("72148", "MA", "drive-thru")


def test_get_pa_packet_phi_minimization() -> None:
    """Hard rule: get_pa_packet stub must not surface PHI fields (full DOB,
    SSN, address, phone, chart_notes)."""
    from tools.foundry_tools.get_pa_packet import get_pa_packet

    out = get_pa_packet("PA-2026-0001829")
    forbidden = {"dob", "date_of_birth", "ssn", "address", "phone", "chart_notes"}
    flat_keys = set(out.keys()) | set(out.get("member_context", {}).keys())
    leaks = flat_keys & forbidden
    assert not leaks, f"PHI leak in get_pa_packet stub: {leaks}"
    # malformed id should be rejected (boundary validation)
    with pytest.raises(ValueError, match="invalid pa_id"):
        get_pa_packet("not-a-pa-id")


def test_delegating_tools_resolve_to_existing_dataagents(agent_yaml: dict) -> None:
    """`ask_um_agent` → UMAgent, `ask_risk_agent` → RiskAdjustmentAgent.
    Both upstream DataAgents must exist as workspace items (B.3 shipped them)."""
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


def test_regulatory_citations_resolve(agent_yaml: dict) -> None:
    """All citation ids referenced by aiInstructions + cases must resolve in
    citations.yaml. We check the two anchors PAReviewCopilot is built around."""
    citations = yaml.safe_load((REPO_ROOT / "citations.yaml").read_text(encoding="utf-8"))
    ids = {c["id"] for c in citations["citations"]}
    for required_id in ("CMS-0057-F", "AMA-PA-SURVEY-2024"):
        assert required_id in ids, f"citations.yaml missing {required_id!r}"


def test_knowledge_sources_exist(agent_yaml: dict) -> None:
    for ks in agent_yaml["knowledge_sources"]:
        p = REPO_ROOT / ks
        assert p.is_file(), f"knowledge_source missing on disk: {ks}"


def test_build_hosted_agent_payload_shape() -> None:
    """`build_hosted_agent_payload()` is a pure function — assert it produces
    the expected payload shape from on-disk artifacts."""
    from tools.deploy_data_agents import build_hosted_agent_payload

    payload = build_hosted_agent_payload(AGENT_DIR)
    assert payload["name"] == "PAReviewCopilot"
    assert payload["kind"] == "foundry_hosted_agent"
    assert payload["model"] == "gpt-4.1-mini"
    assert payload["auth"] == {"type": "ProjectManagedIdentity"}
    assert payload["mcp_tool"] == {"require_approval": "never"}
    assert payload["governance"]["phi_minimization"] == "required"
    assert payload["governance"]["decision_authority"] == "deny"
    assert payload["governance"]["audit_log"] == "required"
    assert len(payload["tools"]) == 4
    assert payload["structured_output"]["schema"]["title"] == "PAReviewEnvelope"
    # B.0: no api_version field in the payload either (Responses API)
    assert "api_version" not in payload


def test_recommendation_enum_locked(output_schema: dict) -> None:
    """Decision_authority=deny enforced via the 4-value enum — locking this
    prevents accidental drift to an adjudicated-outcome value."""
    rec = output_schema["properties"]["recommendation"]
    assert set(rec["enum"]) == {
        "prepare_approval",
        "request_more_info",
        "escalate_to_md",
        "prepare_denial_for_md_review",
    }


def test_deploy_hosted_agent_dry_run_is_safe() -> None:
    """Dry-run path must not require the agent-framework-azure-ai SDK to be
    importable — the import lives behind the live branch."""
    from tools.deploy_data_agents import deploy_hosted_agent

    result = deploy_hosted_agent(AGENT_DIR, dry_run=True)
    assert result["status"] == "DryRun"
    assert result["id"] == "sim-PAReviewCopilot"


def test_deploy_hosted_agent_live_requires_project() -> None:
    """Live path must refuse to run without an explicit project endpoint."""
    from tools.deploy_data_agents import deploy_hosted_agent

    with pytest.raises(RuntimeError, match="foundry_project"):
        deploy_hosted_agent(AGENT_DIR, dry_run=False, foundry_project=None)

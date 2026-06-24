"""
Stream D.2 - observability wiring tests.

When `APPLICATIONINSIGHTS_CONNECTION_STRING` is set in the environment, every
hosted-agent payload built by `tools.deploy_data_agents.build_hosted_agent_payload`
must carry an `application_insights` block with:
  - connection_string_env="APPLICATIONINSIGHTS_CONNECTION_STRING" (we never
    persist the secret value on disk; only the env-var name)
  - OTel resource attributes tagged with service.name == agent name,
    service.namespace == "fabric-payer-demo", and ai.agent.kind == agent kind

When the env var is NOT set, the payload must NOT carry the block (so dry-run
in plain dev environments stays clean).

Also asserts that the two App Insights workbook JSON files under
`monitoring/` are well-formed and reference the correct `cloud_RoleName`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DA = ROOT / "data_agents"
MON = ROOT / "monitoring"

sys.path.insert(0, str(ROOT))
from tools.deploy_data_agents import build_hosted_agent_payload  # noqa: E402

HOSTED_AGENT_DIRS = sorted(DA.glob("*.HostedAgent"))


@pytest.mark.parametrize("agent_dir", HOSTED_AGENT_DIRS, ids=[d.name for d in HOSTED_AGENT_DIRS])
def test_payload_omits_app_insights_when_env_unset(agent_dir: Path, monkeypatch) -> None:
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    payload = build_hosted_agent_payload(agent_dir)
    assert "application_insights" not in payload, (
        f"{agent_dir.name}: payload carries application_insights block even with env unset"
    )


@pytest.mark.parametrize("agent_dir", HOSTED_AGENT_DIRS, ids=[d.name for d in HOSTED_AGENT_DIRS])
def test_payload_attaches_app_insights_when_env_set(agent_dir: Path, monkeypatch) -> None:
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=stub;IngestionEndpoint=https://stub")
    payload = build_hosted_agent_payload(agent_dir)
    assert "application_insights" in payload, (
        f"{agent_dir.name}: payload missing application_insights block when env is set"
    )
    ai = payload["application_insights"]
    # We MUST NOT persist the secret connection string in the payload.
    assert ai["connection_string_env"] == "APPLICATIONINSIGHTS_CONNECTION_STRING", (
        "payload must reference the env var by name, not the secret value"
    )
    # Forbid raw secret leakage anywhere in the payload.
    flat = json.dumps(payload)
    assert "InstrumentationKey=stub" not in flat, (
        "raw connection string leaked into payload; deploy script must only reference the env var name"
    )
    attrs = ai["otel_resource_attributes"]
    expected_name = agent_dir.name.replace(".HostedAgent", "")
    assert attrs["service.name"] == expected_name
    assert attrs["service.namespace"] == "fabric-payer-demo"
    assert attrs["ai.agent.kind"] == payload["kind"]
    assert "deployment.environment" in attrs


@pytest.mark.parametrize(
    "workbook,agent_role",
    [
        ("payerrt_dashboard.json", "PayerRT_Copilot"),
        ("pareview_dashboard.json", "PAReviewCopilot"),
    ],
)
def test_monitoring_workbook_is_wellformed(workbook: str, agent_role: str) -> None:
    p = MON / workbook
    assert p.exists(), f"monitoring/{workbook} missing"
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert "$schema" in doc and doc["$schema"].startswith("https://aka.ms/AzureMonitor/Workbook"), (
        f"{workbook}: must declare the Azure Monitor Workbook schema"
    )
    items = doc.get("items", [])
    assert items, f"{workbook}: must contain at least one item"
    # Every KQL query must scope to this agent's cloud_RoleName.
    queries = [i["content"].get("query", "") for i in items if i.get("type") == 3]
    assert queries, f"{workbook}: must contain at least one KQL query item (type=3)"
    for q in queries:
        assert agent_role in q, (
            f"{workbook}: KQL query missing cloud_RoleName scope to {agent_role!r}: {q[:120]!r}"
        )


def test_both_hosted_agents_have_a_workbook() -> None:
    """Every hosted agent should have a monitoring workbook so dashboards stay 1:1."""
    expected = {f"{d.name.replace('.HostedAgent', '').lower().replace('_copilot', '')}_dashboard.json"
                for d in HOSTED_AGENT_DIRS}
    # Map the actual filenames since we shortened them.
    actual = {p.name for p in MON.glob("*_dashboard.json")}
    # Loose check: count parity (we shipped 2 workbooks for 2 hosted agents).
    assert len(actual) == len(HOSTED_AGENT_DIRS), (
        f"hosted agents={len(HOSTED_AGENT_DIRS)} but monitoring/*_dashboard.json={len(actual)} "
        f"(expected hint={expected}, actual={actual})"
    )

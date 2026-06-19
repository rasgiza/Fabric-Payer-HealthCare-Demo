"""
lookup_policy_citation — Foundry function-tool stub for PAReviewCopilot.

Schema source of truth: `data_agents/PAReviewCopilot.HostedAgent/tool_schemas.json`.

Pointer-not-text discipline (per payer_knowledge/policy_citation_pattern.md):
  - Returns policy_id + policy_version + cited_section_anchor (a *pointer*).
  - NEVER returns licensed-criteria text (MCG / InterQual / internal medical
    policy). The reviewer opens the licensed source themselves.
  - Every emitted envelope is logged with policy_id+version+anchor so a
    RADV-style audit can reconstruct exactly which version was pointed at.
"""

from __future__ import annotations

from typing import Any

_LOB_ENUM = {"MA", "Medicaid", "Commercial", "ACA", "Dual"}
_SETTING_ENUM = {"inpatient", "outpatient", "office", "asc", "home", "telehealth"}


def lookup_policy_citation(
    service_code: str,
    lob: str,
    requested_setting: str,
) -> dict[str, Any]:
    """Resolve the governing policy pointer for a service code + LOB + setting.

    Args:
        service_code: CPT or HCPCS code.
        lob: One of MA / Medicaid / Commercial / ACA / Dual.
        requested_setting: One of inpatient / outpatient / office / asc / home / telehealth.

    Returns:
        Dict with keys: policy_id, policy_version, cited_section_anchor, link_token.
        link_token is an opaque token the reviewer's policy-library UI resolves
        to the actual document. No licensed-criteria text is returned.

    Raises:
        ValueError: if lob or requested_setting are outside the schema enums.
    """
    if not isinstance(service_code, str) or not service_code:
        raise ValueError("lookup_policy_citation: service_code is required")
    if lob not in _LOB_ENUM:
        raise ValueError(f"lookup_policy_citation: lob {lob!r} not in {sorted(_LOB_ENUM)}")
    if requested_setting not in _SETTING_ENUM:
        raise ValueError(
            f"lookup_policy_citation: requested_setting {requested_setting!r} not in {sorted(_SETTING_ENUM)}"
        )
    # v1 stub: deterministic pointer shape so structured-output envelope
    # validates end-to-end. v1.1 wires to the policy library backend.
    return {
        "policy_id": f"AcmeCare-{service_code}-{lob}",
        "policy_version": "2026.1",
        "cited_section_anchor": "§stub",
        "link_token": f"policylib://{lob}/{service_code}/{requested_setting}",
        "_stub": True,
    }

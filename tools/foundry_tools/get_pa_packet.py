"""
get_pa_packet — Foundry function-tool stub for PAReviewCopilot.

Schema source of truth: `data_agents/PAReviewCopilot.HostedAgent/tool_schemas.json`.
The signature here MUST match the JSON-schema parameters declared there.

Hard rules (from aiInstructions.md):
  - Returns the structured packet a reviewer needs (service code, requested
    setting, clinical fields, member context).
  - PHI minimization: NEVER returns full DOB, SSN, address, phone, or chart
    notes. Member identity is `member_hash`. Permitted: age band, sex, LOB,
    market.
  - Missing-data behavior: caller declares missing fields explicitly; this
    stub returns a `missing_fields` list rather than fabricating values.
"""

from __future__ import annotations

from typing import Any


def get_pa_packet(pa_id: str) -> dict[str, Any]:
    """Fetch the prior-authorization packet for a PA case id.

    Args:
        pa_id: PA case id, e.g., "PA-2026-0001829".

    Returns:
        Dict with keys: pa_id, service_code, requested_setting, lob, expedited,
        clinical_fields, member_context, missing_fields.

    v1 stub: returns a structurally-valid shell with `missing_fields` listing
    every required field. v1.1 wires this to the claims/PA system of record.
    """
    if not isinstance(pa_id, str) or not pa_id.startswith("PA-"):
        raise ValueError(f"get_pa_packet: invalid pa_id {pa_id!r} (expected 'PA-YYYY-NNNNNNN' format)")
    return {
        "pa_id": pa_id,
        "service_code": None,
        "requested_setting": None,
        "lob": None,
        "expedited": None,
        "clinical_fields": {},
        "member_context": {
            "member_hash": None,
            "age_band": None,
            "sex": None,
            "lob": None,
            "market": None,
        },
        "missing_fields": [
            "service_code",
            "requested_setting",
            "lob",
            "expedited",
            "clinical_fields",
        ],
        "_stub": True,
    }

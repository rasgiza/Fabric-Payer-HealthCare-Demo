"""
get_emergency_admit_worklist -- Foundry function-tool stub for PayerRT_Copilot.

Schema source of truth: `data_agents/PayerRT_Copilot.HostedAgent/tool_schemas.json`.

Reads the leftanti-join shape NB_RTI_03_ADT_Outreach publishes to
`kqldb_payer_rt.adt_admissions` -- emergency admits without a
member_outreach row within 24h. PHI-minimized: returns priority-bucket
counts only, no member or facility identifiers.
"""

from __future__ import annotations

from typing import Any

_PRIORITY_ENUM = {"high", "standard", "all"}


def get_emergency_admit_worklist(
    lookback_min: int, priority_only: str | None = None
) -> dict[str, Any]:
    """Return current emergency-admit worklist evidence.

    Args:
        lookback_min: window size in minutes, 30..1440.
        priority_only: "high", "standard", or "all" (default).

    Returns:
        Dict with keys: lookback_min, priority_only, high_priority_count,
        standard_priority_count, without_outreach_count.

    v1 stub: deterministic shell with zero counts; v1.1 wires to kqldb_payer_rt.
    """
    if not isinstance(lookback_min, int) or not (30 <= lookback_min <= 1440):
        raise ValueError(
            f"get_emergency_admit_worklist: lookback_min must be int 30..1440, got {lookback_min!r}"
        )
    if priority_only is not None and priority_only not in _PRIORITY_ENUM:
        raise ValueError(
            f"get_emergency_admit_worklist: priority_only must be one of {sorted(_PRIORITY_ENUM)} or None, got {priority_only!r}"
        )
    return {
        "lookback_min": lookback_min,
        "priority_only": priority_only,
        "high_priority_count": 0,
        "standard_priority_count": 0,
        "without_outreach_count": 0,
        "_stub": True,
    }

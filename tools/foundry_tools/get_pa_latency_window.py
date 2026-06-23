"""
get_pa_latency_window -- Foundry function-tool stub for PayerRT_Copilot.

Schema source of truth: `data_agents/PayerRT_Copilot.HostedAgent/tool_schemas.json`.
The signature here MUST match the JSON-schema parameters declared there.

Reads the same 15-minute bin shape NB_RTI_02_PA_Latency publishes to
`kqldb_payer_rt.auth_lifecycle`. PHI-minimized: returns aggregates and
percentiles only -- no member, provider, or auth identifiers.
"""

from __future__ import annotations

from typing import Any


def get_pa_latency_window(lookback_min: int, is_expedited: bool | None = None) -> dict[str, Any]:
    """Return current PA latency window evidence.

    Args:
        lookback_min: window size in minutes, 15..1440.
        is_expedited: if True, filter to 72h-SLA cohort; if False, 168h cohort;
            if None, both cohorts combined.

    Returns:
        Dict with keys: lookback_min, is_expedited, p50_hours, p90_hours,
        p99_hours, breach_count, breach_rate, decisions.

    v1 stub: deterministic shell with zero counts so a dry-run envelope
    validates end-to-end. v1.1 wires this to kqldb_payer_rt.
    """
    if not isinstance(lookback_min, int) or not (15 <= lookback_min <= 1440):
        raise ValueError(
            f"get_pa_latency_window: lookback_min must be int 15..1440, got {lookback_min!r}"
        )
    if is_expedited is not None and not isinstance(is_expedited, bool):
        raise ValueError(
            f"get_pa_latency_window: is_expedited must be bool or None, got {is_expedited!r}"
        )
    return {
        "lookback_min": lookback_min,
        "is_expedited": is_expedited,
        "p50_hours": 0.0,
        "p90_hours": 0.0,
        "p99_hours": 0.0,
        "breach_count": 0,
        "breach_rate": 0.0,
        "decisions": 0,
        "_stub": True,
    }

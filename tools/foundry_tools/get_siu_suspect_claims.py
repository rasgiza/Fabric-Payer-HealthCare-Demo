"""
get_siu_suspect_claims -- Foundry function-tool stub for PayerRT_Copilot.

Schema source of truth: `data_agents/PayerRT_Copilot.HostedAgent/tool_schemas.json`.

Reads the score-aggregation shape NB_RTI_04_SIU_Intake_Scoring publishes to
`kqldb_payer_rt.claim_arrivals`. PHI-minimized: returns aggregate counts and
the max intake_score in window, never individual claim identifiers.
"""

from __future__ import annotations

from typing import Any


def get_siu_suspect_claims(lookback_min: int, score_threshold: float) -> dict[str, Any]:
    """Return current SIU suspect-claims window evidence.

    Args:
        lookback_min: window size in minutes, 30..1440.
        score_threshold: 0.0..1.0; rows with intake_score >= threshold count
            as suspect (mirrors NB_RTI_04 parameter, default 0.6).

    Returns:
        Dict with keys: lookback_min, score_threshold, suspect_count,
        max_intake_score.

    v1 stub: deterministic shell with zero counts; v1.1 wires to kqldb_payer_rt.
    """
    if not isinstance(lookback_min, int) or not (30 <= lookback_min <= 1440):
        raise ValueError(
            f"get_siu_suspect_claims: lookback_min must be int 30..1440, got {lookback_min!r}"
        )
    if not isinstance(score_threshold, int | float) or not (0.0 <= score_threshold <= 1.0):
        raise ValueError(
            f"get_siu_suspect_claims: score_threshold must be float 0..1, got {score_threshold!r}"
        )
    return {
        "lookback_min": lookback_min,
        "score_threshold": float(score_threshold),
        "suspect_count": 0,
        "max_intake_score": 0.0,
        "_stub": True,
    }

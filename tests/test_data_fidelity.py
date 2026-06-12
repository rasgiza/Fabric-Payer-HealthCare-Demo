"""Tier 1C — data-fidelity gate.

Wraps tools/data_fidelity.run_all() at the bundled smoke run. Each check
must report passed=True; a single failure fails the test with the offending
detail strings so CI logs are self-explanatory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import data_fidelity


@pytest.fixture(scope="module")
def fidelity_checks(smoke_synth_dir: Path) -> list[data_fidelity.Check]:
    return data_fidelity.run_all(smoke_synth_dir)


def test_all_fidelity_checks_pass(fidelity_checks: list[data_fidelity.Check]) -> None:
    fails = [c for c in fidelity_checks if not c.passed]
    msg = "\n".join(f"  [FAIL] {c.name} — {c.detail}" for c in fails)
    assert not fails, f"data fidelity failed {len(fails)}/{len(fidelity_checks)} checks:\n{msg}"


def test_fidelity_returns_expected_check_set(fidelity_checks: list[data_fidelity.Check]) -> None:
    """Lock the check inventory so adding/removing checks is an explicit code change."""
    expected = {
        "member_pii_uniqueness",
        "provider_npi_uniqueness",
        "near_duplicate_claims",
        "near_duplicate_rx",
        "payer_mix_realism",
        "denial_concentration",
        "raf_coherence",
        "line_header_consistency",
        "service_date_sanity",
    }
    actual = {c.name for c in fidelity_checks}
    assert actual == expected, f"check inventory drift: missing={expected - actual}, extra={actual - expected}"

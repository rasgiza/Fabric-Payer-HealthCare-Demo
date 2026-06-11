"""Wraps `tools/audit_data.py` against the bundled smoke synth run.

This pins the data-fidelity baseline: referential integrity, dup-key scan, and
distribution sanity (denial rate, PMPM bands, RAF avg, HEDIS compliance bands).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import audit_data


@pytest.mark.smoke
def test_audit_data_smoke(smoke_synth_dir: Path) -> None:
    rc = audit_data.audit(smoke_synth_dir)
    assert rc == 0, "audit_data reported failures on smoke run (see captured stdout)"

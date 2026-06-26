"""
test_layer_schemas.py — Schema-contract pytest gate.

Runs every column/dtype/nullability/uniqueness/range contract from
tools/dq_checks.py against the smoke lakehouse output. Skips cleanly if
data/lakehouse/smoke/ is missing (so the test can be invoked even on a fresh
clone before run_local_etl.py has run — CI always generates smoke first).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools import dq_checks

ROOT = Path(__file__).resolve().parent.parent
SMOKE = ROOT / "data" / "lakehouse" / "smoke"


pytestmark = pytest.mark.skipif(
    not SMOKE.exists(),
    reason="Smoke lakehouse not generated; run `python tools/run_local_etl.py --run-id smoke` first.",
)


@pytest.mark.parametrize("layer", ["bronze", "silver", "gold"])
def test_layer_schema_contracts(layer: str) -> None:
    results = dq_checks.validate_layer("smoke", layer)
    failures = [r for r in results if not r.passed]
    assert not failures, "\n".join(
        f"{r.layer}.{r.table}: {r.check} -- {r.detail}" for r in failures
    )


def test_all_three_layers_have_contracts() -> None:
    """Guard against accidental removal of a whole layer's contracts."""
    for layer in ("bronze", "silver", "gold"):
        assert dq_checks.ALL_CONTRACTS[layer], f"{layer} has no contracts"


def test_every_contract_has_a_primary_key() -> None:
    """Every table contract should declare at least one unique_key OR mark a column unique=True."""
    for layer, contracts in dq_checks.ALL_CONTRACTS.items():
        for c in contracts:
            has_uk = bool(c.unique_keys)
            has_uniq_col = any(col.unique for col in c.columns)
            assert has_uk or has_uniq_col, (
                f"{layer}.{c.name} declares no primary key (unique_keys or unique=True column)"
            )

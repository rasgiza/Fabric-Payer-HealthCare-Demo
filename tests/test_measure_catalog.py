"""Schema check on `semantic_model/measure_catalog.yaml`.

Every entry must have `name` and `folder`; names must be unique. This is the
contract that `eval_agents_offline.py` validates fewshots against.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture(scope="module")
def measure_catalog(repo_root: Path) -> dict:
    path = repo_root / "semantic_model" / "measure_catalog.yaml"
    assert path.exists(), f"missing {path}"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_measure_catalog_schema(measure_catalog: dict) -> None:
    measures = measure_catalog.get("measures")
    assert isinstance(measures, list) and measures, "measure_catalog.measures must be a non-empty list"

    seen: set[str] = set()
    for i, m in enumerate(measures):
        assert isinstance(m, dict), f"measure[{i}] is not a mapping"
        name = m.get("name")
        assert name, f"measure[{i}] missing 'name'"
        assert m.get("folder"), f"measure[{name}] missing 'folder'"
        assert name not in seen, f"duplicate measure name: {name}"
        seen.add(name)

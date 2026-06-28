"""Validator for the Tier 1 Quickstart jumpstart manifest.

Checks that ``jumpstarts/quickstart/manifest.yaml`` is internally consistent and
that every artifact it references resolves on disk:

  1. Each ``items.*.source`` (and ``authoring``) path exists.
  2. Each report ``pages`` id exists in ``powerbi/pages.yaml``.
  3. Every table in ``data.tables`` has a matching ``<gold_dir>/<table>.parquet``
     and the gold dir contains no unexpected parquet files.
  4. The gold table set equals the union of the CFOAgent + StarsAgent
     ``table_allowlist`` bindings (the agents the quickstart ships).
  5. Each knowledge doc exists under ``knowledge.source_dir``.
  6. Each ``use_cases`` entry names a shipped agent surface.

Exits non-zero on any violation. Run from repo root::

    python tools/validate_jumpstart.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "jumpstarts" / "quickstart" / "manifest.yaml"
PAGES_YAML = REPO_ROOT / "powerbi" / "pages.yaml"


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"FATAL: {path} not found")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _agent_allowlist(agent: str) -> set[str]:
    binding = REPO_ROOT / "data_agents" / f"{agent}.DataAgent" / "binding.yaml"
    data = _load_yaml(binding)
    return set(data.get("fabric_data_agent", {}).get("table_allowlist", []))


def validate() -> list[str]:
    errors: list[str] = []
    m = _load_yaml(MANIFEST)

    items = m.get("items", {})
    shipped_agents: set[str] = set()

    # 1. item source/authoring paths exist
    for category, entries in items.items():
        for entry in entries:
            for key in ("source", "authoring"):
                rel = entry.get(key)
                if rel and not (REPO_ROOT / rel).exists():
                    errors.append(f"items.{category}.{entry.get('name')}: {key} path missing -> {rel}")
            if category == "data_agents":
                shipped_agents.add(entry["name"])

    # 2. report page ids exist in pages.yaml
    page_ids = {p["id"] for p in _load_yaml(PAGES_YAML).get("pages", [])}
    for entry in items.get("report", []):
        for pid in entry.get("pages", []):
            if pid not in page_ids:
                errors.append(f"items.report.{entry.get('name')}: page '{pid}' not in pages.yaml")

    # 3. data tables <-> parquet on disk (exact set match)
    data = m.get("data", {})
    gold_dir = REPO_ROOT / data.get("gold_dir", "")
    declared = list(data.get("tables", []))
    declared_set = set(declared)
    if len(declared) != len(declared_set):
        errors.append("data.tables contains duplicates")
    for table in declared_set:
        if not (gold_dir / f"{table}.parquet").exists():
            errors.append(f"data.tables: '{table}' has no parquet at {gold_dir}/{table}.parquet")
    if gold_dir.is_dir():
        on_disk = {p.stem for p in gold_dir.glob("*.parquet")}
        for extra in sorted(on_disk - declared_set):
            errors.append(f"gold dir has undeclared parquet: {extra}.parquet")
    else:
        errors.append(f"data.gold_dir missing -> {gold_dir}")

    # 4. gold tables == union of shipped agent allowlists
    if shipped_agents:
        union: set[str] = set()
        for agent in shipped_agents:
            union |= _agent_allowlist(agent)
        if declared_set != union:
            missing = sorted(union - declared_set)
            extra = sorted(declared_set - union)
            errors.append(
                "data.tables != union(agent allowlists): "
                f"missing={missing} extra={extra}"
            )

    # 5. knowledge docs exist
    knowledge = m.get("knowledge", {})
    ksrc = REPO_ROOT / knowledge.get("source_dir", "")
    for doc in knowledge.get("docs", []):
        if not (ksrc / doc).exists():
            errors.append(f"knowledge doc missing -> {ksrc / doc}")

    # 6. use cases reference shipped surfaces
    surfaces = shipped_agents | {e["name"] for e in items.get("report", [])}
    for uc in m.get("use_cases", []):
        if uc.get("surface") not in surfaces:
            errors.append(f"use_case {uc.get('id')}: surface '{uc.get('surface')}' not shipped")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print(f"FAIL: {MANIFEST.relative_to(REPO_ROOT)} has {len(errors)} issue(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK: {MANIFEST.relative_to(REPO_ROOT)} validated (quickstart Tier 1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Validator for the Payer Healthcare jumpstart manifests (all tiers).

Discovers every ``jumpstarts/<tier>/manifest.yaml`` (or a single one via
``--manifest``) and checks that each is internally consistent and that every
artifact it references resolves on disk:

  1. Each ``items.*.source`` and ``items.*.authoring`` path exists. Hosted
     Foundry agents may declare ``authoring`` only (they deploy via Foundry,
     not fabric-cicd, so they have no workspace ``source``).
  2. Each report ``pages`` id exists in ``powerbi/pages.yaml``.
  3. Data invariants:
       * pre-baked (``data.gold_dir`` set): every ``data.tables`` entry has a
         matching ``<gold_dir>/<table>.parquet`` AND the gold dir contains no
         undeclared parquet (exact set match).
       * generated (``data.generated: true``): no parquet on disk is required.
  4. The union of every shipped DataAgent's ``table_allowlist`` is a subset of
     ``data.tables`` (so each agent has every surface it binds to).
  5. Each knowledge doc exists under ``knowledge.source_dir``.
  6. Each ``use_cases`` entry names a shipped agent or report surface.
  7. Tier ordering: a higher tier's items/tables/knowledge must be a superset
     of every lower tier's (promotion safety — upgrading never drops content).

Exits non-zero on any violation. Run from repo root::

    python tools/validate_jumpstart.py              # all tiers
    python tools/validate_jumpstart.py --manifest jumpstarts/quickstart/manifest.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
JUMPSTARTS_DIR = REPO_ROOT / "jumpstarts"
PAGES_YAML = REPO_ROOT / "powerbi" / "pages.yaml"

# Back-compat: the Tier 1 quickstart manifest (kept so callers/tests that import
# ``validate()`` without args still work).
MANIFEST = JUMPSTARTS_DIR / "quickstart" / "manifest.yaml"

# Item categories whose entries deploy via fabric-cicd and therefore must carry
# a workspace ``source`` path. ``hosted_agents`` is intentionally absent — those
# deploy via Foundry and declare ``authoring`` only.
SOURCE_REQUIRED = {
    "lakehouse",
    "semantic_model",
    "data_agents",
    "report",
    "notebook",
    "data_pipeline",
    "ontology",
    "eventhouse",
    "eventstream",
    "kqldatabase",
    "reflex",
}


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"FATAL: {path} not found")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _agent_allowlist(agent: str) -> set[str]:
    binding = REPO_ROOT / "data_agents" / f"{agent}.DataAgent" / "binding.yaml"
    if not binding.exists():
        return set()
    data = _load_yaml(binding)
    return set(data.get("fabric_data_agent", {}).get("table_allowlist", []))


def _shipped_agents(manifest: dict) -> set[str]:
    return {e["name"] for e in manifest.get("items", {}).get("data_agents", [])}


def _declared_tables(manifest: dict) -> set[str]:
    return set(manifest.get("data", {}).get("tables", []))


def validate_one(manifest_path: Path) -> list[str]:
    errors: list[str] = []
    m = _load_yaml(manifest_path)
    rel = manifest_path.relative_to(REPO_ROOT)
    items = m.get("items", {})

    # 1. item source/authoring paths exist
    for category, entries in items.items():
        for entry in entries:
            name = entry.get("name", "?")
            checked_any = False
            for key in ("source", "authoring"):
                p = entry.get(key)
                if p:
                    checked_any = True
                    if not (REPO_ROOT / p).exists():
                        errors.append(f"{rel}: items.{category}.{name}: {key} missing -> {p}")
            if category in SOURCE_REQUIRED and not entry.get("source"):
                errors.append(f"{rel}: items.{category}.{name}: missing required 'source'")
            if not checked_any:
                errors.append(f"{rel}: items.{category}.{name}: no source/authoring path declared")

    # 2. report pages exist in pages.yaml
    page_ids = {p["id"] for p in _load_yaml(PAGES_YAML).get("pages", [])}
    for entry in items.get("report", []):
        for pid in entry.get("pages", []):
            if pid not in page_ids:
                errors.append(f"{rel}: items.report.{entry.get('name')}: page '{pid}' not in pages.yaml")

    # 3. data invariants
    data = m.get("data", {})
    declared = list(data.get("tables", []))
    declared_set = set(declared)
    if len(declared) != len(declared_set):
        errors.append(f"{rel}: data.tables contains duplicates")
    if data.get("generated"):
        if data.get("gold_dir"):
            errors.append(f"{rel}: data.generated=true must not also set gold_dir")
    elif declared:
        gold_dir = REPO_ROOT / data.get("gold_dir", "")
        if gold_dir.is_dir():
            on_disk = {p.stem for p in gold_dir.glob("*.parquet")}
            for table in declared_set - on_disk:
                errors.append(f"{rel}: data.tables '{table}' has no parquet at {gold_dir}/{table}.parquet")
            for extra in sorted(on_disk - declared_set):
                errors.append(f"{rel}: gold dir has undeclared parquet: {extra}.parquet")
        else:
            errors.append(f"{rel}: data.gold_dir missing -> {gold_dir}")

    # 4. union(agent allowlists) subset of declared tables
    union: set[str] = set()
    for agent in _shipped_agents(m):
        union |= _agent_allowlist(agent)
    if not (union <= declared_set):
        errors.append(f"{rel}: agent allowlist surfaces missing from data.tables: {sorted(union - declared_set)}")

    # 5. knowledge docs exist
    knowledge = m.get("knowledge", {})
    ksrc = REPO_ROOT / knowledge.get("source_dir", "")
    for doc in knowledge.get("docs", []):
        if not (ksrc / doc).exists():
            errors.append(f"{rel}: knowledge doc missing -> {ksrc / doc}")

    # 6. use cases reference shipped surfaces
    surfaces = _shipped_agents(m)
    surfaces |= {e["name"] for e in items.get("report", [])}
    surfaces |= {e["name"] for e in items.get("hosted_agents", [])}
    for uc in m.get("use_cases", []):
        if uc.get("surface") not in surfaces:
            errors.append(f"{rel}: use_case {uc.get('id')}: surface '{uc.get('surface')}' not shipped")

    return errors


def validate(manifest_path: Path | None = None) -> list[str]:
    """Back-compat single-manifest entry point (defaults to the quickstart)."""
    return validate_one(manifest_path or MANIFEST)


def validate_tier_ordering(manifests: dict[int, dict], paths: dict[int, Path]) -> list[str]:
    """A higher tier must be a content superset of every lower tier.

    Checked on the sets where promotion safety matters — shipped DataAgents,
    gold tables, and knowledge docs. Launcher notebooks are intentionally
    tier-specific and are NOT part of this invariant.
    """
    errors: list[str] = []
    tiers = sorted(manifests)
    for lo, hi in zip(tiers, tiers[1:], strict=False):
        m_lo, m_hi = manifests[lo], manifests[hi]
        rel_hi = paths[hi].relative_to(REPO_ROOT)
        for label, lo_set, hi_set in (
            ("data_agents", _shipped_agents(m_lo), _shipped_agents(m_hi)),
            ("data.tables", _declared_tables(m_lo), _declared_tables(m_hi)),
            ("knowledge", set(m_lo.get("knowledge", {}).get("docs", [])),
             set(m_hi.get("knowledge", {}).get("docs", []))),
        ):
            missing = lo_set - hi_set
            if missing:
                errors.append(
                    f"{rel_hi}: tier {hi} drops {label} present in tier {lo}: {sorted(missing)}"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=None, help="Validate only this manifest path.")
    args = parser.parse_args()

    if args.manifest:
        mp = Path(args.manifest)
        manifest_paths = [mp if mp.is_absolute() else REPO_ROOT / args.manifest]
    else:
        manifest_paths = sorted(JUMPSTARTS_DIR.glob("*/manifest.yaml"))

    if not manifest_paths:
        print("FAIL: no jumpstart manifests found under jumpstarts/*/manifest.yaml")
        return 1

    all_errors: list[str] = []
    by_tier: dict[int, dict] = {}
    paths_by_tier: dict[int, Path] = {}
    for mp in manifest_paths:
        all_errors.extend(validate_one(mp))
        data = _load_yaml(mp)
        tier = data.get("tier")
        if isinstance(tier, int):
            by_tier[tier] = data
            paths_by_tier[tier] = mp

    if len(by_tier) > 1:
        all_errors.extend(validate_tier_ordering(by_tier, paths_by_tier))

    if all_errors:
        print(f"FAIL: {len(all_errors)} issue(s) across {len(manifest_paths)} manifest(s):")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    names = ", ".join(p.parent.name for p in manifest_paths)
    print(f"OK: {len(manifest_paths)} jumpstart manifest(s) validated ({names})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

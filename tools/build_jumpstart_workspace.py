"""Assemble a per-tier, self-contained Fabric workspace folder for a jumpstart.

The Fabric Jumpstart installer (``fabric_jumpstart._install_from_github``) clones
the repo at ``repo_ref`` and hands ``workspace_path`` to ``fabric_cicd`` which
walks that folder recursively for ``*.<ItemType>`` directories, filtered only by
``items_in_scope`` (item *type*, never individual item). Pointing every tier at
the shared repo-root ``workspace/`` would therefore leak items that belong to a
higher tier (e.g. the four ``NB_RTI_*`` notebooks are ``Notebook`` type and would
land in a Tier-2 install).

So each tier needs its own folder containing exactly its items. Rather than keep
a hand-maintained second copy that silently drifts from the source of truth, this
script *generates* ``jumpstarts/<tier>/workspace/`` from each tier's
``manifest.yaml`` ``items:`` block plus the shared ``workspace/parameter.yml``.

Usage (from repo root)::

    python tools/build_jumpstart_workspace.py --tier analytics          # write
    python tools/build_jumpstart_workspace.py --tier analytics --check  # drift gate
    python tools/build_jumpstart_workspace.py --all                     # every tier
    python tools/build_jumpstart_workspace.py --all --check

``--check`` regenerates into a temp dir and compares it against the committed
folder, exiting non-zero on any difference (mirrors ``tools/deploy.py --check``).
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
JUMPSTARTS_DIR = REPO_ROOT / "jumpstarts"
PARAMETER_YML = REPO_ROOT / "workspace" / "parameter.yml"

# Fabric item-folder suffixes we recognise as deployable workspace items. A
# manifest ``source`` whose directory name ends in one of these is copied; other
# sources (e.g. the Foundry ``mission_control`` orchestrator) are skipped because
# they do not deploy through fabric-cicd.
KNOWN_ITEM_SUFFIXES = {
    "Lakehouse",
    "SemanticModel",
    "Report",
    "DataAgent",
    "Notebook",
    "DataPipeline",
    "Ontology",
    "Eventhouse",
    "Eventstream",
    "KQLDatabase",
    "Reflex",
}

# DataAgent datasource folders are named ``<prefix>-<displayName>`` where the
# prefix maps to the Fabric item type of the backing item. A tier that does not
# deploy that backing item (e.g. Tier 2 has no ``Payer_Ontology`` Ontology) must
# not ship the datasource folder: the entry-point launcher only rebinds folders
# whose target item is discoverable in the workspace, so a leftover folder stays
# a dangling zero-GUID reference. This mirrors ``bind_data_agent_sources`` which
# drops the same folders in the dev deploy path.
DATASOURCE_PREFIX_TO_TYPE = {
    "lakehouse-tables": "Lakehouse",
    "semantic-model": "SemanticModel",
    "graph": "Ontology",
}


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"FATAL: {path} not found")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _is_item_source(source: str) -> bool:
    """True when ``source`` names a Fabric item folder (``*.<KnownType>``)."""
    suffix = Path(source).name.rsplit(".", 1)
    return len(suffix) == 2 and suffix[1] in KNOWN_ITEM_SUFFIXES


def _item_keys(sources: list[Path]) -> set[tuple[str, str]]:
    """Return the ``(fabric_type, displayName)`` set of a tier's deployed items."""
    keys: set[tuple[str, str]] = set()
    for src in sources:
        stem, _, suffix = src.name.rpartition(".")
        if stem and suffix in KNOWN_ITEM_SUFFIXES:
            keys.add((suffix, stem))
    return keys


def _prune_agent_datasources(agent_dir: Path, item_keys: set[tuple[str, str]]) -> None:
    """Drop datasource folders whose backing item is not deployed in this tier."""
    for stage in ("draft", "published"):
        stage_dir = agent_dir / "Files" / "Config" / stage
        if not stage_dir.is_dir():
            continue
        for sub in stage_dir.iterdir():
            if not sub.is_dir():
                continue
            for prefix, fabric_type in DATASOURCE_PREFIX_TO_TYPE.items():
                if sub.name.startswith(prefix + "-"):
                    display_name = sub.name[len(prefix) + 1:]
                    if (fabric_type, display_name) not in item_keys:
                        shutil.rmtree(sub)
                    break


def _collect_item_sources(manifest: dict) -> list[Path]:
    """Return the repo-relative item-folder sources declared under ``items:``."""
    sources: list[Path] = []
    seen: set[str] = set()
    for entries in (manifest.get("items") or {}).values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            source = entry.get("source")
            if not source or not _is_item_source(source):
                continue
            if source in seen:
                continue
            seen.add(source)
            sources.append(REPO_ROOT / source)
    return sources


def _build_into(dest: Path, sources: list[Path]) -> None:
    """Materialise ``dest`` with each item folder + parameter.yml."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    item_keys = _item_keys(sources)
    for src in sources:
        if not src.exists():
            sys.exit(f"FATAL: item source not found: {src.relative_to(REPO_ROOT)}")
        copied = dest / src.name
        shutil.copytree(src, copied)
        if src.name.endswith(".DataAgent"):
            _prune_agent_datasources(copied, item_keys)
    if not PARAMETER_YML.exists():
        sys.exit(f"FATAL: {PARAMETER_YML.relative_to(REPO_ROOT)} not found")
    shutil.copy2(PARAMETER_YML, dest / PARAMETER_YML.name)


def _diff_trees(a: Path, b: Path) -> list[str]:
    """Return human-readable differences between two directory trees."""
    diffs: list[str] = []

    def _walk(cmp: filecmp.dircmp, rel: str) -> None:
        for name in cmp.left_only:
            diffs.append(f"  only in generated: {rel}{name}")
        for name in cmp.right_only:
            diffs.append(f"  only in committed: {rel}{name}")
        for name in cmp.diff_files:
            diffs.append(f"  differs: {rel}{name}")
        for name in cmp.funny_files:
            diffs.append(f"  unreadable: {rel}{name}")
        for name, sub in cmp.subdirs.items():
            _walk(sub, f"{rel}{name}/")

    _walk(filecmp.dircmp(a, b), "")
    return diffs


def build_tier(tier_dir: Path, *, check: bool) -> bool:
    """Generate (or verify) one tier's workspace folder. Returns True on success."""
    manifest = _load_yaml(tier_dir / "manifest.yaml")
    sources = _collect_item_sources(manifest)
    dest = tier_dir / "workspace"
    rel_dest = dest.relative_to(REPO_ROOT)

    if not sources:
        print(f"[{tier_dir.name}] no fabric item sources in manifest; nothing to build")
        return True

    if check:
        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp) / "workspace"
            _build_into(staged, sources)
            if not dest.exists():
                print(f"[{tier_dir.name}] DRIFT: {rel_dest} is missing (run without --check)")
                return False
            diffs = _diff_trees(staged, dest)
        if diffs:
            print(f"[{tier_dir.name}] DRIFT between generated and {rel_dest}:")
            print("\n".join(diffs))
            return False
        print(f"[{tier_dir.name}] OK: {rel_dest} matches manifest ({len(sources)} items)")
        return True

    _build_into(dest, sources)
    print(f"[{tier_dir.name}] wrote {rel_dest}: {len(sources)} items + parameter.yml")
    return True


def _tier_dirs(args: argparse.Namespace) -> list[Path]:
    if args.all:
        return sorted(p.parent for p in JUMPSTARTS_DIR.glob("*/manifest.yaml"))
    tier_dir = JUMPSTARTS_DIR / args.tier
    if not (tier_dir / "manifest.yaml").exists():
        sys.exit(f"FATAL: no manifest at {tier_dir / 'manifest.yaml'}")
    return [tier_dir]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tier", help="tier folder name under jumpstarts/ (e.g. analytics)")
    group.add_argument("--all", action="store_true", help="build/check every tier")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify committed folders match the manifest instead of writing",
    )
    args = parser.parse_args()

    ok = True
    for tier_dir in _tier_dirs(args):
        ok = build_tier(tier_dir, check=args.check) and ok

    if args.check and not ok:
        print("\nDRIFT detected. Run: python tools/build_jumpstart_workspace.py --all", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

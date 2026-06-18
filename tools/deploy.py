"""Thin wrapper around fabric-cicd 1.1.0 for the Payer demo.

Reads deployment.yaml + workspace/parameter.yml, validates the workspace tree
shape, then publishes via the fabric-cicd Python API. Designed so the same
invocation works locally (developer push) and in GitHub Actions.

Usage:
    python tools/deploy.py --env dev
    python tools/deploy.py --env prod --confirm
    python tools/deploy.py --env dev --dry-run

Environment variables required (per env):
    FABRIC_WORKSPACE_ID_<ENV>     target workspace GUID
    FABRIC_CAPACITY_ID_<ENV>      Fabric capacity GUID (informational)
    AZURE_TENANT_ID               for the identity that publishes
    AZURE_CLIENT_ID               (only when not using DefaultAzureCredential)
    AZURE_CLIENT_SECRET           (only when not using MSI / az login)

Exit codes:
    0  success (or dry-run preview rendered)
    1  validation failure (missing item, parameter drift)
    2  missing env vars / auth failure
    3  fabric-cicd publish error
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOYMENT_YAML = REPO_ROOT / "deployment.yaml"
WORKSPACE_DIR = REPO_ROOT / "workspace"
PARAMETER_YAML = WORKSPACE_DIR / "parameter.yml"

# fabric-cicd 1.1.0 supports these item types; the SDK names are stable.
SUPPORTED_TYPES = {
    "Lakehouse",
    "Notebook",
    "DataPipeline",
    "Environment",
    "SemanticModel",
    "Report",
    "DataAgent",
    "Eventhouse",
    "KQLDatabase",
    "Reflex",
    "Eventstream",
}


def _load_manifest() -> dict:
    if not DEPLOYMENT_YAML.is_file():
        sys.exit(f"[deploy] deployment.yaml not found at {DEPLOYMENT_YAML}")
    return yaml.safe_load(DEPLOYMENT_YAML.read_text(encoding="utf-8"))


def _resolve_workspace_id(manifest: dict, env: str) -> str:
    envs = manifest["spec"]["environments"]
    if env not in envs:
        sys.exit(f"[deploy] env {env!r} not declared in deployment.yaml (have: {list(envs)})")
    raw = envs[env]["workspaceId"]
    # YAML stores `${FABRIC_WORKSPACE_ID_DEV}` literally — expand here.
    if raw.startswith("${") and raw.endswith("}"):
        var = raw[2:-1]
        val = os.environ.get(var)
        if not val:
            sys.exit(f"[deploy] env var {var} is required for --env {env}")
        return val
    return raw


def _discover_items() -> dict[str, list[str]]:
    """Returns {ItemType: [displayName, ...]} for every <name>.<Type>/ folder."""
    items: dict[str, list[str]] = {}
    for child in sorted(WORKSPACE_DIR.iterdir()):
        if not child.is_dir():
            continue
        if "." not in child.name:
            continue
        name, _, kind = child.name.rpartition(".")
        if kind not in SUPPORTED_TYPES:
            continue
        plat = child / ".platform"
        if not plat.is_file():
            sys.exit(f"[deploy] {child.name}: missing .platform descriptor")
        doc = json.loads(plat.read_text(encoding="utf-8"))
        if doc["metadata"]["type"] != kind:
            sys.exit(
                f"[deploy] {child.name}: .platform type {doc['metadata']['type']!r} "
                f"does not match folder suffix {kind!r}"
            )
        if doc["metadata"]["displayName"] != name:
            sys.exit(
                f"[deploy] {child.name}: .platform displayName "
                f"{doc['metadata']['displayName']!r} does not match folder name {name!r}"
            )
        items.setdefault(kind, []).append(name)
    return items


def _validate(manifest: dict, items: dict[str, list[str]]) -> None:
    order = manifest["spec"]["itemOrder"]
    for kind in items:
        if kind not in order:
            sys.exit(f"[deploy] item type {kind!r} present on disk but not in itemOrder")
    if not PARAMETER_YAML.is_file():
        sys.exit(f"[deploy] {PARAMETER_YAML} missing")


def _render_preview(manifest: dict, items: dict[str, list[str]], workspace_id: str) -> None:
    print("=" * 72)
    print(f"[deploy] DRY RUN — workspace_id={workspace_id}")
    print("=" * 72)
    print(f"Manifest: {manifest['metadata']['name']}")
    print(f"Order:    {' -> '.join(manifest['spec']['itemOrder'])}")
    print()
    optional = set(manifest["spec"].get("optionalItems") or [])
    total = 0
    for kind in manifest["spec"]["itemOrder"]:
        names = items.get(kind, [])
        if not names:
            continue
        print(f"  [{kind}]")
        for n in names:
            tag = "  (optional)" if f"{n}.{kind}" in optional else ""
            print(f"    - {n}{tag}")
            total += 1
    print()
    print(f"[deploy] {total} item(s) would be published. Re-run without --dry-run to apply.")


def _publish(env: str, workspace_id: str, manifest: dict) -> None:
    """Invoke fabric-cicd. Import is lazy so dry-run + tests don't need the SDK."""
    try:
        fc = importlib.import_module("fabric_cicd")
    except ImportError:
        sys.exit(
            "[deploy] fabric-cicd is not installed in this environment. "
            "Install via `pip install fabric-cicd==1.1.0`."
        )

    publish_cls = getattr(fc, "FabricWorkspace", None)
    if publish_cls is None:
        sys.exit("[deploy] fabric-cicd: FabricWorkspace not found — SDK version mismatch?")

    ws = publish_cls(
        workspace_id=workspace_id,
        repository_directory=str(WORKSPACE_DIR),
        item_type_in_scope=manifest["spec"]["itemOrder"],
        environment=env,
    )

    print(f"[deploy] publishing to env={env} workspace={workspace_id}")
    try:
        fc.publish_all_items(ws)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"[deploy] fabric-cicd publish failed: {exc}")
    print("[deploy] publish succeeded")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Deploy the Payer Fabric workspace via fabric-cicd 1.1.0")
    p.add_argument("--env", required=True, choices=["dev", "staging", "prod"])
    p.add_argument("--dry-run", action="store_true", help="Preview the deploy without calling fabric-cicd")
    p.add_argument(
        "--confirm",
        action="store_true",
        help="Required for --env prod (guard against accidental prod publishes)",
    )
    args = p.parse_args(argv)

    if args.env == "prod" and not (args.confirm or args.dry_run):
        sys.exit("[deploy] --env prod requires --confirm (or --dry-run for preview)")

    manifest = _load_manifest()
    items = _discover_items()
    _validate(manifest, items)
    workspace_id = (
        "<dry-run-placeholder>" if args.dry_run else _resolve_workspace_id(manifest, args.env)
    )

    if args.dry_run:
        _render_preview(manifest, items, workspace_id)
        return 0

    _publish(args.env, workspace_id, manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())

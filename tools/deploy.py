"""Thin wrapper around fabric-cicd 1.1.0 for the Payer demo.

Reads deployment.yaml + workspace/parameter.yml, validates the workspace tree
shape, then publishes via the fabric-cicd Python API. Designed so the same
invocation works locally (developer push) and in GitHub Actions.

Usage:
    python tools/deploy.py --env dev
    python tools/deploy.py --env prod --confirm
    python tools/deploy.py --env dev --dry-run
    python tools/deploy.py --env dev --dry-run --only DataAgent
    python tools/deploy.py --env staging --explain
    python tools/deploy.py --check

Environment variables required (per env):
    FABRIC_WORKSPACE_ID_<ENV>     target workspace GUID
    FABRIC_CAPACITY_ID_<ENV>      Fabric capacity GUID (informational)
    AZURE_TENANT_ID               for the identity that publishes
    AZURE_CLIENT_ID               (only when not using DefaultAzureCredential)
    AZURE_CLIENT_SECRET           (only when not using MSI / az login)

fabric-cicd v1.0.0 removed the implicit credential fallback, so we now pass an
explicit `token_credential=DefaultAzureCredential()` — works with `az login`
locally, with `AZURE_CLIENT_ID/SECRET` in CI, and with workspace MSI in Fabric.

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
# Note: HostedAgent (Foundry hosted agents, preview) is NOT a fabric-cicd item
# type — those deploy via the Foundry SDK / container registry, not via the
# Fabric workspace tree. PAReviewCopilot (Stream B.4) lives under
# data_agents/PAReviewCopilot.HostedAgent/ and is published by
# tools/deploy_data_agents.py (`deploy_hosted_agent`), not here.
# Source: https://microsoft.github.io/fabric-cicd/latest/#supported-item-types
SUPPORTED_TYPES = {
    "Lakehouse",
    "Notebook",
    "DataPipeline",
    "Environment",
    "SemanticModel",
    "Report",
    "DataAgent",
    "Ontology",
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


def _apply_only_filter(
    items: dict[str, list[str]],
    item_order: list[str],
    only: str | None,
) -> tuple[dict[str, list[str]], list[str]]:
    """Restrict items + itemOrder to a single ItemType.

    Used to re-publish just one slice of the workspace (e.g. `--only DataAgent`
    after a launcher Cell-3 rebind regen).
    """
    if only is None:
        return items, item_order
    if only not in SUPPORTED_TYPES:
        sys.exit(
            f"[deploy] --only {only!r}: not a fabric-cicd-supported item type. "
            f"Choose from {sorted(SUPPORTED_TYPES)}."
        )
    if only not in item_order:
        sys.exit(
            f"[deploy] --only {only!r}: not in deployment.yaml itemOrder "
            f"({item_order})."
        )
    if only not in items:
        sys.exit(
            f"[deploy] --only {only!r}: no folders of that type under workspace/."
        )
    return {only: items[only]}, [only]


def _apply_skip_optional_filter(
    items: dict[str, list[str]],
    manifest: dict,
) -> dict[str, list[str]]:
    """Drop items listed under spec.optionalItems (e.g. RTI scaffolds without
    definition files)."""
    optional = set(manifest["spec"].get("optionalItems") or [])
    if not optional:
        return items
    filtered: dict[str, list[str]] = {}
    for kind, names in items.items():
        kept = [n for n in names if f"{n}.{kind}" not in optional]
        if kept:
            filtered[kind] = kept
    return filtered


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


def _render_plan_table(items: dict[str, list[str]], item_order: list[str]) -> None:
    """Per-item plan printed before live publish so logs show what was attempted.

    fabric-cicd does not return a structured per-item result we can post-process;
    printing the plan up front gives operators the same visibility a real summary
    would, and aligns the live-mode log with the --dry-run preview.
    """
    print("-" * 72)
    print("[deploy] publish plan (in itemOrder):")
    total = 0
    for kind in item_order:
        names = items.get(kind, [])
        if not names:
            continue
        for n in names:
            print(f"    {kind:14s}  {n}")
            total += 1
    print(f"[deploy] {total} item(s) will be published.")
    print("-" * 72)


def _load_parameter_rules() -> list[dict]:
    if not PARAMETER_YAML.is_file():
        sys.exit(f"[deploy] {PARAMETER_YAML} missing")
    doc = yaml.safe_load(PARAMETER_YAML.read_text(encoding="utf-8")) or {}
    return doc.get("find_replace", []) or []


def _render_explain(env: str) -> int:
    """For each parameter.yml rule, show what it resolves to for `env`.

    Surfaces missing/unset $ENV_VAR references that would otherwise cause a
    silent identity-passthrough at publish time. Returns 1 if any variable is
    unset (so CI can gate on it), else 0.
    """
    rules = _load_parameter_rules()
    print("=" * 72)
    print(f"[deploy] --explain env={env}  rules={len(rules)}")
    print("=" * 72)
    missing: list[str] = []
    for rule in rules:
        find = rule.get("find_value", "<no find_value>")
        replace_map = rule.get("replace_value", {}) or {}
        raw = replace_map.get(env)
        if raw is None:
            print(f"  {find}")
            print(f"    [no rule for env={env}]")
            continue
        if isinstance(raw, str) and raw.startswith("$"):
            var = raw.lstrip("$")
            val = os.environ.get(var)
            if val:
                shown = val[:8] + "..." if len(val) > 12 else val
                print(f"  {find}")
                print(f"    -> ${var} = {shown}")
            else:
                missing.append(var)
                print(f"  {find}")
                print(f"    -> ${var}  [UNSET]")
        else:
            print(f"  {find}")
            print(f"    -> {raw}  [literal]")
    print()
    if missing:
        print(f"[deploy] {len(missing)} env var(s) unset for env={env}: {sorted(set(missing))}")
        return 1
    print(f"[deploy] all {len(rules)} parameter.yml rules resolve for env={env}.")
    return 0


def _render_check() -> int:
    """Drift check: every parameter.yml find_value with a logicalId shape must
    point at a real `.platform` logicalId in workspace/, and every `.platform`
    logicalId must be referenced by some parameter.yml rule.

    Catches the two most common parameter.yml regressions:
      - A `.platform` folder was added but parameter.yml was not extended
        (the new item would deploy with its zero-GUID artifactId references
        unrewritten, breaking cross-tenant promotion).
      - A `.platform` was renamed/deleted but its parameter.yml block was
        not pruned (silent dead config).

    Live-Fabric drift (local manifest vs published workspace) is out of scope
    here — that path requires network + auth and is not useful as a CI gate.
    """
    rules = _load_parameter_rules()
    items = _discover_items()

    platform_lids: dict[str, str] = {}
    for kind, names in items.items():
        for n in names:
            plat = WORKSPACE_DIR / f"{n}.{kind}" / ".platform"
            doc = json.loads(plat.read_text(encoding="utf-8"))
            platform_lids[doc["config"]["logicalId"]] = f"{n}.{kind}"

    rule_lids = {
        r["find_value"] for r in rules
        if isinstance(r.get("find_value"), str) and len(r["find_value"]) == 36
    }

    # Workspace-id placeholders (e.g. the PayerAnalytics DirectLake URL's
    # workspace segment) are intentional non-item sentinels: they rewrite to the
    # target workspace id, not to any workspace/<*> item, so they have no
    # `.platform` logicalId. Exempt them from the dead-rule gate.
    def _is_workspace_placeholder(rule: dict) -> bool:
        rv = rule.get("replace_value")
        if not isinstance(rv, dict):
            return False
        return any(
            isinstance(v, str) and v.startswith("$FABRIC_WORKSPACE_ID")
            for v in rv.values()
        )

    workspace_placeholder_lids = {
        r["find_value"] for r in rules
        if isinstance(r.get("find_value"), str) and _is_workspace_placeholder(r)
    }

    missing_rules = sorted(set(platform_lids) - rule_lids)
    dead_rules = sorted(rule_lids - set(platform_lids) - workspace_placeholder_lids)

    print("=" * 72)
    print("[deploy] --check  (parameter.yml <-> workspace/ drift)")
    print("=" * 72)
    print(f"  .platform logicalIds: {len(platform_lids)}")
    print(f"  parameter.yml rules (logicalId-shaped): {len(rule_lids)}")

    if missing_rules:
        print()
        print("  .platform logicalIds with NO parameter.yml rule:")
        for lid in missing_rules:
            print(f"    - {lid}  ({platform_lids[lid]})")
    if dead_rules:
        print()
        print("  parameter.yml rules with NO matching .platform:")
        for lid in dead_rules:
            print(f"    - {lid}")

    if missing_rules or dead_rules:
        print()
        print("[deploy] --check FAILED. Update workspace/parameter.yml or workspace/<*>/.platform.")
        return 1
    print()
    print("[deploy] --check OK. parameter.yml and workspace/ are in sync.")
    return 0


def _publish(
    env: str,
    workspace_id: str,
    manifest: dict,
    item_order: list[str],
) -> None:
    """Invoke fabric-cicd. Imports are lazy so dry-run + tests don't need the SDK."""
    try:
        fc = importlib.import_module("fabric_cicd")
    except ImportError:
        sys.exit(
            "[deploy] fabric-cicd is not installed in this environment. "
            "Install via `pip install fabric-cicd==1.1.0`."
        )
    try:
        identity = importlib.import_module("azure.identity")
    except ImportError:
        sys.exit(
            "[deploy] azure-identity is not installed in this environment. "
            "Install via `pip install azure-identity>=1.19`."
        )

    publish_cls = getattr(fc, "FabricWorkspace", None)
    if publish_cls is None:
        sys.exit("[deploy] fabric-cicd: FabricWorkspace not found — SDK version mismatch?")

    # Rebind DataAgent datasource.json files in a staging copy of workspace/.
    # Repo source-of-truth keeps zero-GUID placeholders (portable across tenants);
    # fabric-cicd reads from the staged copy with live workspace+item GUIDs.
    from bind_data_agent_sources import stage_workspace  # noqa: PLC0415
    repository_directory = str(stage_workspace(workspace_id))

    # fabric-cicd v1.0.0 removed implicit credential fallback; an explicit
    # token_credential is now mandatory. DefaultAzureCredential covers az login,
    # CI service principals (AZURE_CLIENT_ID/SECRET), and workspace MSI.
    ws = publish_cls(
        workspace_id=workspace_id,
        repository_directory=repository_directory,
        item_type_in_scope=item_order,
        environment=env,
        token_credential=identity.DefaultAzureCredential(),
    )

    # `manifest` retained for future per-item-callback wiring; fabric-cicd 1.1.0
    # does not expose a structured publish result, so we pre-print the plan
    # table from main() and rely on the SDK's own log line for per-item status.
    del manifest

    print(f"[deploy] publishing to env={env} workspace={workspace_id}")
    try:
        fc.publish_all_items(ws)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"[deploy] fabric-cicd publish failed: {exc}")
    print("[deploy] publish succeeded")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Deploy the Payer Fabric workspace via fabric-cicd 1.1.0")
    p.add_argument("--env", choices=["dev", "staging", "prod"],
                   help="Required for --dry-run, --explain, and live publish. Not required for --check.")
    p.add_argument("--dry-run", action="store_true", help="Preview the deploy without calling fabric-cicd")
    p.add_argument(
        "--confirm",
        action="store_true",
        help="Required for --env prod (guard against accidental prod publishes)",
    )
    p.add_argument(
        "--only",
        metavar="ItemType",
        default=None,
        help="Restrict the publish to a single fabric-cicd item type (e.g. DataAgent). "
             "Useful for re-publishing just one slice after a rebind.",
    )
    p.add_argument(
        "--skip-optional",
        action="store_true",
        help="Skip items listed under spec.optionalItems in deployment.yaml "
             "(e.g. RTI scaffolds that need definition files before re-publish).",
    )
    p.add_argument(
        "--explain",
        action="store_true",
        help="Print, per parameter.yml rule, what it resolves to for the chosen --env. "
             "Exits non-zero if any referenced env var is unset.",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Verify parameter.yml is in sync with workspace/ .platform logicalIds. "
             "Does not require --env or network access.",
    )
    args = p.parse_args(argv)

    if args.check:
        return _render_check()

    if not args.env:
        sys.exit("[deploy] --env is required (unless using --check)")

    if args.explain:
        return _render_explain(args.env)

    if args.env == "prod" and not (args.confirm or args.dry_run):
        sys.exit("[deploy] --env prod requires --confirm (or --dry-run for preview)")

    manifest = _load_manifest()
    items = _discover_items()
    _validate(manifest, items)
    if args.skip_optional:
        items = _apply_skip_optional_filter(items, manifest)
    items, item_order = _apply_only_filter(items, manifest["spec"]["itemOrder"], args.only)
    # Drop item types from scope when no items of that type remain after filtering
    # — fabric-cicd's publish_all_items scans repository_directory directly and
    # would otherwise still try to publish skipped items.
    item_order = [t for t in item_order if t in items]

    workspace_id = (
        "<dry-run-placeholder>" if args.dry_run else _resolve_workspace_id(manifest, args.env)
    )

    if args.dry_run:
        # Build a shallow shim so _render_preview honors the --only filter.
        preview_manifest = dict(manifest)
        preview_manifest["spec"] = dict(manifest["spec"])
        preview_manifest["spec"]["itemOrder"] = item_order
        _render_preview(preview_manifest, items, workspace_id)
        return 0

    _render_plan_table(items, item_order)
    _publish(args.env, workspace_id, manifest, item_order)
    return 0


if __name__ == "__main__":
    sys.exit(main())

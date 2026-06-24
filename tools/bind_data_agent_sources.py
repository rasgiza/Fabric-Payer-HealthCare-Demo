"""Stage `workspace/` into `.staging/workspace/` with live DataAgent GUIDs.

DataAgent items embed datasource.json files under
`<Agent>.DataAgent/Files/Config/{draft,published}/<source-type>-<displayName>/`
where source-type ∈ {graph, lakehouse-tables, semantic-model}. Each file has
`artifactId` (item GUID) and `workspaceId` that must point to a real item in
the target Fabric workspace; fabric-cicd 1.1.0 rejects empty-GUID values.

The repo source-of-truth stores `00000000-...` placeholders so it stays
workspace-agnostic and portable across tenants. This tool produces a staging
copy whose datasource.json files are rebound to live GUIDs (looked up by
displayName via Fabric REST API), and drops any datasource folder whose
target item is not present in the workspace (e.g. `graph-Payer_Ontology`
while Ontology preview is deferred to phase 2).

`tools/deploy.py` calls `stage_workspace()` automatically before
`fabric-cicd.publish_all_items`, pointing the SDK at `.staging/workspace/`
instead of `workspace/`. Direct CLI invocation is supported for inspection.

Usage:
    python tools/bind_data_agent_sources.py --workspace-id <GUID>           # dry-run preview
    python tools/bind_data_agent_sources.py --workspace-id <GUID> --apply   # write .staging/workspace/
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = REPO_ROOT / "workspace"
STAGING_DIR = REPO_ROOT / ".staging" / "workspace"
ZERO_GUID = "00000000-0000-0000-0000-000000000000"

FOLDER_TYPE_TO_FABRIC_TYPE = {
    "lakehouse-tables": "Lakehouse",
    "semantic-model": "SemanticModel",
    "graph": "Ontology",
}


def _fetch_workspace_items(workspace_id: str) -> dict[tuple[str, str], str]:
    """Returns {(itemType, displayName): itemId} for every item in the workspace."""
    url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items"
    result = subprocess.run(
        ["az", "rest", "--method", "get", "--url", url,
         "--resource", "https://api.fabric.microsoft.com",
         "--query", "value[].{type:type, name:displayName, id:id}", "-o", "json"],
        capture_output=True, text=True, check=False, shell=True,
    )
    if result.returncode != 0:
        sys.exit(f"[bind] az rest failed: {result.stderr.strip()}")
    items = json.loads(result.stdout)
    return {(it["type"], it["name"]): it["id"] for it in items}


def _parse_folder_name(folder_name: str) -> tuple[str, str] | None:
    for prefix, fabric_type in FOLDER_TYPE_TO_FABRIC_TYPE.items():
        if folder_name.startswith(prefix + "-"):
            return fabric_type, folder_name[len(prefix) + 1:]
    return None


def _rewrite_agent(agent_dir: Path, workspace_id: str,
                   live_items: dict[tuple[str, str], str],
                   *, apply: bool, log: bool) -> tuple[int, int, int]:
    rewrote = removed = skipped = 0
    for stage in ("draft", "published"):
        stage_dir = agent_dir / "Files" / "Config" / stage
        if not stage_dir.is_dir():
            continue
        for sub in sorted(stage_dir.iterdir()):
            if not sub.is_dir():
                continue
            parsed = _parse_folder_name(sub.name)
            if not parsed:
                continue
            fabric_type, display_name = parsed
            live_id = live_items.get((fabric_type, display_name))
            ds_file = sub / "datasource.json"

            if live_id is None:
                if log:
                    verb = "REMOVE" if apply else "would REMOVE"
                    print(f"  [{verb}] {sub.relative_to(REPO_ROOT)}  "
                          f"({fabric_type} '{display_name}' not in workspace)")
                if apply:
                    shutil.rmtree(sub)
                removed += 1
                continue

            if not ds_file.is_file():
                skipped += 1
                continue
            ds = json.loads(ds_file.read_text(encoding="utf-8"))
            if ds.get("artifactId") == live_id and ds.get("workspaceId") == workspace_id:
                skipped += 1
                continue
            if log:
                verb = "REWRITE" if apply else "would REWRITE"
                print(f"  [{verb}] {ds_file.relative_to(REPO_ROOT)}")
                print(f"           artifactId  -> {live_id}")
                print(f"           workspaceId -> {workspace_id}")
            if apply:
                ds["artifactId"] = live_id
                ds["workspaceId"] = workspace_id
                ds_file.write_text(json.dumps(ds, indent=2) + "\n", encoding="utf-8")
            rewrote += 1
    return rewrote, removed, skipped


def stage_workspace(workspace_id: str, *, log: bool = True) -> Path:
    """Copy `workspace/` to `.staging/workspace/`, rebind DataAgents, return path.

    Call this from `tools/deploy.py` right before `fabric-cicd.publish_all_items`.
    The repo `workspace/` tree is never mutated.
    """
    if log:
        print(f"[bind] staging {WORKSPACE_DIR} -> {STAGING_DIR}")
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    STAGING_DIR.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(WORKSPACE_DIR, STAGING_DIR)

    live_items = _fetch_workspace_items(workspace_id)
    if log:
        print(f"[bind] found {len(live_items)} live item(s) in workspace {workspace_id}")

    total_rewrote = total_removed = 0
    for agent_dir in sorted(STAGING_DIR.glob("*.DataAgent")):
        if log:
            print(f"[bind] {agent_dir.name}")
        r, rm, _ = _rewrite_agent(agent_dir, workspace_id, live_items, apply=True, log=log)
        total_rewrote += r
        total_removed += rm

    if log:
        print(f"[bind] staging complete: rewrote {total_rewrote} datasource(s), "
              f"removed {total_removed} unbound folder(s).")
    return STAGING_DIR


def _main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Stage workspace/ with live DataAgent GUIDs.")
    p.add_argument("--workspace-id", required=True, help="Target Fabric workspace GUID")
    p.add_argument("--apply", action="store_true",
                   help="Materialize .staging/workspace/ (default is dry-run preview)")
    args = p.parse_args(argv)

    if args.apply:
        stage_workspace(args.workspace_id, log=True)
        return 0

    print(f"[bind] DRY-RUN against workspace_id={args.workspace_id} "
          f"(no files written; use --apply to materialize .staging/)")
    live_items = _fetch_workspace_items(args.workspace_id)
    print(f"[bind] found {len(live_items)} live item(s)")
    for (t, n), i in sorted(live_items.items()):
        print(f"         {t:<14} {n:<46} {i}")
    print()

    total_rewrote = total_removed = total_skipped = 0
    for agent_dir in sorted(WORKSPACE_DIR.glob("*.DataAgent")):
        print(f"[bind] {agent_dir.name}")
        r, rm, sk = _rewrite_agent(agent_dir, args.workspace_id, live_items,
                                    apply=False, log=True)
        total_rewrote += r
        total_removed += rm
        total_skipped += sk
    print()
    print(f"[bind] DRY-RUN summary: would rewrite {total_rewrote} datasource(s), "
          f"would remove {total_removed} unbound folder(s), {total_skipped} already correct.")
    return 0


if __name__ == "__main__":
    sys.exit(_main())

"""Phase 4 / C.4 — clone a template DataAgent into a new agent folder.

The 7 baseline DataAgents under `workspace/<Name>.DataAgent/` were authored by
hand once and now drive ~13 JSON files each. To add an 8th agent (or future
agents) without copy-paste drift we clone an existing one and substitute:

  - `.platform` displayName + logicalId
  - `manifest.json` agentName
  - `Files/Config/publish_info.json` description
  - `Files/Config/{draft,published}/stage_config.json` aiInstructions
  - `Files/Config/{draft,published}/lakehouse-tables-*/datasource.json`
    dataSourceInstructions, userDescription, and per-table `is_selected`
    (matching the new binding.yaml table_allowlist)
  - `Files/Config/{draft,published}/semantic-model-*/datasource.json`
    same idea
  - `Files/Config/{draft,published}/graph-*/datasource.json`
    select graph entities whose source_table is in the allowlist
    (mirrors `tests/test_data_agent_shape.test_graph_selected_matches_allowlist_intersection`)

Usage:
    python tools/clone_data_agent.py \\
        --template SIUAgent \\
        --target ClaimsRawExplorer \\
        --display "Claims Raw Explorer" \\
        --logical-id d5000005-0001-0001-0001-000000000010 \\
        --persona ClaimsOps \\
        --apply

Without `--apply` the tool prints a dry-run plan and exits 0.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
AUTHORING = REPO / "data_agents"
WORKSPACE = REPO / "workspace"
ONTOLOGY = WORKSPACE / "Payer_Ontology.Ontology"


def _binding(agent: str) -> dict:
    return yaml.safe_load(
        (AUTHORING / f"{agent}.DataAgent" / "binding.yaml").read_text(encoding="utf-8")
    )


def _instructions(agent: str) -> str:
    return (AUTHORING / f"{agent}.DataAgent" / "aiInstructions.md").read_text(encoding="utf-8")


def _entity_to_source_table() -> dict[str, str]:
    out: dict[str, str] = {}
    for ent_dir in (ONTOLOGY / "EntityTypes").iterdir():
        defn = json.loads((ent_dir / "definition.json").read_text(encoding="utf-8"))
        binding_files = list((ent_dir / "DataBindings").glob("*.json"))
        if not binding_files:
            continue
        b = json.loads(binding_files[0].read_text(encoding="utf-8"))
        out[defn["name"]] = b["dataBindingConfiguration"]["sourceTableProperties"][
            "sourceTableName"
        ]
    return out


def _patch_lakehouse(ds: dict, allowlist: set[str], target: str, display: str) -> dict:
    ds = json.loads(json.dumps(ds))
    ds["dataSourceInstructions"] = (
        f"Gold-layer lakehouse for the {target} persona. "
        "Use SQL for detail-row queries, TOP-N lists, and filtered lookups across the allowed "
        "tables. Always JOIN on _key columns. Prefer the PayerAnalytics semantic model for KPIs "
        "/ percentages / fleet-wide aggregates (DAX measures are pre-computed)."
    )
    ds["userDescription"] = (
        f"Gold lakehouse tables exposed to {target} (allowlist: {sorted(allowlist)!s})."
    )
    tables = ds["elements"][0]["children"][0]["children"][0]["children"]
    for t in tables:
        wants = t["display_name"] in allowlist
        t["is_selected"] = wants
        for c in t.get("children", []):
            c["is_selected"] = wants
    return ds


def _patch_sm(ds: dict, allowlist: set[str], target: str, display: str) -> dict:
    ds = json.loads(json.dumps(ds))
    ds["dataSourceInstructions"] = (
        f"PayerAnalytics semantic model for the {target} persona. Use DAX measures from "
        "PaymentIntegrity / Operations folders for KPIs. For row-level detail use the lakehouse_tables data source."
    )
    ds["userDescription"] = (
        f"PayerAnalytics SM exposed to {target} (allowlist: {sorted(allowlist)!s})."
    )
    for t in ds["elements"]:
        wants = t["display_name"] in allowlist
        t["is_selected"] = wants
        for c in t.get("children", []):
            c["is_selected"] = wants
    return ds


def _patch_graph(
    ds: dict, allowlist: set[str], target: str, display: str, ent_to_table: dict[str, str]
) -> dict:
    ds = json.loads(json.dumps(ds))
    ds["dataSourceInstructions"] = (
        f"Payer_Ontology graph for the {target} persona. Use graph queries for cross-entity "
        "traversal (member ↔ provider ↔ claim) — not for KPIs."
    )
    wanted_entities = {n for n, src in ent_to_table.items() if src in allowlist}
    ds["userDescription"] = (
        f"Payer_Ontology entities exposed to {target} (resolved from allowlist intersect): "
        f"{sorted(wanted_entities)!s}."
    )
    for e in ds["elements"]:
        wants = e["display_name"] in wanted_entities
        e["is_selected"] = wants
        for c in e.get("children", []):
            c["is_selected"] = wants
    return ds


def _stage_config(target: str, instructions: str) -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/stageConfiguration/1.0.0/schema.json",
        "aiInstructions": instructions,
    }


def _publish_info(target: str, display: str, binding: dict) -> dict:
    allow = binding["fabric_data_agent"]["table_allowlist"]
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/publishInfo/1.0.0/schema.json",
        "description": (
            f"{display} ({target}) for the "
            f"{', '.join(binding['personas_owned'])} persona(s). "
            "Bound to PayerAnalytics semantic model (Direct Lake over lh_gold_curated) and the "
            f"Payer_Ontology graph. Allowed gold tables: {', '.join(allow)}."
        ),
    }


def _platform(target: str, display: str, logical_id: str) -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "DataAgent", "displayName": target},
        "config": {"version": "2.0", "logicalId": logical_id},
    }


def _manifest(target: str) -> dict:
    return {
        "agentName": target,
        "exportedParts": [
            {"path": "Files/Config/data_agent.json", "payloadType": "InlineBase64"},
            {"path": "Files/Config/draft/stage_config.json", "payloadType": "InlineBase64"},
            {
                "path": "Files/Config/draft/lakehouse-tables-lh_gold_curated/datasource.json",
                "payloadType": "InlineBase64",
            },
            {
                "path": "Files/Config/draft/semantic-model-PayerAnalytics/datasource.json",
                "payloadType": "InlineBase64",
            },
            {
                "path": "Files/Config/draft/graph-Payer_Ontology/datasource.json",
                "payloadType": "InlineBase64",
            },
            {"path": "Files/Config/published/stage_config.json", "payloadType": "InlineBase64"},
            {
                "path": "Files/Config/published/lakehouse-tables-lh_gold_curated/datasource.json",
                "payloadType": "InlineBase64",
            },
            {
                "path": "Files/Config/published/semantic-model-PayerAnalytics/datasource.json",
                "payloadType": "InlineBase64",
            },
            {
                "path": "Files/Config/published/graph-Payer_Ontology/datasource.json",
                "payloadType": "InlineBase64",
            },
            {"path": "Files/Config/publish_info.json", "payloadType": "InlineBase64"},
            {"path": ".platform", "payloadType": "InlineBase64"},
        ],
    }


def _data_agent_root() -> dict:
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/dataAgent/definition/dataAgent/2.1.0/schema.json"
    }


def _write_json(path: Path, payload: dict, apply: bool) -> None:
    if not apply:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clone(
    *,
    template: str,
    target: str,
    display: str,
    logical_id: str,
    apply: bool,
) -> int:
    tpl_ws = WORKSPACE / f"{template}.DataAgent"
    tgt_ws = WORKSPACE / f"{target}.DataAgent"
    tgt_authoring = AUTHORING / f"{target}.DataAgent"

    if not tpl_ws.is_dir():
        print(f"[clone] FAIL template workspace dir not found: {tpl_ws}", file=sys.stderr)
        return 2
    if not tgt_authoring.is_dir():
        print(
            f"[clone] FAIL target authoring dir missing — create "
            f"data_agents/{target}.DataAgent/{{binding.yaml,aiInstructions.md,fewshots.jsonl,eval/cases.jsonl}} first",
            file=sys.stderr,
        )
        return 2

    binding = _binding(target)
    instructions = _instructions(target)
    allowlist = set(binding["fabric_data_agent"]["table_allowlist"])
    ent_to_table = _entity_to_source_table()
    wanted_entities = {n for n, src in ent_to_table.items() if src in allowlist}

    print(f"[clone] template = workspace/{template}.DataAgent")
    print(f"[clone] target   = workspace/{target}.DataAgent")
    print(f"[clone] display  = {display}")
    print(f"[clone] logical  = {logical_id}")
    print(f"[clone] allow    = {sorted(allowlist)}")
    print(f"[clone] graph entities (intersect): {sorted(wanted_entities)}")

    if tgt_ws.exists() and apply:
        print(f"[clone] removing existing {tgt_ws}")
        shutil.rmtree(tgt_ws)

    # 1. .platform + manifest + data_agent.json + publish_info.json
    _write_json(tgt_ws / ".platform", _platform(target, display, logical_id), apply)
    _write_json(tgt_ws / "manifest.json", _manifest(target), apply)
    _write_json(tgt_ws / "Files" / "Config" / "data_agent.json", _data_agent_root(), apply)
    _write_json(
        tgt_ws / "Files" / "Config" / "publish_info.json",
        _publish_info(target, display, binding),
        apply,
    )

    # 2. draft + published stage_config.json + datasources
    tpl_cfg = tpl_ws / "Files" / "Config"
    for stage in ("draft", "published"):
        stage_cfg_path = tgt_ws / "Files" / "Config" / stage / "stage_config.json"
        _write_json(stage_cfg_path, _stage_config(target, instructions), apply)

        for sub_kind, patch_fn in (
            ("lakehouse-tables-lh_gold_curated", _patch_lakehouse),
            ("semantic-model-PayerAnalytics", _patch_sm),
        ):
            src = tpl_cfg / stage / sub_kind / "datasource.json"
            ds = json.loads(src.read_text(encoding="utf-8"))
            new_ds = patch_fn(ds, allowlist, target, display)
            _write_json(
                tgt_ws / "Files" / "Config" / stage / sub_kind / "datasource.json",
                new_ds,
                apply,
            )

        # graph needs the entity intersection
        src = tpl_cfg / stage / "graph-Payer_Ontology" / "datasource.json"
        ds = json.loads(src.read_text(encoding="utf-8"))
        new_ds = _patch_graph(ds, allowlist, target, display, ent_to_table)
        _write_json(
            tgt_ws / "Files" / "Config" / stage / "graph-Payer_Ontology" / "datasource.json",
            new_ds,
            apply,
        )

    mode = "APPLIED" if apply else "DRY-RUN ok"
    print(f"[clone] {mode}: {target} cloned from {template}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Clone a workspace DataAgent template into a new agent.")
    p.add_argument("--template", required=True, help="source agent name (folder stem)")
    p.add_argument("--target", required=True, help="new agent name (folder stem)")
    p.add_argument("--display", required=True, help='.platform displayName must equal target')
    p.add_argument("--logical-id", required=True, help="logical_id (uuid)")
    p.add_argument("--apply", action="store_true", help="actually write files (default = dry-run)")
    args = p.parse_args(argv)

    if args.display != args.target:
        print(
            "[clone] WARN: display != target; tests/test_data_agent_shape.test_platform_descriptors "
            "asserts displayName == folder stem. Setting displayName=target.",
            file=sys.stderr,
        )

    return clone(
        template=args.template,
        target=args.target,
        display=args.target,
        logical_id=args.logical_id,
        apply=args.apply,
    )


if __name__ == "__main__":
    raise SystemExit(main())

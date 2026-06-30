"""
build_pbi_report.py - [DEPRECATED] Schematic PBIR generator from powerbi/pages.yaml.

.. deprecated::
    The authoritative, deployable report now lives at
    ``workspace/PayerAnalytics.Report`` and is generated as REAL Power BI PBIR
    (v4.0) bound to the live PayerAnalytics semantic model using the ``pbir``
    CLI (see the ``_build_payer_report.py`` driver at the repo root). That report
    is the one fabric-cicd deploys (it is listed in ``deployment.yaml`` itemOrder
    and the jumpstart manifests point ``items.report.source`` at it).

    This script emits a *schematic* (not visual-pixel-perfect) report into the
    legacy ``powerbi/PayerAnalytics.Report`` folder using a custom simplified
    JSON shape that Power BI will NOT render. It is retained only as a reference
    for the ``powerbi/pages.yaml`` design intent and is no longer wired into any
    deploy path. Running it requires the explicit ``--force-legacy`` flag.

Output (legacy):
  powerbi/PayerAnalytics.Report/
    definition.pbir              (points at the semantic model)
    definition/
      report.json                (top-level report def)
      pages.json                 (page index)
      pages/<id>/page.json       (per-page definition)
      pages/<id>/visuals/<id>.json

The output is intentionally schematic (not visual-pixel-perfect). Visual
positions use a 4-column grid auto-layout.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PAGES_YAML = ROOT / "powerbi" / "pages.yaml"
OUT = ROOT / "powerbi" / "PayerAnalytics.Report"

GRID_COLS = 4
TILE_W = 320
TILE_H = 200
PAGE_W = TILE_W * GRID_COLS + 40
PAGE_H = 720


def emit_pbir(dataset: str) -> str:
    return json.dumps({
        "version": "1.0",
        "datasetReference": {
            "byPath": {"path": f"../{dataset}.SemanticModel"},
            "byConnection": None,
        },
    }, indent=2)


def emit_report() -> str:
    return json.dumps({
        "themeCollection": {"baseTheme": {"name": "CY24SU10"}},
        "layoutOptimization": 0,
        "config": json.dumps({"version": "5.43"}),
        "resourcePackages": [],
    }, indent=2)


def emit_pages_index(pages) -> str:
    return json.dumps({
        "activePageName": pages[0]["id"],
        "pageOrder": [p["id"] for p in pages],
    }, indent=2)


def emit_page(page) -> str:
    is_tooltip = page.get("page_kind") == "tooltip"
    return json.dumps({
        "name": page["id"],
        "displayName": page["display"],
        "displayOption": 1,
        "width": PAGE_W if not is_tooltip else 320,
        "height": PAGE_H if not is_tooltip else 240,
        "pageType": "Tooltip" if is_tooltip else "Standard",
        "filters": ([{"column": page["page_filter"]}] if page.get("page_filter") else []),
        "annotations": {
            "persona": page.get("persona", ""),
            "description": page.get("description", ""),
            "locked": page.get("locked", False),
        },
        "visualOrder": [v["id"] for v in page["visuals"]],
    }, indent=2)


def emit_visual(visual, idx) -> str:
    row, col = divmod(idx, GRID_COLS)
    return json.dumps({
        "name": visual["id"],
        "visualType": visual["type"],
        "title": visual.get("title", ""),
        "position": {
            "x": 20 + col * TILE_W,
            "y": 20 + row * TILE_H,
            "width": visual.get("width", TILE_W - 16),
            "height": visual.get("height", TILE_H - 16),
        },
        "fields": {
            "measures": visual.get("measures", []),
            "axis": visual.get("axis"),
            "legend": visual.get("legend"),
            "rows": visual.get("fields", []),
            "breakdown": visual.get("breakdown", []),
        },
    }, indent=2)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--clean", action="store_true")
    p.add_argument(
        "--force-legacy",
        action="store_true",
        help="Acknowledge this generator is DEPRECATED and emit the schematic "
             "powerbi/PayerAnalytics.Report anyway. The deployable report is "
             "workspace/PayerAnalytics.Report (built via pbir).",
    )
    args = p.parse_args()

    if not args.force_legacy:
        print(
            "[pbir] build_pbi_report.py is DEPRECATED. The deployable report is "
            "workspace/PayerAnalytics.Report (real PBIR bound to the live "
            "semantic model, built via the pbir CLI / _build_payer_report.py). "
            "Re-run with --force-legacy only if you specifically need the old "
            "schematic powerbi/PayerAnalytics.Report.",
            file=sys.stderr,
        )
        return 2

    if not PAGES_YAML.exists():
        print(f"[pbir] missing {PAGES_YAML}", file=sys.stderr)
        return 2

    if args.clean and OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "definition" / "pages").mkdir(parents=True, exist_ok=True)

    spec = yaml.safe_load(PAGES_YAML.read_text())
    pages = spec["pages"]
    dataset = spec["dataset"]

    (OUT / "definition.pbir").write_text(emit_pbir(dataset), encoding="utf-8")
    (OUT / "definition" / "report.json").write_text(emit_report(), encoding="utf-8")
    (OUT / "definition" / "pages.json").write_text(emit_pages_index(pages), encoding="utf-8")

    for page in pages:
        page_dir = OUT / "definition" / "pages" / page["id"]
        (page_dir / "visuals").mkdir(parents=True, exist_ok=True)
        (page_dir / "page.json").write_text(emit_page(page), encoding="utf-8")
        for idx, v in enumerate(page["visuals"]):
            (page_dir / "visuals" / f"{v['id']}.json").write_text(emit_visual(v, idx), encoding="utf-8")
        tag = " (LOCKED tooltip)" if page.get("page_kind") == "tooltip" else (" (LOCKED Phase 4-add)" if page.get("locked") else "")
        print(f"  + page {page['id']:24s} ({len(page['visuals'])} visuals){tag}")

    print(f"\n[pbir] OK -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

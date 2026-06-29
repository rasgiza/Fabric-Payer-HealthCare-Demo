"""Convert workspace/*.Notebook/notebook-content.py from legacy inline
``# METADATA **{json}**`` cell markers to Fabric Git Integration v2.0
canonical format (``# CELL ********************`` separators + ``# META {json}``
blocks).

Why: fabric-cicd 1.1.0 ships notebook-content.py bytes as-is. The Fabric
notebook parser only recognises the canonical asterisk-separator format; the
legacy inline form is silently treated as comment noise, leaving the
published notebook with a single empty cell. Symptom: open the notebook in
Fabric portal -> blank canvas, "Press Alt+I to get code from Copilot".

Source format (per-cell, what we have on disk)::

    # METADATA **{"language":"python"}**

    # CELL **{"language":"python"}**

    <cell body>

Canonical format (what Fabric expects)::

    # CELL ********************

    # METADATA ********************

    # META {
    # META   "language": "python",
    # META   "language_group": "synapse_pyspark"
    # META }

    <cell body>

Markdown cells use ``# MARKDOWN`` instead of ``# CELL`` and the body is
already comment-prefixed (each line starts with ``# ``).

Usage::

    python tools/convert_notebook_format.py            # dry-run, show diff
    python tools/convert_notebook_format.py --apply    # rewrite in place
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "workspace"

FILE_HEADER = "# Fabric notebook source"
SEP = "*" * 20
KERNEL_META = {"kernel_info": {"name": "synapse_pyspark"}}

# Matches the cell preamble:
#   # METADATA **{...}**
#   <blank lines>
#   # CELL **{...}**   OR  # MARKDOWN **{...}**
PREAMBLE_RE = re.compile(
    r"^# METADATA \*\*(?P<meta>\{.*?\})\*\*\s*\n"
    r"(?:\s*\n)*"
    r"^# (?P<kind>CELL|MARKDOWN) \*\*(?P<cell_meta>\{.*?\})\*\*\s*\n",
    re.MULTILINE,
)


def _emit_meta_block(obj: dict) -> str:
    """Render dict as ``# META`` prefixed JSON lines."""
    raw = json.dumps(obj, indent=2)
    return "\n".join(f"# META {line}" if line else "# META" for line in raw.splitlines())


def _emit_cell(kind: str, cell_meta: dict, body: str) -> str:
    """Emit one canonical cell block (CELL or MARKDOWN)."""
    body = body.strip("\n")
    return (
        f"# {kind} {SEP}\n\n"
        f"# METADATA {SEP}\n\n"
        f"{_emit_meta_block(cell_meta)}\n\n"
        f"{body}\n"
    )


def _emit_file_header() -> str:
    """File-level header + kernel metadata block."""
    return (
        f"{FILE_HEADER}\n\n"
        f"# METADATA {SEP}\n\n"
        f"{_emit_meta_block(KERNEL_META)}\n"
    )


def already_converted(text: str) -> bool:
    """True if file already uses canonical asterisk-separator format."""
    return f"# METADATA {SEP}" in text and f"# CELL {SEP}" in text


def convert(text: str) -> str:
    """Convert legacy ``**{...}**`` cells to canonical ``********************``."""
    if already_converted(text):
        return text

    matches = list(PREAMBLE_RE.finditer(text))
    if not matches:
        raise ValueError("no legacy cell markers found")

    out_parts: list[str] = [_emit_file_header()]
    for i, m in enumerate(matches):
        cell_meta = json.loads(m.group("cell_meta"))
        kind = m.group("kind")
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end]
        out_parts.append(_emit_cell(kind, cell_meta, body))

    return "\n".join(out_parts).rstrip() + "\n"


def find_notebooks(root: Path) -> list[Path]:
    return sorted(root.glob("*.Notebook/notebook-content.py"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true", help="rewrite files in place")
    p.add_argument("--path", type=Path, default=WORKSPACE, help="workspace dir")
    args = p.parse_args(argv)

    files = find_notebooks(args.path)
    if not files:
        print(f"no notebooks found under {args.path}", file=sys.stderr)
        return 1

    changed = 0
    skipped = 0
    for f in files:
        original = f.read_text(encoding="utf-8")
        try:
            new = convert(original)
        except ValueError as e:
            print(f"  SKIP  {f.relative_to(REPO_ROOT)}  ({e})")
            skipped += 1
            continue
        if new == original:
            print(f"  ok    {f.relative_to(REPO_ROOT)}  (already canonical)")
            continue
        delta = len(new) - len(original)
        sign = "+" if delta >= 0 else ""
        action = "WRITE" if args.apply else "would write"
        print(f"  {action:>11}  {f.relative_to(REPO_ROOT)}  ({sign}{delta} bytes)")
        if args.apply:
            f.write_text(new, encoding="utf-8")
        changed += 1

    print()
    print(f"converted: {changed}   skipped: {skipped}   total: {len(files)}")
    if not args.apply and changed:
        print("(dry-run — re-run with --apply to rewrite)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

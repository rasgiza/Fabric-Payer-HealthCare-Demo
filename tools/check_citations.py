"""Citation linter for the Fabric Payer Healthcare Demo.

Enforces three rules:

  1. Every ``[CIT:<id>]`` reference in any tracked ``*.md`` file resolves to an
     entry in ``citations.yaml``.
  2. Every entry in ``citations.yaml`` has non-empty ``url`` and ``quote``.
  3. Every ``time_sensitive: true`` entry has ``year >= MIN_TIME_SENSITIVE_YEAR``.

Exits non-zero on any violation. Run from repo root::

    python tools/check_citations.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CITATIONS_FILE = REPO_ROOT / "citations.yaml"
MIN_TIME_SENSITIVE_YEAR = 2024
CIT_PATTERN = re.compile(r"\[CIT:([A-Z0-9][A-Z0-9_\-]*)\]")
SCAN_GLOBS = ("**/*.md",)
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "synthea"}


def load_citations() -> dict:
    if not CITATIONS_FILE.exists():
        sys.exit(f"FATAL: {CITATIONS_FILE} not found")
    with CITATIONS_FILE.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {entry["id"]: entry for entry in data.get("citations", [])}


def iter_markdown_files() -> list[Path]:
    files: list[Path] = []
    for pattern in SCAN_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            files.append(path)
    return files


def main() -> int:
    citations = load_citations()
    errors: list[str] = []

    # Rule 2: schema validation
    for cid, entry in citations.items():
        if not entry.get("url"):
            errors.append(f"[schema] {cid}: missing or empty 'url'")
        if not entry.get("quote"):
            errors.append(f"[schema] {cid}: missing or empty 'quote'")
        if not isinstance(entry.get("year"), int):
            errors.append(f"[schema] {cid}: 'year' must be an integer")
        # Rule 3: freshness for time-sensitive citations
        if entry.get("time_sensitive") and isinstance(entry.get("year"), int):
            if entry["year"] < MIN_TIME_SENSITIVE_YEAR:
                errors.append(
                    f"[stale]  {cid}: time_sensitive=true but year={entry['year']} "
                    f"(must be >= {MIN_TIME_SENSITIVE_YEAR})"
                )

    # Rule 1: every [CIT:<id>] reference resolves
    referenced: set[str] = set()
    for md_file in iter_markdown_files():
        try:
            text = md_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in CIT_PATTERN.finditer(text):
            cid = match.group(1)
            referenced.add(cid)
            if cid not in citations:
                rel = md_file.relative_to(REPO_ROOT)
                errors.append(f"[unknown] {rel}: [CIT:{cid}] is not in citations.yaml")

    if errors:
        print("Citation linter FAILED:\n", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        print(
            f"\n{len(errors)} error(s). "
            f"{len(citations)} citations defined, {len(referenced)} referenced.",
            file=sys.stderr,
        )
        return 1

    print(
        f"Citation linter OK: {len(citations)} citations defined, "
        f"{len(referenced)} referenced, 0 errors."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Wraps `tools/check_citations.py` so the citation linter is part of pytest."""

from __future__ import annotations

from pathlib import Path

from tools import check_citations


def test_citation_linter_passes(repo_root: Path, monkeypatch) -> None:
    # check_citations.main() prints to stderr and returns 0/1. It uses module-level
    # REPO_ROOT, so chdir is not strictly required, but keep CWD predictable.
    monkeypatch.chdir(repo_root)
    rc = check_citations.main()
    assert rc == 0, "citation linter reported violations (see captured stderr)"

"""Wraps `tools/audit_rels.py` — verifies every ontology relationship resolves.

audit_rels.py uses argparse + sys.exit so we shell out via subprocess instead
of monkey-patching argv. The smoke graph is built from `data/graph/smoke/`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.smoke
@pytest.mark.slow
def test_audit_rels_smoke(repo_root: Path, smoke_graph_path: Path) -> None:
    cmd = [sys.executable, str(repo_root / "tools" / "audit_rels.py"), "--run-id", "smoke"]
    proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    assert proc.returncode == 0, (
        f"audit_rels exited {proc.returncode}\n"
        f"--- stdout ---\n{proc.stdout}\n"
        f"--- stderr ---\n{proc.stderr}"
    )

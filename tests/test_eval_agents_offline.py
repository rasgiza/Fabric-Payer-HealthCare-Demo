"""Wraps `tools/eval_agents_offline.py` — Phase 5 calibrated offline gate.

Asserts: >=30 happy cases, routing accuracy >=90%, refusal accuracy 100%,
every expected_measure resolves in measure_catalog.yaml, and every
HostedAgent artifact passes schema validation.
"""

from __future__ import annotations

from pathlib import Path

from tools import eval_agents_offline


def test_eval_agents_offline_passes(repo_root: Path, monkeypatch) -> None:
    monkeypatch.chdir(repo_root)
    rc = eval_agents_offline.main()
    assert rc == 0, "eval_agents_offline gate failed (see captured stdout)"

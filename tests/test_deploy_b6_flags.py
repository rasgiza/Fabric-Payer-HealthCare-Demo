"""B.6 — CLI tests for the new flags on `tools/deploy.py`.

Sister to `tests/test_deploy_data_agents_integration.py` (B.5). The flags
exercised here:
  --check         (parameter.yml <-> workspace/ logicalId drift)
  --explain       (per-rule env-var resolution; exits non-zero if any var unset)
  --only X        (restrict publish scope to a single ItemType)

All assertions are at the CLI / stdout level so a refactor of the internal
helper signatures cannot silently change operator-visible behavior.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run(repo_root: Path, *args: str, env_overrides: dict[str, str] | None = None
         ) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    # Strip every FABRIC_* / LH_* / NB_* / PL_* / *AGENT* / PAYER_* var that
    # could spuriously satisfy --explain on a developer machine. This keeps
    # the test deterministic locally vs CI.
    drop_prefixes = ("FABRIC_", "LH_", "NB_", "PL_", "HEALTHCARE_LAUNCHER",
                     "PAYER_ANALYTICS", "PAYER_ONTOLOGY")
    drop_suffixes = ("AGENT_DEV", "AGENT_STAGING", "AGENT_PROD")
    for k in list(env):
        if any(k.startswith(p) for p in drop_prefixes) or any(k.endswith(s) for s in drop_suffixes):
            del env[k]
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(repo_root / "tools" / "deploy.py"), *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


# ---------- --check ----------------------------------------------------------


def test_check_passes_in_sync_state(repo_root: Path) -> None:
    """`--check` must exit 0 today: parameter.yml covers all 29 logicalIds."""
    res = _run(repo_root, "--check")
    assert res.returncode == 0, (
        f"--check failed: stdout={res.stdout!r}  stderr={res.stderr!r}"
    )
    assert "--check OK" in res.stdout
    assert ".platform logicalIds: 29" in res.stdout
    assert "parameter.yml rules (logicalId-shaped): 29" in res.stdout


def test_check_does_not_require_env_flag(repo_root: Path) -> None:
    """`--check` works without `--env` so it can run in any CI stage."""
    res = _run(repo_root, "--check")
    assert res.returncode == 0


# ---------- --explain --------------------------------------------------------


def test_explain_reports_unset_vars_with_nonzero_exit(repo_root: Path) -> None:
    """With no env vars set, --explain must enumerate every unset $VAR and exit 1."""
    res = _run(repo_root, "--env", "dev", "--explain")
    assert res.returncode == 1, (
        f"--explain with no env vars should exit 1, got {res.returncode}; "
        f"stdout={res.stdout!r}"
    )
    assert "[UNSET]" in res.stdout
    # 4 lakehouse + 9 notebook (NB_00..NB_03 + launcher + NB_RTI_01..NB_RTI_04)
    # + 2 pipeline + 1 SM + 1 ontology + 8 agent + 1 Eventhouse + 1 KQLDatabase
    # + 1 Eventstream + 1 Reflex = 29 logicalIds + 1 workspace placeholder = 30 rules.
    assert "rules=30" in res.stdout
    # Mentions a known unset variable
    assert "LH_BRONZE_RAW_DEV" in res.stdout


def test_explain_resolves_when_env_vars_set(repo_root: Path) -> None:
    """When every $VAR for an env is set, --explain must exit 0 and show values."""
    # Set every var --explain will look up for env=dev.
    overrides = {
        "LH_BRONZE_RAW_DEV":          "11111111-1111-1111-1111-aaaaaaaaaaa1",
        "LH_SILVER_STAGE_DEV":        "11111111-1111-1111-1111-aaaaaaaaaaa2",
        "LH_SILVER_ODS_DEV":          "11111111-1111-1111-1111-aaaaaaaaaaa3",
        "LH_GOLD_CURATED_DEV":        "11111111-1111-1111-1111-aaaaaaaaaaa4",            "NB_00_GENERATE_SMOKE_DATA_DEV": "11111111-1111-1111-1111-bbbbbbbbbbb0",        "NB_01_BRONZE_INGEST_DEV":    "11111111-1111-1111-1111-bbbbbbbbbbb1",
        "NB_02_SILVER_TRANSFORM_DEV": "11111111-1111-1111-1111-bbbbbbbbbbb2",
        "NB_03_GOLD_BUILD_DEV":       "11111111-1111-1111-1111-bbbbbbbbbbb3",
        "HEALTHCARE_LAUNCHER_DEV":    "11111111-1111-1111-1111-bbbbbbbbbb99",
        "PL_PAYER_FULL_LOAD_DEV":     "11111111-1111-1111-1111-ccccccccccc1",
        "PL_PAYER_MASTER_DEV":        "11111111-1111-1111-1111-ccccccccccc2",
        "PAYER_ANALYTICS_DEV":        "11111111-1111-1111-1111-ddddddddddd1",
        "PAYER_ONTOLOGY_DEV":         "11111111-1111-1111-1111-ddddddddddd2",
        "CFOAGENT_DEV":               "11111111-1111-1111-1111-ddddddddddd3",
        "STARSAGENT_DEV":             "11111111-1111-1111-1111-ddddddddddd4",
        "RISKADJUSTMENTAGENT_DEV":    "11111111-1111-1111-1111-ddddddddddd5",
        "SIUAGENT_DEV":               "11111111-1111-1111-1111-ddddddddddd6",
        "CAREMGMTAGENT_DEV":          "11111111-1111-1111-1111-ddddddddddd7",
        "NETWORKAGENT_DEV":           "11111111-1111-1111-1111-ddddddddddd8",
        "UMAGENT_DEV":                "11111111-1111-1111-1111-ddddddddddd9",
        "CLAIMSRAWEXPLORER_DEV":      "11111111-1111-1111-1111-dddddddddda0",
        "EH_PAYER_RT_DEV":            "11111111-1111-1111-1111-eeeeeeeeeee1",
        "KQLDB_PAYER_RT_DEV":         "11111111-1111-1111-1111-fffffffffff1",
        "ES_CLAIMS_ARRIVALS_DEV":     "11111111-1111-1111-1111-eeeeeeee0008",
        "NB_RTI_01_INGEST_CLAIMS_STREAM_DEV": "11111111-1111-1111-1111-bbbbbbbbbbb5",
        "NB_RTI_02_PA_LATENCY_DEV":           "11111111-1111-1111-1111-bbbbbbbbbbb6",
        "NB_RTI_03_ADT_OUTREACH_DEV":         "11111111-1111-1111-1111-bbbbbbbbbbb7",
        "NB_RTI_04_SIU_INTAKE_SCORING_DEV":   "11111111-1111-1111-1111-bbbbbbbbbbb8",
        "PAYEROPS_ACTIVATOR_DEV":             "11111111-1111-1111-1111-aaaaaaaa1919",
        "FABRIC_WORKSPACE_ID_DEV":    "22222222-2222-2222-2222-222222222222",
    }
    res = _run(repo_root, "--env", "dev", "--explain", env_overrides=overrides)
    assert res.returncode == 0, (
        f"--explain with all vars set should exit 0; stdout={res.stdout!r}, "
        f"stderr={res.stderr!r}"
    )
    assert "[UNSET]" not in res.stdout
    assert "all 30 parameter.yml rules resolve" in res.stdout


# ---------- --only -----------------------------------------------------------


def test_only_filter_restricts_dry_run_to_one_type(repo_root: Path) -> None:
    res = _run(repo_root, "--env", "dev", "--dry-run", "--only", "DataAgent")
    assert res.returncode == 0, f"--only DataAgent dry-run failed: {res.stderr!r}"
    out = res.stdout
    # Only DataAgent section should appear, with all 8 agents listed.
    assert "[DataAgent]" in out
    assert "Order:    DataAgent" in out
    assert "8 item(s) would be published" in out
    for agent in ("CFOAgent", "StarsAgent", "RiskAdjustmentAgent", "SIUAgent",
                  "CareMgmtAgent", "NetworkAgent", "UMAgent", "ClaimsRawExplorer"):
        assert agent in out
    # Other item types must NOT appear
    for kind in ("[Lakehouse]", "[Notebook]", "[DataPipeline]", "[SemanticModel]"):
        assert kind not in out, f"--only DataAgent leaked {kind}"


def test_only_filter_rejects_unknown_type(repo_root: Path) -> None:
    res = _run(repo_root, "--env", "dev", "--dry-run", "--only", "Bogus")
    assert res.returncode != 0
    assert "Bogus" in (res.stdout + res.stderr)


def test_only_filter_rejects_type_with_no_folders(repo_root: Path) -> None:
    """Environment is in SUPPORTED_TYPES + itemOrder but has no folder on disk.

    (C.4 added a real Reflex folder, so it's no longer the no-folder canary.)
    """
    res = _run(repo_root, "--env", "dev", "--dry-run", "--only", "Environment")
    assert res.returncode != 0
    msg = (res.stdout + res.stderr)
    assert "Environment" in msg
    # Must distinguish "type unknown to fabric-cicd" from "no folders of that type".
    # The error should reference itemOrder or "no folders" so an operator knows
    # which fix to apply (deployment.yaml vs add a workspace folder).
    assert ("itemOrder" in msg) or ("no folders" in msg)

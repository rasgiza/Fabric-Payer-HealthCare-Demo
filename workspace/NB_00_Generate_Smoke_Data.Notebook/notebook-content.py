# Fabric notebook source

# METADATA **{"language":"markdown"}**

# MARKDOWN **{"language":"markdown"}**

# # NB_00 - Generate Smoke Data (Payer)
#
# Fetches `tools/gen_payer_overlay.py` + the 7 `data/reference/*.csv` lookup
# files from GitHub raw, runs the generator at the requested scale, and lands
# the 21 synthetic CSVs at `lh_bronze_raw/Files/synth/<run_id>/` where
# `NB_01_Bronze_Ingest` expects them.
#
# **Default lakehouse must be `lh_bronze_raw` when running manually.**
#
# **Parameters** (set by `Healthcare_Launcher` or via the medallion pipeline):
# - `run_id`        - synth batch folder under `Files/synth/` (default: `smoke`)
# - `scale`         - generator scale (default: `0.005`, ~500 members)
# - `seed`          - RNG seed for determinism (default: `42`)
# - `github_owner`  - source repo owner (default: `rasgiza`)
# - `github_repo`   - source repo name (default: `Fabric-Payer-HealthCare-Demo`)
# - `github_branch` - source repo branch (default: `main`)

# METADATA **{"language":"python"}**

# PARAMETERS CELL **{"language":"python"}**

run_id = "smoke"
scale = 0.005
seed = 42
github_owner = "rasgiza"
github_repo = "Fabric-Payer-HealthCare-Demo"
github_branch = "main"

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# 21-table inventory matches NB_01_Bronze_Ingest BRONZE_TABLES (kept in sync by
# tests/test_notebook_shape.py::test_bronze_inventory_matches_etl_module).
BRONZE_TABLES = [
    "members", "enrollment_spans", "providers", "payers", "conditions",
    "claims_header", "claims_line", "rx_claims", "auths", "appeals",
    "premiums", "raf_scores", "quality_events",
    "pharmacy_pa", "provider_sanctions", "provider_directory_attestation",
    "readmission", "sdoh_assessment", "cahps_response", "outreach",
    "vbc_attribution",
]
REFERENCE_CSVS = [
    "carc_codes.csv",
    "cms_stars_2026_cutpoints.csv",
    "conditions_prevalence.csv",
    "hcc_v28_sample.csv",
    "hedis_my2026_measures.csv",
    "payers.csv",
]

import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

RAW_BASE = f"https://raw.githubusercontent.com/{github_owner}/{github_repo}/{github_branch}"
STAGE = Path("/tmp/payer_synth")
STAGE_TOOLS = STAGE / "tools"
STAGE_REF = STAGE / "data" / "reference"
STAGE_OUT = STAGE / "data" / "synth" / run_id
DEST = Path(f"/lakehouse/default/Files/synth/{run_id}")

print(f"[gen] start={datetime.now().isoformat(timespec='seconds')} run_id={run_id} scale={scale} seed={seed}")
print(f"[gen] source={RAW_BASE}")
print(f"[gen] stage={STAGE}  dest={DEST}")

if STAGE.exists():
    shutil.rmtree(STAGE)
STAGE_TOOLS.mkdir(parents=True, exist_ok=True)
STAGE_REF.mkdir(parents=True, exist_ok=True)
STAGE_OUT.mkdir(parents=True, exist_ok=True)


def _fetch(rel_path: str, dest: Path) -> int:
    url = f"{RAW_BASE}/{rel_path}"
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    dest.write_bytes(data)
    return len(data)


bytes_total = 0
bytes_total += _fetch("tools/gen_payer_overlay.py", STAGE_TOOLS / "gen_payer_overlay.py")
for name in REFERENCE_CSVS:
    bytes_total += _fetch(f"data/reference/{name}", STAGE_REF / name)
print(f"[gen] fetched generator + {len(REFERENCE_CSVS)} reference csvs ({bytes_total:,} bytes)")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# Generator resolves reference + output paths relative to its own __file__:
#   ref = <script>/../data/reference
#   out = --out arg
# Staging tree mirrors the repo layout, so reference lookup just works.
proc = subprocess.run(
    [
        sys.executable,
        str(STAGE_TOOLS / "gen_payer_overlay.py"),
        "--scale", str(scale),
        "--seed", str(seed),
        "--out", str(STAGE_OUT),
    ],
    capture_output=True,
    text=True,
    check=False,
)
print(proc.stdout)
if proc.returncode != 0:
    print(proc.stderr, file=sys.stderr)
    raise RuntimeError(f"gen_payer_overlay.py failed with exit {proc.returncode}")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

DEST.mkdir(parents=True, exist_ok=True)
# Clear any prior contents under the same run_id so this notebook is idempotent.
for old in DEST.glob("*.csv"):
    old.unlink()

copied = 0
for t in BRONZE_TABLES:
    src = STAGE_OUT / f"{t}.csv"
    if not src.is_file():
        raise FileNotFoundError(f"generator did not produce {src.name}")
    shutil.copyfile(src, DEST / src.name)
    copied += 1
print(f"[gen] copied {copied} csvs -> {DEST}")

# Final smoke check: file count + non-empty.
found = sorted(p.name for p in DEST.glob("*.csv"))
missing = [f"{t}.csv" for t in BRONZE_TABLES if f"{t}.csv" not in found]
extra = [n for n in found if n not in {f"{t}.csv" for t in BRONZE_TABLES}]
assert not missing, f"missing csvs in {DEST}: {missing}"
assert not extra, f"unexpected csvs in {DEST}: {extra}"
for n in found:
    size = (DEST / n).stat().st_size
    assert size > 0, f"{n} is empty"
print(f"[gen] PASS - all {len(BRONZE_TABLES)} csvs present and non-empty in {DEST}")

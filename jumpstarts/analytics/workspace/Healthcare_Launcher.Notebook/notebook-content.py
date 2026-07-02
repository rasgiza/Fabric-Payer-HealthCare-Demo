# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "a2000002-0001-0001-0001-000000000004",
# META       "default_lakehouse_name": "lh_gold_curated",
# META       "default_lakehouse_workspace_id": "a0000000-0001-0001-0001-000000000000",
# META       "known_lakehouses": [
# META         {"id": "a2000002-0001-0001-0001-000000000001"},
# META         {"id": "a2000002-0001-0001-0001-000000000002"},
# META         {"id": "a2000002-0001-0001-0001-000000000003"},
# META         {"id": "a2000002-0001-0001-0001-000000000004"}
# META       ]
# META     }
# META   }
# META }

# MARKDOWN ********************

# METADATA ********************

# META {
# META   "language": "markdown"
# META }

# # Fabric Payer Healthcare Demo — Launcher
#
# **Single in-workspace entry point** for the Payer demo. Open this notebook
# in a Fabric workspace that has the `Fabric-Payer-HealthCare-Demo` items
# deployed (via `fabric-cicd` CI for platform teams or via the Fabric Jumpstart
# catalog installer for the analyst path) and **Run All** to:
#
# 1. Upload `payer_knowledge/*.md` from GitHub raw → `lh_gold_curated/Files/payer_knowledge/`
#    (Fabric Jumpstart deploys workspace items but does not extract loose
#    markdown — we pull them directly from the public repo at install time).
# 2. Invoke the medallion notebook chain (`NB_01` → `NB_02` → `NB_03`) with the
#    chosen `RUN_ID` and `MODE`.
# 3. Rebuild the `PayerAnalytics` Direct Lake semantic model: delete the
#    placeholder deployed by fabric-cicd, recreate it fresh from the repo TMDL
#    with the live OneLake URL patched in (a fresh create binds cleanly; an
#    in-place update keeps stale table bindings and breaks the refresh), and
#    rebind the `PayerAnalytics` report to the new model GUID.
# 4. Patch the 7 Foundry DataAgent definitions in place: replace the
#    zero-GUID placeholder `artifactId` / `workspaceId` (committed at
#    `workspace/<Name>.DataAgent/Files/Config/{draft,published}/<datasource>/datasource.json`)
#    with the **real** lakehouse + semantic-model item ids discovered at
#    runtime.
# 5. Print a one-line gold-tier sanity check (8 must-have tables) and
#    workspace publish-state summary.
# 6. Refresh the `PayerAnalytics` Direct Lake model (deferred to the last cell
#    with a long retry budget, because the lakehouse SQL endpoint exposes
#    newly-written gold tables asynchronously).
#
# > **Smoke data**: by default this launcher does NOT regenerate synthetic
# > data; it expects CSVs already present at `lh_bronze_raw/Files/synth/smoke/`
# > (shipped via the Jumpstart installer or `python tools/run_local_etl.py`).
# > Set `RUN_GENERATE_SMOKE = True` below to invoke `NB_00_Generate_Smoke_Data`
# > first, which fetches the generator + reference CSVs from GitHub raw and
# > lands a fresh 500-member smoke set into the bronze lakehouse (true
# > one-click path for fresh workspaces).
# >
# > **Out-of-scope here**: PAReviewCopilot hosted Foundry agent (deploys via
# > `tools/deploy_data_agents.py --live`, not this notebook). RTI Eventhouse
# > + Activator + KQL Dashboard (Stream C).

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

# ============================================================================
# CONFIGURATION — edit these values
# ============================================================================

# --- Source repo (used as a runtime fallback when fetching payer_knowledge/
#     markdown files; same pattern as the Fabric Jumpstart Provider launcher) ---
GITHUB_OWNER  = "rasgiza"
GITHUB_REPO   = "Fabric-Payer-HealthCare-Demo"
GITHUB_BRANCH = "main"
GITHUB_TOKEN  = ""   # optional PAT for private repos; leave empty for public

# --- Post-deploy toggles ---
UPLOAD_KNOWLEDGE_DOCS  = True   # Cell 1: fetch payer_knowledge/*.md → lh_gold_curated
RUN_ETL                = True   # Cell 2: medallion chain NB_01 → NB_02 → NB_03
BUILD_SEMANTIC_MODEL   = True   # Cell 3: recreate PayerAnalytics Direct Lake SM fresh + rebind report
PATCH_DATA_AGENTS      = True   # Cell 4: rebind 8 DataAgent placeholder GUIDs to real ids
RUN_SANITY_CHECK       = True   # Cell 5: gold-tier 8-table + publish-state summary
REFRESH_SEMANTIC_MODEL = True   # Cell 6: deferred Direct Lake refresh (long budget, endpoint nudge)

# --- ETL options (apply only when RUN_ETL=True) ---
RUN_ID             = "smoke"        # synth batch under Files/synth/<run_id>/
MODE               = "overwrite"    # 'overwrite' on first run, 'append' for daily increment
RUN_GENERATE_SMOKE = True           # set True to run NB_00 first (fetch+gen 500-member smoke set)
SMOKE_SCALE        = 0.005          # NB_00 generator scale (only used when RUN_GENERATE_SMOKE=True)
SMOKE_SEED         = 42             # NB_00 RNG seed (deterministic)
RUN_BRONZE         = True           # set False to skip NB_01 (silver+gold-only iteration)

workspace_id = spark.conf.get("trident.workspace.id")
print(f"Workspace:   {workspace_id}")
print(f"Source ref:  github.com/{GITHUB_OWNER}/{GITHUB_REPO}@{GITHUB_BRANCH}")
print(f"Toggles:     knowledge={UPLOAD_KNOWLEDGE_DOCS}  etl={RUN_ETL}  build_sm={BUILD_SEMANTIC_MODEL}  patch_agents={PATCH_DATA_AGENTS}  sanity={RUN_SANITY_CHECK}  refresh_sm={REFRESH_SEMANTIC_MODEL}")
print(f"ETL config:  run_id={RUN_ID}  mode={MODE}  gen_smoke={RUN_GENERATE_SMOKE}  run_bronze={RUN_BRONZE}")

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

# ============================================================================
# CELL 1 — Upload payer_knowledge/*.md → lh_gold_curated/Files/payer_knowledge/
# ============================================================================
# Mirrors the Provider Jumpstart launcher pattern. GitHub Contents API
# enumerates the folder, raw URLs stream each file. Falls back to a known
# inventory if the API rate-limits or 404s.

if UPLOAD_KNOWLEDGE_DOCS:
    import requests
    from notebookutils import mssparkutils

    raw_base = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/payer_knowledge"
    api_url  = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/payer_knowledge?ref={GITHUB_BRANCH}"
    api_hdrs = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}

    KNOWN_DOCS = [
        "ama_prior_auth_survey.md",
        "carc_reference.md",
        "cms_0057_f_pa_rule.md",
        "cms_network_adequacy.md",
        "hcc_v28_weights.md",
        "hcp_lan_apm_framework.md",
        "hedis_my2026_measures.md",
        "hfma_glossary.md",
        "kff_high_cost_methodology.md",
        "nhcaa_fraud_schemes.md",
        "oig_radv_audit_guidance.md",
        "onelake_security_model.md",
        "policy_citation_pattern.md",
        "README.md",
        "rti_ops_runbook.md",
        "sdoh_hcp_lan_framework.md",
        "stars_2026_cutpoints.md",
    ]

    try:
        resp = requests.get(api_url, headers=api_hdrs, timeout=30)
        if resp.status_code == 200:
            entries = [e["name"] for e in resp.json() if e.get("name", "").endswith(".md")]
        else:
            print(f"  GitHub Contents API returned {resp.status_code}; falling back to known inventory")
            entries = KNOWN_DOCS
    except Exception as e:
        print(f"  GitHub Contents API failed ({e}); falling back to known inventory")
        entries = KNOWN_DOCS

    target_dir = "/lakehouse/default/Files/payer_knowledge"
    mssparkutils.fs.mkdirs(f"file:{target_dir}")

    uploaded = 0
    for name in entries:
        try:
            r = requests.get(f"{raw_base}/{name}", timeout=30)
            r.raise_for_status()
            with open(f"{target_dir}/{name}", "wb") as fh:
                fh.write(r.content)
            uploaded += 1
        except Exception as e:
            print(f"  [WARN] failed to upload {name}: {e}")
    print(f"Uploaded {uploaded}/{len(entries)} payer-knowledge documents to lh_gold_curated/Files/payer_knowledge/")
else:
    print("Skipping payer-knowledge upload (UPLOAD_KNOWLEDGE_DOCS=False)")

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

# ============================================================================
# CELL 2 — Run the medallion notebook chain
# ============================================================================
# Each step times out after 60 minutes (3600 sec). PL_Payer_Master is the
# schedulable production path; this launcher is the interactive equivalent
# so we don't need pipeline RBAC to drive a fresh workspace.

if RUN_ETL:
    from notebookutils import mssparkutils

    results: dict[str, str] = {}

    if RUN_GENERATE_SMOKE:
        results["NB_00_Generate_Smoke_Data"] = mssparkutils.notebook.run(
            "NB_00_Generate_Smoke_Data",
            3600,
            {
                "run_id": RUN_ID,
                "scale": SMOKE_SCALE,
                "seed": SMOKE_SEED,
                "github_owner": GITHUB_OWNER,
                "github_repo": GITHUB_REPO,
                "github_branch": GITHUB_BRANCH,
                "useRootDefaultLakehouse": True,
            },
        )

    if RUN_BRONZE:
        results["NB_01_Bronze_Ingest"] = mssparkutils.notebook.run(
            "NB_01_Bronze_Ingest",
            3600,
            {"run_id": RUN_ID, "mode": MODE, "useRootDefaultLakehouse": True},
        )

    results["NB_02_Silver_Transform"] = mssparkutils.notebook.run(
        "NB_02_Silver_Transform", 3600, {"useRootDefaultLakehouse": True}
    )

    results["NB_03_Gold_Build"] = mssparkutils.notebook.run(
        "NB_03_Gold_Build", 3600, {"useRootDefaultLakehouse": True}
    )

    for k, v in results.items():
        print(f"[{k}] exit={v}")
else:
    print("Skipping ETL chain (RUN_ETL=False)")

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

# ============================================================================
# CELL 3 — Build PayerAnalytics Semantic Model (Direct Lake) — refresh deferred
# ============================================================================
# fabric-cicd / the Jumpstart installer deploys PayerAnalytics.SemanticModel as
# a git item with a PLACEHOLDER Direct Lake binding (expressions.tmdl points at
# zero-GUID workspace/lakehouse ids). Updating that placeholder in place keeps
# its stale internal table bindings, so a Direct Lake refresh reframes against
# the old table identity and fails with "source tables do not exist".
#
# So — exactly like the Provider Jumpstart launcher (verified pattern) — we
# DELETE the placeholder model and CREATE it fresh here, AFTER the medallion
# chain has written the gold tables, with the live OneLake URL patched into
# expressions.tmdl. We then rebind the PayerAnalytics report to the new model
# GUID and carry the id forward in PAYER_SM_ID. This cell runs BEFORE the
# DataAgent patch cell so those agents bind to the freshly-created SM id.
#
# The Direct Lake REFRESH is DEFERRED to the LAST cell of this notebook,
# because the lakehouse SQL analytics endpoint exposes newly-written Delta
# tables asynchronously and needs a few minutes to catch up.
# ============================================================================

if BUILD_SEMANTIC_MODEL:
    import base64
    import os
    import re
    import time
    import requests

    SM_NAME = "PayerAnalytics"
    SM_REPO_DIR = "workspace/PayerAnalytics.SemanticModel"
    REPORT_NAME = "PayerAnalytics"
    URL_PATTERN = re.compile(
        r"https://onelake\.dfs\.fabric\.microsoft\.com/"
        r"[0-9a-fA-F-]{36}/[0-9a-fA-F-]{36}"
    )

    token = notebookutils.credentials.getToken("pbi")  # noqa: F821
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    FABRIC_API = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
    PBI_API = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}"

    def _sm_wait_lro(resp, hdr, timeout=180):
        loc = resp.headers.get("Location", "")
        retry = int(resp.headers.get("Retry-After", 5) or 5)
        elapsed = 0
        while loc and elapsed < timeout:
            time.sleep(retry)
            elapsed += retry
            rr = requests.get(loc, headers=hdr, timeout=30)
            if rr.status_code != 200:
                continue
            st = rr.json().get("status", "")
            if st == "Succeeded":
                return "Succeeded"
            if st in ("Failed", "Cancelled"):
                return st
        return "Timeout"

    print("=" * 60)
    print("  SEMANTIC MODEL — Rebuild PayerAnalytics from repo definition")
    print("=" * 60)

    # -- Step 1: Discover lh_gold_curated id -------------------------------
    resp = requests.get(f"{FABRIC_API}/lakehouses", headers=headers, timeout=60)
    resp.raise_for_status()
    lh_gold_id = next((lh["id"] for lh in resp.json().get("value", [])
                       if lh["displayName"] == "lh_gold_curated"), None)

    PAYER_SM_ID = None
    if not lh_gold_id:
        print("  [WARN] lh_gold_curated not found — run the ETL cell first. Skipping.")
    else:
        new_url = f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/{lh_gold_id}"
        print(f"  Lakehouse: lh_gold_curated ({lh_gold_id})")

        # -- Step 2: Find existing SM (will be deleted + recreated fresh) ---
        existing_sm_id = None
        r = requests.get(f"{FABRIC_API}/items?type=SemanticModel", headers=headers, timeout=60)
        r.raise_for_status()
        for sm in r.json().get("value", []):
            if sm["displayName"] == SM_NAME:
                existing_sm_id = sm["id"]
                break

        # -- Step 3: Load TMDL — lakehouse extract first, else GitHub raw ---
        sm_base = None
        for base_prefix in [".lakehouse/default/Files/src", "/lakehouse/default/Files/src"]:
            cand = os.path.join(base_prefix, SM_REPO_DIR)
            if os.path.isdir(cand):
                sm_base = cand
                break

        if not sm_base:
            print("  Downloading SM definition from GitHub...")
            import tempfile
            _tmp = tempfile.mkdtemp()
            _local = os.path.join(_tmp, SM_REPO_DIR)
            gh_hdrs = {"Accept": "application/vnd.github.v3+json"}
            if GITHUB_TOKEN:
                gh_hdrs["Authorization"] = f"token {GITHUB_TOKEN}"
            tree_url = (f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
                        f"/git/trees/{GITHUB_BRANCH}?recursive=1")
            tr = requests.get(tree_url, headers=gh_hdrs, timeout=60)
            tr.raise_for_status()
            prefix = SM_REPO_DIR + "/"
            blobs = [e for e in tr.json()["tree"]
                     if e["path"].startswith(prefix) and e["type"] == "blob"]
            for entry in blobs:
                rel = entry["path"][len(prefix):]
                if rel == ".platform":
                    continue
                raw_url = (f"https://raw.githubusercontent.com/{GITHUB_OWNER}/"
                           f"{GITHUB_REPO}/{GITHUB_BRANCH}/{entry['path']}")
                dr = requests.get(raw_url, timeout=60)
                dr.raise_for_status()
                lp = os.path.join(_local, rel)
                os.makedirs(os.path.dirname(lp), exist_ok=True)
                with open(lp, "wb") as f:
                    f.write(dr.content)
            if os.path.isdir(_local):
                sm_base = _local
                print(f"  Downloaded {len(blobs)} SM definition files from GitHub")

        if not sm_base:
            print("  [FAIL] SM definition not found on lakehouse or GitHub — skipping.")
        else:
            def_dir = os.path.join(sm_base, "definition")
            parts = []

            pbism_path = os.path.join(sm_base, "definition.pbism")
            if os.path.exists(pbism_path):
                with open(pbism_path, "rb") as f:
                    raw = f.read()
                if raw.startswith(b"\xef\xbb\xbf"):
                    raw = raw[3:]
                parts.append({"path": "definition.pbism",
                              "payload": base64.b64encode(raw).decode(),
                              "payloadType": "InlineBase64"})

            for root, _dirs, files in os.walk(def_dir):
                for fname in sorted(files):
                    fpath = os.path.join(root, fname)
                    rel = "definition/" + os.path.relpath(fpath, def_dir).replace("\\", "/")
                    with open(fpath, "rb") as f:
                        raw = f.read()
                    if raw.startswith(b"\xef\xbb\xbf"):
                        raw = raw[3:]
                    if "expressions.tmdl" in rel:
                        content = raw.decode("utf-8")
                        found = URL_PATTERN.findall(content)
                        if found and found[0] != new_url:
                            print(f"  Patching Direct Lake URL -> {new_url}")
                            content = URL_PATTERN.sub(new_url, content)
                            raw = content.encode("utf-8")
                    parts.append({"path": rel,
                                  "payload": base64.b64encode(raw).decode(),
                                  "payloadType": "InlineBase64"})

            print(f"  Loaded {len(parts)} definition parts")

            if not parts:
                print("  [FAIL] No definition parts loaded — cannot create SM.")
            else:
                # -- Step 4: Delete placeholder, then CREATE fresh ---------
                if existing_sm_id:
                    print(f"  Deleting placeholder SM ({existing_sm_id}) to recreate fresh...")
                    dr = requests.delete(f"{FABRIC_API}/semanticModels/{existing_sm_id}",
                                         headers=headers, timeout=60)
                    if dr.status_code == 202:
                        _sm_wait_lro(dr, headers, timeout=120)
                    time.sleep(5)
                    token = notebookutils.credentials.getToken("pbi")  # noqa: F821
                    headers["Authorization"] = f"Bearer {token}"

                create_body = {"displayName": SM_NAME,
                               "description": "Payer Analytics Direct Lake semantic model",
                               "definition": {"parts": parts}}
                print(f"  Creating SM {SM_NAME} with {len(parts)} parts...")
                cr = requests.post(f"{FABRIC_API}/semanticModels",
                                   headers=headers, json=create_body, timeout=120)
                if cr.status_code in (200, 201):
                    PAYER_SM_ID = cr.json().get("id")
                elif cr.status_code == 202:
                    if _sm_wait_lro(cr, headers, timeout=180) == "Succeeded":
                        time.sleep(3)
                        rr = requests.get(f"{FABRIC_API}/items?type=SemanticModel",
                                          headers=headers, timeout=60)
                        for sm in rr.json().get("value", []):
                            if sm["displayName"] == SM_NAME:
                                PAYER_SM_ID = sm["id"]
                                break
                else:
                    print(f"  [FAIL] Create SM HTTP {cr.status_code}: {cr.text[:300]}")

                if PAYER_SM_ID:
                    print(f"  Created PayerAnalytics ({PAYER_SM_ID})")

                    # -- Step 4b: Rebind the PayerAnalytics report ---------
                    try:
                        rep = requests.get(f"{FABRIC_API}/items?type=Report",
                                           headers=headers, timeout=60)
                        report_id = next((it["id"] for it in rep.json().get("value", [])
                                          if it["displayName"] == REPORT_NAME), None)
                        if report_id:
                            rb = requests.post(f"{PBI_API}/reports/{report_id}/Rebind",
                                               headers=headers,
                                               json={"datasetId": PAYER_SM_ID}, timeout=60)
                            if rb.status_code in (200, 202):
                                print(f"  Rebound report {REPORT_NAME} -> {PAYER_SM_ID}")
                            else:
                                print(f"  [WARN] Rebind HTTP {rb.status_code}: {rb.text[:200]}")
                        else:
                            print(f"  [WARN] Report {REPORT_NAME} not found — will bind on next deploy")
                    except Exception as _e:
                        print(f"  [WARN] Report rebind skipped: {_e}")

                    print("  Refresh DEFERRED to the final cell.")
                else:
                    print("  [WARN] SM not created — final refresh cell will look it up by name.")
else:
    PAYER_SM_ID = None
    print("Skipping semantic model rebuild (BUILD_SEMANTIC_MODEL=False)")

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

# ============================================================================
# CELL 4 — Patch 7 Foundry DataAgents with real workspace artifact ids
# ============================================================================
# The 7 DataAgent items deploy via fabric-cicd or Jumpstart with placeholder
# GUIDs at `Files/Config/{draft,published}/<datasource>/datasource.json`:
#   artifactId  = 00000000-0000-0000-0000-000000000000
#   workspaceId = 00000000-0000-0000-0000-000000000000
#
# This cell discovers the REAL ids for lh_gold_curated and PayerAnalytics in
# the live workspace, fetches each agent's definition via the Fabric REST API,
# rewrites the placeholders in both draft + published copies, and pushes the
# updated definition back (handling 202 LRO polling per Fabric API contract).
#
# Source pattern: Provider Jumpstart launcher Cell 6 (verified 2026-06-19).
# ============================================================================

if PATCH_DATA_AGENTS:
    import base64
    import json as _json
    import time
    import requests

    AGENT_NAMES = (
        "CFOAgent", "StarsAgent", "RiskAdjustmentAgent", "SIUAgent",
        "CareMgmtAgent", "NetworkAgent", "UMAgent", "ClaimsRawExplorer",
    )
    ZERO_GUID = "00000000-0000-0000-0000-000000000000"

    token = notebookutils.credentials.getToken("pbi")  # noqa: F821 — provided by Fabric runtime
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    api_base = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"

    resp = requests.get(f"{api_base}/items", headers=headers, timeout=60)
    items = resp.json().get("value", []) if resp.status_code == 200 else []

    lh_gold_id = next((it["id"] for it in items
                       if it["type"] == "Lakehouse" and it["displayName"] == "lh_gold_curated"), None)
    sm_id = next((it["id"] for it in items
                  if it["type"] == "SemanticModel" and it["displayName"] == "PayerAnalytics"), None)
    ontology_id = next((it["id"] for it in items
                        if it["type"] == "Ontology" and it["displayName"] == "Payer_Ontology"), None)

    print(f"  Discovered: lakehouse={lh_gold_id}  semantic_model={sm_id}  ontology={ontology_id}")

    ds_type_map: dict[str, dict[str, str]] = {}
    if lh_gold_id:
        ds_type_map["lakehouse_tables"] = {"artifactId": lh_gold_id, "workspaceId": workspace_id}
    if sm_id:
        ds_type_map["semantic_model"]   = {"artifactId": sm_id, "workspaceId": workspace_id}
    if ontology_id:
        ds_type_map["graph"]            = {"artifactId": ontology_id, "workspaceId": workspace_id}

    def _poll_lro(loc: str, retry_after: int) -> dict | None:
        for _ in range(60):
            time.sleep(retry_after)
            op = requests.get(loc, headers=headers, timeout=30)
            if op.status_code != 200:
                continue
            body = op.json()
            st = body.get("status")
            if st == "Succeeded":
                res_loc = body.get("resourceLocation", "")
                for url in (f"{loc}/result", res_loc):
                    if not url:
                        continue
                    rr = requests.get(url, headers=headers, timeout=30)
                    if rr.status_code == 200:
                        return rr.json()
                return body
            if st in ("Failed", "Cancelled"):
                return None
        return None

    patched_agents = 0
    for agent_name in AGENT_NAMES:
        agent_id = next((it["id"] for it in items
                         if it["type"] == "DataAgent" and it["displayName"] == agent_name), None)
        if not agent_id:
            print(f"  [SKIP] {agent_name}: not present in workspace")
            continue

        get_def_url = f"{api_base}/DataAgents/{agent_id}/getDefinition"
        r = requests.post(get_def_url, headers=headers, timeout=30)
        if r.status_code == 200:
            parts = r.json().get("definition", {}).get("parts", [])
        elif r.status_code == 202:
            result = _poll_lro(r.headers.get("Location", ""),
                               int(r.headers.get("Retry-After", 5)))
            parts = (result or {}).get("definition", {}).get("parts", [])
        else:
            print(f"  [FAIL] {agent_name} getDefinition HTTP {r.status_code}")
            continue

        if not parts:
            print(f"  [FAIL] {agent_name}: no definition parts returned")
            continue

        patched_parts: list[dict] = []
        agent_patches = 0
        for part in parts:
            path = part.get("path", "")
            payload = part.get("payload", "")
            ptype = part.get("payloadType", "InlineBase64")

            if "datasource.json" in path and ptype == "InlineBase64" and payload:
                try:
                    content = base64.b64decode(payload).decode("utf-8")
                    ds = _json.loads(content)
                    dtype = ds.get("type", "")
                    if dtype in ds_type_map:
                        new = ds_type_map[dtype]
                        if ds.get("artifactId") != new["artifactId"]:
                            ds["artifactId"] = new["artifactId"]
                            agent_patches += 1
                        if ds.get("workspaceId") != new["workspaceId"]:
                            ds["workspaceId"] = new["workspaceId"]
                            agent_patches += 1
                        content = _json.dumps(ds, indent=2, ensure_ascii=False)
                        payload = base64.b64encode(content.encode("utf-8")).decode("utf-8")
                    elif ZERO_GUID in (ds.get("artifactId", ""), ds.get("workspaceId", "")):
                        print(f"    [DROP] {agent_name}/{ds.get('displayName', dtype)}: unpatched placeholder")
                        continue
                except Exception as e:
                    print(f"    [WARN] {agent_name} {path}: {e}")

            patched_parts.append({"path": path, "payload": payload, "payloadType": ptype})

        if agent_patches == 0:
            print(f"  [OK]   {agent_name}: no placeholders to rewrite")
            continue

        upd_url = f"{api_base}/DataAgents/{agent_id}/updateDefinition"
        upd = requests.post(upd_url, headers=headers,
                            json={"definition": {"parts": patched_parts}}, timeout=60)
        if upd.status_code == 200:
            patched_agents += 1
            print(f"  [OK]   {agent_name}: rewrote {agent_patches} placeholder field(s)")
        elif upd.status_code == 202:
            _ = _poll_lro(upd.headers.get("Location", ""),
                          int(upd.headers.get("Retry-After", 5)))
            patched_agents += 1
            print(f"  [OK]   {agent_name}: rewrote {agent_patches} field(s) (LRO)")
        else:
            print(f"  [FAIL] {agent_name} updateDefinition HTTP {upd.status_code}: {upd.text[:200]}")

    print(f"\n  Patched {patched_agents}/{len(AGENT_NAMES)} agents")
else:
    print("Skipping DataAgent ID patching (PATCH_DATA_AGENTS=False)")

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

# ============================================================================
# CELL 5 — Sanity check: gold tables + publish-state summary
# ============================================================================
# Same 8-table gold check as before (locked by tests/test_launcher_and_deploy.py)
# plus a workspace-publish summary so the analyst sees what landed.

if RUN_SANITY_CHECK:
    REQUIRED_GOLD = [
        "dim_member",
        "dim_date",
        "fact_claim",
        "fact_pharmacy_pa",
        "agg_denial_by_payer",
        "agg_pa_tat",
        "agg_stars_compliance",
        "agg_health_equity_index_proxy",
    ]

    missing = []
    for t in REQUIRED_GOLD:
        n = spark.sql(f"SELECT COUNT(*) AS n FROM lh_gold_curated.{t}").collect()[0]["n"]
        if n == 0:
            missing.append(f"{t} (empty)")
        print(f"  {t:40s} rows={n}")

    if missing:
        raise RuntimeError(f"[launcher] FAIL — empty gold tables: {missing}")

    # Publish-state summary (best-effort; no failure if items missing)
    try:
        import requests
        token = notebookutils.credentials.getToken("pbi")  # noqa: F821
        headers = {"Authorization": f"Bearer {token}"}
        api_base = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
        r = requests.get(f"{api_base}/items", headers=headers, timeout=60)
        if r.status_code == 200:
            by_type: dict[str, int] = {}
            for it in r.json().get("value", []):
                by_type[it["type"]] = by_type.get(it["type"], 0) + 1
            print("\n  Workspace publish state:")
            for k in sorted(by_type):
                print(f"    {k:20s} {by_type[k]}")
    except Exception as e:
        print(f"  [WARN] publish-state summary failed: {e}")

    print("\n[launcher] PASS — gold tier ready for PayerAnalytics + Payer_Ontology + 7 Foundry data agents")
else:
    print("Skipping sanity check (RUN_SANITY_CHECK=False)")

# CELL ********************

# METADATA ********************

# META {
# META   "language": "python"
# META }

# ============================================================================
# CELL 6 — Refresh PayerAnalytics Semantic Model (Direct Lake) — deferred
# ============================================================================
# This is the LAST cell on purpose. Cell 3 only CREATES the model; the Direct
# Lake REFRESH happens here.
#
# WHY DEFERRED: Direct Lake reads the gold tables through the lakehouse SQL
# analytics endpoint, which exposes newly-written Delta tables ASYNCHRONOUSLY.
# The largest gold aggregates can lag a few minutes behind the notebook write.
# Refreshing immediately fails the reframe with "source tables do not exist",
# while a refresh a few minutes later always succeeds. Running it at the very
# end (after the DataAgent patch + sanity steps) gives the endpoint settle
# time; we also retry on a ~12-minute budget and nudge the SQL endpoint before
# each attempt, so a slow tenant still lands cleanly.
# ============================================================================

if REFRESH_SEMANTIC_MODEL:
    import json as _json
    import time
    import requests

    SM_NAME = "PayerAnalytics"
    _token = notebookutils.credentials.getToken("pbi")  # noqa: F821
    _hdrs = {"Authorization": f"Bearer {_token}", "Content-Type": "application/json"}
    _FABRIC = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
    _PBI = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}"

    def _ref_wait_lro(resp, hdr, timeout=180):
        loc = resp.headers.get("Location", "")
        retry = int(resp.headers.get("Retry-After", 5) or 5)
        elapsed = 0
        while loc and elapsed < timeout:
            time.sleep(retry)
            elapsed += retry
            rr = requests.get(loc, headers=hdr, timeout=30)
            if rr.status_code != 200:
                continue
            st = rr.json().get("status", "")
            if st == "Succeeded":
                return "Succeeded"
            if st in ("Failed", "Cancelled"):
                return st
        return "Timeout"

    print("=" * 60)
    print("  SEMANTIC MODEL — Direct Lake Refresh (deferred to final cell)")
    print("=" * 60)

    sm_id = globals().get("PAYER_SM_ID")
    if not sm_id:
        r = requests.get(f"{_FABRIC}/items?type=SemanticModel", headers=_hdrs, timeout=60)
        sm_id = next((it["id"] for it in r.json().get("value", [])
                      if it["displayName"] == SM_NAME), None)

    if not sm_id:
        print(f"  [SKIP] {SM_NAME} not found — run the build cell first.")
    else:
        print(f"  Semantic model: {SM_NAME} ({sm_id})")

        # Resolve the lakehouse SQL endpoint (to nudge metadata sync).
        sql_ep_id = None
        try:
            lr = requests.get(f"{_FABRIC}/lakehouses", headers=_hdrs, timeout=60)
            lh_id = next((lh["id"] for lh in lr.json().get("value", [])
                          if lh["displayName"] == "lh_gold_curated"), None)
            if lh_id:
                ld = requests.get(f"{_FABRIC}/lakehouses/{lh_id}", headers=_hdrs, timeout=60)
                if ld.status_code == 200:
                    sql_ep_id = (ld.json().get("properties", {})
                                 .get("sqlEndpointProperties", {}).get("id"))
        except Exception as _e:
            print(f"  [WARN] Could not resolve SQL endpoint: {_e}")

        refresh_url = f"{_PBI}/datasets/{sm_id}/refreshes"
        MAX_MINUTES = 12
        deadline = time.time() + MAX_MINUTES * 60
        attempt = 0
        done = False
        while time.time() < deadline and not done:
            attempt += 1

            # Best-effort endpoint metadata nudge before each attempt.
            if sql_ep_id:
                try:
                    sr = requests.post(f"{_FABRIC}/sqlEndpoints/{sql_ep_id}/refreshMetadata",
                                       headers=_hdrs, json={}, timeout=60)
                    if sr.status_code == 202:
                        _ref_wait_lro(sr, _hdrs, timeout=180)
                except Exception:
                    pass

            _token = notebookutils.credentials.getToken("pbi")  # noqa: F821
            _hdrs["Authorization"] = f"Bearer {_token}"

            print(f"  Triggering refresh (attempt {attempt})...")
            r = requests.post(refresh_url, headers=_hdrs, json={"type": "Full"}, timeout=60)
            if r.status_code not in (200, 202):
                print(f"  Refresh trigger HTTP {r.status_code}: {r.text[:200]}")
                time.sleep(30)
                continue

            # Poll this refresh to a terminal state.
            for _ in range(60):
                time.sleep(10)
                pr = requests.get(refresh_url, headers=_hdrs, timeout=60)
                if pr.status_code != 200:
                    continue
                vals = pr.json().get("value", [])
                if not vals:
                    continue
                status = vals[0].get("status", "Unknown")
                if status in ("Completed", "Succeeded"):
                    print(f"  Refresh COMPLETED (attempt {attempt}).")
                    done = True
                    break
                if status == "Failed":
                    emsg = vals[0].get("serviceExceptionJson", "")
                    try:
                        detail = _json.loads(emsg).get("errorDescription", "") or emsg
                    except Exception:
                        detail = emsg
                    if "do not exist" in detail or "does not exist" in detail:
                        print(f"  Attempt {attempt}: tables not exposed yet — endpoint still syncing.")
                    else:
                        print(f"  Refresh FAILED (attempt {attempt}): {detail[:250]}")
                        done = True  # non-timing failure won't self-heal
                    break

            if done:
                break
            remaining = int(deadline - time.time())
            if remaining <= 0:
                break
            print(f"  Waiting 45s for endpoint to catch up (~{remaining // 60}m budget left)...")
            time.sleep(45)

        if not done:
            print("  [WARN] Refresh not confirmed within budget.")
            print(f"         Click Refresh on {SM_NAME} in the workspace in a few")
            print("         minutes — the endpoint is still syncing the gold tables.")
else:
    print("Skipping semantic model refresh (REFRESH_SEMANTIC_MODEL=False)")

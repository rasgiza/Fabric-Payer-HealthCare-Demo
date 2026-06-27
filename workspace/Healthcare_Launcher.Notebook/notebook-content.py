# Fabric notebook source

# METADATA **{"language":"markdown"}**

# MARKDOWN **{"language":"markdown"}**

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
# 3. Patch the 7 Foundry DataAgent definitions in place: replace the
#    zero-GUID placeholder `artifactId` / `workspaceId` (committed at
#    `workspace/<Name>.DataAgent/Files/Config/{draft,published}/<datasource>/datasource.json`)
#    with the **real** lakehouse + semantic-model item ids discovered at
#    runtime.
# 4. Print a one-line gold-tier sanity check (8 must-have tables) and
#    workspace publish-state summary.
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

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

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
UPLOAD_KNOWLEDGE_DOCS = True   # Cell 1: fetch payer_knowledge/*.md → lh_gold_curated
RUN_ETL               = True   # Cell 2: medallion chain NB_01 → NB_02 → NB_03
PATCH_DATA_AGENTS     = True   # Cell 3: rebind 8 DataAgent placeholder GUIDs to real ids
RUN_SANITY_CHECK      = True   # Cell 4: gold-tier 8-table + publish-state summary

# --- ETL options (apply only when RUN_ETL=True) ---
RUN_ID             = "smoke"        # synth batch under Files/synth/<run_id>/
MODE               = "overwrite"    # 'overwrite' on first run, 'append' for daily increment
RUN_GENERATE_SMOKE = False          # set True to run NB_00 first (fetch+gen 500-member smoke set)
SMOKE_SCALE        = 0.005          # NB_00 generator scale (only used when RUN_GENERATE_SMOKE=True)
SMOKE_SEED         = 42             # NB_00 RNG seed (deterministic)
RUN_BRONZE         = True           # set False to skip NB_01 (silver+gold-only iteration)

workspace_id = spark.conf.get("trident.workspace.id")
print(f"Workspace:   {workspace_id}")
print(f"Source ref:  github.com/{GITHUB_OWNER}/{GITHUB_REPO}@{GITHUB_BRANCH}")
print(f"Toggles:     knowledge={UPLOAD_KNOWLEDGE_DOCS}  etl={RUN_ETL}  patch_agents={PATCH_DATA_AGENTS}  sanity={RUN_SANITY_CHECK}")
print(f"ETL config:  run_id={RUN_ID}  mode={MODE}  gen_smoke={RUN_GENERATE_SMOKE}  run_bronze={RUN_BRONZE}")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

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

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

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
            },
        )

    if RUN_BRONZE:
        results["NB_01_Bronze_Ingest"] = mssparkutils.notebook.run(
            "NB_01_Bronze_Ingest",
            3600,
            {"run_id": RUN_ID, "mode": MODE},
        )

    results["NB_02_Silver_Transform"] = mssparkutils.notebook.run(
        "NB_02_Silver_Transform", 3600, {}
    )

    results["NB_03_Gold_Build"] = mssparkutils.notebook.run(
        "NB_03_Gold_Build", 3600, {}
    )

    for k, v in results.items():
        print(f"[{k}] exit={v}")
else:
    print("Skipping ETL chain (RUN_ETL=False)")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ============================================================================
# CELL 3 — Patch 7 Foundry DataAgents with real workspace artifact ids
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

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ============================================================================
# CELL 4 — Sanity check: gold tables + publish-state summary
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

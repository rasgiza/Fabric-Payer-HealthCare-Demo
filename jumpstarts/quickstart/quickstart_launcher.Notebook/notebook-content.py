# Fabric notebook source

# METADATA **{"language":"markdown"}**

# MARKDOWN **{"language":"markdown"}**

# # Payer Quickstart — Launcher (Tier 1)
#
# **One-click entry point for the Tier 1 Quickstart jumpstart.** Open this
# notebook in a Fabric workspace that has the quickstart items deployed
# (`lh_gold_curated`, `PayerAnalytics` semantic model, `CFOAgent`, `StarsAgent`,
# and the 2-page `PayerAnalytics` report) and **Run All** to:
#
# 1. Load the **pre-baked gold tables** shipped in
#    `jumpstarts/quickstart/data/gold/*.parquet` (fetched from GitHub raw) into
#    `lh_gold_curated` as managed Delta tables — **no ETL run required**.
# 2. Upload the four payer-knowledge documents the two quickstart agents cite
#    (`carc_reference`, `hfma_glossary`, `hedis_my2026_measures`,
#    `stars_2026_cutpoints`) → `lh_gold_curated/Files/payer_knowledge/`.
# 3. Patch the **two** Foundry DataAgents (`CFOAgent`, `StarsAgent`): replace
#    the zero-GUID placeholder `artifactId` / `workspaceId` with the real
#    lakehouse + semantic-model item ids discovered at runtime.
# 4. Print a gold-tier sanity check over the 14 quickstart tables plus a
#    workspace publish-state summary.
#
# > **Pre-baked data**: unlike the full `Healthcare_Launcher`, this launcher
# > does NOT invoke the medallion chain — the curated gold slice is committed
# > to the repo so the analyst path lands in minutes. To regenerate from raw,
# > use the full demo's `Healthcare_Launcher` instead.
# >
# > **Promotion**: a Tier 1 install is a strict subset of the full workspace,
# > so upgrading to Tier 2 / Tier 3 never re-lands this data.

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ============================================================================
# CONFIGURATION — edit these values
# ============================================================================

# --- Source repo (used to fetch pre-baked gold parquet + payer_knowledge
#     markdown at install time; same pattern as the full launcher) ---
GITHUB_OWNER  = "rasgiza"
GITHUB_REPO   = "Fabric-Payer-HealthCare-Demo"
GITHUB_BRANCH = "main"
GITHUB_TOKEN  = ""   # optional PAT for private repos; leave empty for public

# --- Post-deploy toggles ---
LOAD_GOLD_DATA        = True   # Cell 1: pre-baked gold parquet -> lh_gold_curated Delta tables
UPLOAD_KNOWLEDGE_DOCS = True   # Cell 2: fetch the 4 cited payer_knowledge docs
PATCH_DATA_AGENTS     = True   # Cell 3: rebind CFOAgent + StarsAgent placeholder GUIDs
RUN_SANITY_CHECK      = True   # Cell 4: gold-tier + publish-state summary

# --- Quickstart manifest (kept in sync with jumpstarts/quickstart/manifest.yaml) ---
GOLD_TABLES = [
    "fact_claim", "fact_appeal", "fact_premium", "fact_member_month",
    "fact_quality_event", "agg_mlr_monthly", "agg_denial_by_payer",
    "agg_stars_compliance", "dim_member", "dim_payer", "dim_product",
    "dim_lob", "dim_provider", "dim_date",
]
KNOWLEDGE_DOCS = [
    "carc_reference.md", "hfma_glossary.md",
    "hedis_my2026_measures.md", "stars_2026_cutpoints.md",
]
AGENT_NAMES = ("CFOAgent", "StarsAgent")
GOLD_RAW_PREFIX = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/jumpstarts/quickstart/data/gold"

workspace_id = spark.conf.get("trident.workspace.id")
print(f"Workspace:   {workspace_id}")
print(f"Source ref:  github.com/{GITHUB_OWNER}/{GITHUB_REPO}@{GITHUB_BRANCH}")
print(f"Toggles:     load_gold={LOAD_GOLD_DATA}  knowledge={UPLOAD_KNOWLEDGE_DOCS}  patch_agents={PATCH_DATA_AGENTS}  sanity={RUN_SANITY_CHECK}")
print(f"Tier 1 scope: {len(GOLD_TABLES)} gold tables, {len(AGENT_NAMES)} agents, {len(KNOWLEDGE_DOCS)} knowledge docs")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ============================================================================
# CELL 1 — Load pre-baked gold parquet -> lh_gold_curated managed Delta tables
# ============================================================================
# Streams each parquet from GitHub raw to a local temp path, reads it with
# Spark, and writes a managed Delta table into lh_gold_curated. Idempotent:
# overwrite mode means a re-run simply refreshes the slice.

if LOAD_GOLD_DATA:
    import requests
    from notebookutils import mssparkutils

    tmp_dir = "/tmp/quickstart_gold"
    mssparkutils.fs.mkdirs(f"file:{tmp_dir}")

    loaded = 0
    for table in GOLD_TABLES:
        url = f"{GOLD_RAW_PREFIX}/{table}.parquet"
        local = f"{tmp_dir}/{table}.parquet"
        try:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            with open(local, "wb") as fh:
                fh.write(r.content)
            df = spark.read.parquet(f"file:{local}")
            (df.write.mode("overwrite").format("delta")
               .saveAsTable(f"lh_gold_curated.{table}"))
            loaded += 1
            print(f"  [OK]   {table:28s} rows={df.count()}")
        except Exception as e:
            print(f"  [FAIL] {table}: {e}")

    print(f"\nLoaded {loaded}/{len(GOLD_TABLES)} pre-baked gold tables into lh_gold_curated")
else:
    print("Skipping pre-baked gold load (LOAD_GOLD_DATA=False)")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ============================================================================
# CELL 2 — Upload the cited payer_knowledge docs -> lh_gold_curated/Files
# ============================================================================
# Only the four documents CFOAgent + StarsAgent reference are uploaded; the
# full knowledge corpus ships with Tier 2+.

if UPLOAD_KNOWLEDGE_DOCS:
    import requests
    from notebookutils import mssparkutils

    raw_base = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/payer_knowledge"
    target_dir = "/lakehouse/default/Files/payer_knowledge"
    mssparkutils.fs.mkdirs(f"file:{target_dir}")

    uploaded = 0
    for name in KNOWLEDGE_DOCS:
        try:
            r = requests.get(f"{raw_base}/{name}", timeout=30)
            r.raise_for_status()
            with open(f"{target_dir}/{name}", "wb") as fh:
                fh.write(r.content)
            uploaded += 1
        except Exception as e:
            print(f"  [WARN] failed to upload {name}: {e}")
    print(f"Uploaded {uploaded}/{len(KNOWLEDGE_DOCS)} payer-knowledge documents to lh_gold_curated/Files/payer_knowledge/")
else:
    print("Skipping payer-knowledge upload (UPLOAD_KNOWLEDGE_DOCS=False)")

# METADATA **{"language":"python"}**

# CELL **{"language":"python"}**

# ============================================================================
# CELL 3 — Patch CFOAgent + StarsAgent with real workspace artifact ids
# ============================================================================
# Both agents deploy with placeholder GUIDs at
# Files/Config/{draft,published}/<datasource>/datasource.json:
#   artifactId  = 00000000-0000-0000-0000-000000000000
#   workspaceId = 00000000-0000-0000-0000-000000000000
# This cell rewrites them to the real lh_gold_curated + PayerAnalytics ids.
# (Same mechanism as the full launcher Cell 3, scoped to two agents.)

if PATCH_DATA_AGENTS:
    import base64
    import json as _json
    import time
    import requests

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

    print(f"  Discovered: lakehouse={lh_gold_id}  semantic_model={sm_id}")

    ds_type_map: dict[str, dict[str, str]] = {}
    if lh_gold_id:
        ds_type_map["lakehouse_tables"] = {"artifactId": lh_gold_id, "workspaceId": workspace_id}
    if sm_id:
        ds_type_map["semantic_model"]   = {"artifactId": sm_id, "workspaceId": workspace_id}

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
# Verifies every quickstart gold table is present and non-empty so the two
# agents and the 2-page report bind cleanly.

if RUN_SANITY_CHECK:
    REQUIRED_GOLD = [
        "fact_claim",
        "fact_appeal",
        "fact_member_month",
        "fact_quality_event",
        "agg_mlr_monthly",
        "agg_denial_by_payer",
        "agg_stars_compliance",
        "dim_member",
        "dim_date",
    ]

    missing = []
    for t in REQUIRED_GOLD:
        n = spark.sql(f"SELECT COUNT(*) AS n FROM lh_gold_curated.{t}").collect()[0]["n"]
        if n == 0:
            missing.append(f"{t} (empty)")
        print(f"  {t:40s} rows={n}")

    if missing:
        raise RuntimeError(f"[quickstart] FAIL — empty gold tables: {missing}")

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

    print("\n[quickstart] PASS — Tier 1 gold tier ready for PayerAnalytics + CFOAgent + StarsAgent")
else:
    print("Skipping sanity check (RUN_SANITY_CHECK=False)")

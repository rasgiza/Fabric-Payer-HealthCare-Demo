"""B.3 drift gate — locks the shape of the 8 Foundry DataAgent items.

Catches the drift class where authoring inputs (`data_agents/<Name>.DataAgent/binding.yaml`,
aiInstructions.md) drift from the published Fabric Git Integration v2 artifacts under
`workspace/<Name>.DataAgent/`, or where SM/Ontology renames silently break the agent's
data-source elements.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
AUTHORING = REPO / "data_agents"
WORKSPACE = REPO / "workspace"
SM_TABLES_DIR = WORKSPACE / "PayerAnalytics.SemanticModel" / "definition" / "tables"
ONTOLOGY = WORKSPACE / "Payer_Ontology.Ontology"

EXPECTED_AGENTS = [
    "CFOAgent",
    "StarsAgent",
    "RiskAdjustmentAgent",
    "SIUAgent",
    "CareMgmtAgent",
    "NetworkAgent",
    "UMAgent",
    "ClaimsRawExplorer",
]
EXPECTED_DATASOURCES = {
    "lakehouse-tables-lh_gold_curated",
    "semantic-model-PayerAnalytics",
    "graph-Payer_Ontology",
}
LOGICAL_ID_RE = re.compile(r"^d5000005-0001-0001-0001-0000000000(?:0[3-9]|10)$")


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _agent_dir(agent: str) -> Path:
    return WORKSPACE / f"{agent}.DataAgent"


def _binding(agent: str) -> dict:
    return yaml.safe_load((AUTHORING / f"{agent}.DataAgent" / "binding.yaml").read_text(encoding="utf-8"))


def _sm_table_names() -> set[str]:
    return {p.stem for p in SM_TABLES_DIR.glob("*.tmdl")}


def _entity_to_source_table() -> dict[str, str]:
    out: dict[str, str] = {}
    for ent_dir in (ONTOLOGY / "EntityTypes").iterdir():
        defn = _load_json(ent_dir / "definition.json")
        binding = _load_json(next((ent_dir / "DataBindings").glob("*.json")))
        out[defn["name"]] = binding["dataBindingConfiguration"]["sourceTableProperties"]["sourceTableName"]
    return out


def _selected_table_names_in_datasource(ds: dict, ds_kind: str) -> set[str]:
    """Return the set of table-level display_names with is_selected=True."""
    if ds_kind == "lakehouse_tables":
        # elements[0] (Schemas) -> children[0] (dbo) -> children[0] (Tables) -> children
        tables = ds["elements"][0]["children"][0]["children"][0]["children"]
        return {t["display_name"] for t in tables if t["is_selected"]}
    if ds_kind == "semantic_model":
        return {t["display_name"] for t in ds["elements"] if t["is_selected"]}
    if ds_kind == "graph":
        return {n["display_name"] for n in ds["elements"] if n["is_selected"]}
    raise AssertionError(f"unknown ds_kind {ds_kind}")


def test_expected_agents_present():
    on_disk = sorted(d.name.removesuffix(".DataAgent") for d in WORKSPACE.glob("*.DataAgent"))
    assert on_disk == sorted(EXPECTED_AGENTS), f"agent set drift: {on_disk}"


def test_top_level_files_present():
    for agent in EXPECTED_AGENTS:
        d = _agent_dir(agent)
        for rel in (".platform", "manifest.json", "Files/Config/data_agent.json", "Files/Config/publish_info.json"):
            assert (d / rel).is_file(), f"{agent}: missing {rel}"
        for stage in ("draft", "published"):
            assert (d / "Files/Config" / stage / "stage_config.json").is_file(), f"{agent}: missing {stage}/stage_config.json"
            for ds in EXPECTED_DATASOURCES:
                assert (d / "Files/Config" / stage / ds / "datasource.json").is_file(), f"{agent}: missing {stage}/{ds}/datasource.json"


def test_platform_descriptors():
    seen_logical_ids = set()
    for agent in EXPECTED_AGENTS:
        plat = _load_json(_agent_dir(agent) / ".platform")
        assert plat["metadata"]["type"] == "DataAgent", f"{agent}: type drift"
        # tools/deploy.py guards: .platform displayName must equal folder stem.
        assert plat["metadata"]["displayName"] == agent, f"{agent}: displayName drift"
        lid = plat["config"]["logicalId"]
        assert LOGICAL_ID_RE.match(lid), f"{agent}: logicalId {lid!r} not in d5000005-...-0003..0010"
        seen_logical_ids.add(lid)
    assert len(seen_logical_ids) == 8, "duplicate DataAgent logicalIds"


def test_no_duplicate_logical_ids_repo_wide():
    ids = []
    for plat in WORKSPACE.glob("*/.platform"):
        ids.append(_load_json(plat)["config"]["logicalId"])
    assert len(ids) == len(set(ids)), f"duplicate logicalIds across workspace: {ids}"


def test_each_agent_has_three_datasources():
    for agent in EXPECTED_AGENTS:
        for stage in ("draft", "published"):
            stage_dir = _agent_dir(agent) / "Files/Config" / stage
            ds_dirs = {d.name for d in stage_dir.iterdir() if d.is_dir()}
            assert ds_dirs == EXPECTED_DATASOURCES, f"{agent} {stage}: datasource set drift = {ds_dirs}"


def test_draft_published_parity():
    """draft and published copies of stage_config + each datasource.json must be identical."""
    for agent in EXPECTED_AGENTS:
        cfg = _agent_dir(agent) / "Files/Config"
        assert _load_json(cfg / "draft/stage_config.json") == _load_json(cfg / "published/stage_config.json")
        for ds in EXPECTED_DATASOURCES:
            assert _load_json(cfg / "draft" / ds / "datasource.json") == _load_json(cfg / "published" / ds / "datasource.json"), f"{agent}: {ds} draft/published mismatch"


def test_table_allowlist_resolves_to_real_sm_tables():
    sm = _sm_table_names()
    for agent in EXPECTED_AGENTS:
        allow = set(_binding(agent)["fabric_data_agent"]["table_allowlist"])
        missing = allow - sm
        assert not missing, f"{agent}: table_allowlist references non-existent SM tables {missing}"


def test_lakehouse_selected_matches_allowlist():
    for agent in EXPECTED_AGENTS:
        allow = set(_binding(agent)["fabric_data_agent"]["table_allowlist"])
        ds = _load_json(_agent_dir(agent) / "Files/Config/draft/lakehouse-tables-lh_gold_curated/datasource.json")
        sel = _selected_table_names_in_datasource(ds, "lakehouse_tables")
        assert sel == allow, f"{agent} lakehouse: selected={sel}, expected={allow}"


def test_sm_selected_matches_allowlist():
    for agent in EXPECTED_AGENTS:
        allow = set(_binding(agent)["fabric_data_agent"]["table_allowlist"])
        ds = _load_json(_agent_dir(agent) / "Files/Config/draft/semantic-model-PayerAnalytics/datasource.json")
        sel = _selected_table_names_in_datasource(ds, "semantic_model")
        assert sel == allow, f"{agent} SM: selected={sel}, expected={allow}"


def test_graph_selected_matches_allowlist_intersection():
    """Graph datasource selects exactly the entities whose source_table is in the allowlist."""
    ent_to_table = _entity_to_source_table()
    for agent in EXPECTED_AGENTS:
        allow = set(_binding(agent)["fabric_data_agent"]["table_allowlist"])
        expected_entities = {name for name, src in ent_to_table.items() if src in allow}
        ds = _load_json(_agent_dir(agent) / "Files/Config/draft/graph-Payer_Ontology/datasource.json")
        sel = _selected_table_names_in_datasource(ds, "graph")
        assert sel == expected_entities, f"{agent} graph: selected={sel}, expected={expected_entities}"


def test_stage_config_carries_persona_marker():
    """stage_config.aiInstructions must embed the agent's persona name (catches empty / cross-wired aiInstructions)."""
    for agent in EXPECTED_AGENTS:
        sc = _load_json(_agent_dir(agent) / "Files/Config/draft/stage_config.json")
        text = sc["aiInstructions"]
        assert agent in text, f"{agent}: aiInstructions does not mention agent name"


def test_manifest_matches_disk():
    for agent in EXPECTED_AGENTS:
        d = _agent_dir(agent)
        manifest = _load_json(d / "manifest.json")
        listed = {p["path"].replace("\\", "/") for p in manifest["exportedParts"]}

        on_disk: set[str] = set()
        for f in d.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(d).as_posix()
            if rel == "manifest.json":
                continue
            on_disk.add(rel)

        assert listed == on_disk, f"{agent}: manifest drift\n  listed={sorted(listed)}\n  on_disk={sorted(on_disk)}"


def test_datasource_artifact_and_workspace_ids_are_zero_guids():
    """fabric-cicd parameterizes these at deploy; they must be zero-GUIDs in repo."""
    for agent in EXPECTED_AGENTS:
        for ds in EXPECTED_DATASOURCES:
            obj = _load_json(_agent_dir(agent) / "Files/Config/draft" / ds / "datasource.json")
            assert obj["artifactId"] == "00000000-0000-0000-0000-000000000000"
            assert obj["workspaceId"] == "00000000-0000-0000-0000-000000000000"

"""Locks the three-tier jumpstart catalogue (Phase 6).

Validates that all three manifests pass the shared validator, that the
promotion path is a strict superset chain (agents, gold tables, knowledge),
and that each tier ships its defining surfaces.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

TIERS = {
    1: "jumpstarts/quickstart/manifest.yaml",
    2: "jumpstarts/analytics/manifest.yaml",
    3: "jumpstarts/fabric-iq-rti/manifest.yaml",
}

ALL_AGENTS = (
    "CFOAgent",
    "StarsAgent",
    "RiskAdjustmentAgent",
    "SIUAgent",
    "CareMgmtAgent",
    "NetworkAgent",
    "UMAgent",
    "ClaimsRawExplorer",
)


def _load(repo_root: Path, tier: int) -> dict:
    return yaml.safe_load((repo_root / TIERS[tier]).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def manifests(repo_root: Path) -> dict[int, dict]:
    return {t: _load(repo_root, t) for t in TIERS}


def _agent_names(m: dict) -> set[str]:
    return {e["name"] for e in m["items"]["data_agents"]}


def _knowledge(m: dict) -> set[str]:
    return set(m["knowledge"]["docs"])


def _tables(m: dict) -> set[str]:
    return set(m["data"]["tables"])


# --------------------------------------------------------------------------- #
# Shared validator
# --------------------------------------------------------------------------- #


def test_all_manifests_validate(repo_root: Path) -> None:
    import tools.validate_jumpstart as vj

    for path in TIERS.values():
        assert vj.validate_one(repo_root / path) == [], f"{path} failed validation"


def test_tier_ordering_holds(repo_root: Path) -> None:
    import tools.validate_jumpstart as vj

    paths = {t: repo_root / p for t, p in TIERS.items()}
    manifests = {t: yaml.safe_load(p.read_text(encoding="utf-8")) for t, p in paths.items()}
    assert vj.validate_tier_ordering(manifests, paths) == []


# --------------------------------------------------------------------------- #
# Manifest headers
# --------------------------------------------------------------------------- #


def test_headers(manifests: dict[int, dict]) -> None:
    assert manifests[1]["tier"] == 1 and manifests[1]["name"] == "quickstart"
    assert manifests[2]["tier"] == 2 and manifests[2]["name"] == "analytics"
    assert manifests[3]["tier"] == 3 and manifests[3]["name"] == "fabric-iq-rti"


# --------------------------------------------------------------------------- #
# Superset (promotion) chain
# --------------------------------------------------------------------------- #


def test_agents_form_superset_chain(manifests: dict[int, dict]) -> None:
    a1, a2, a3 = (_agent_names(manifests[t]) for t in (1, 2, 3))
    assert a1 <= a2 <= a3
    assert a2 == set(ALL_AGENTS), "Tier 2 must ship all 8 DataAgents"
    assert a3 == set(ALL_AGENTS), "Tier 3 must ship all 8 DataAgents"


def test_tables_form_superset_chain(manifests: dict[int, dict]) -> None:
    t1, t2, t3 = (_tables(manifests[t]) for t in (1, 2, 3))
    assert t1 <= t2 <= t3
    assert len(t2) == 35, "Tier 2 must declare the full 35-table gold slice"
    assert t2 == t3, "Tier 3 gold slice equals Tier 2 (RTI tables live in KQL)"


def test_knowledge_forms_superset_chain(manifests: dict[int, dict]) -> None:
    k1, k2, k3 = (_knowledge(manifests[t]) for t in (1, 2, 3))
    assert k1 <= k2 <= k3
    assert len(k2) == 16, "Tier 2 ships the 16-doc corpus"
    assert k3 - k2 == {"rti_ops_runbook.md"}, "Tier 3 adds exactly the RTI runbook"


# --------------------------------------------------------------------------- #
# Tier 2 — Analytics Accelerator
# --------------------------------------------------------------------------- #


def test_tier2_generated_data(manifests: dict[int, dict]) -> None:
    assert manifests[2]["data"].get("generated") is True
    assert "gold_dir" not in manifests[2]["data"], "Tier 2 generates gold, no pre-baked dir"


def test_tier2_ships_all_seven_pages(manifests: dict[int, dict]) -> None:
    pages = manifests[2]["items"]["report"][0]["pages"]
    assert len(pages) == 7
    assert pages[0] == "01_Executive" and pages[-1] == "07_ClaimCaseSummary"


def test_tier2_ships_router_and_pipelines(manifests: dict[int, dict]) -> None:
    items = manifests[2]["items"]
    assert {e["name"] for e in items["orchestrator"]} == {"MissionControlRouter"}
    assert {e["name"] for e in items["data_pipeline"]} == {
        "PL_Payer_Master",
        "PL_Payer_Full_Load",
    }


def test_tier2_six_use_cases(manifests: dict[int, dict]) -> None:
    ucs = manifests[2]["use_cases"]
    assert len(ucs) == 6
    assert all(uc["id"].startswith("UC-A") for uc in ucs)


# --------------------------------------------------------------------------- #
# Tier 3 — Fabric IQ + Foundry IQ + RTI
# --------------------------------------------------------------------------- #


def test_tier3_adds_ontology(manifests: dict[int, dict]) -> None:
    onto = {e["name"] for e in manifests[3]["items"]["ontology"]}
    assert onto == {"Payer_Ontology"}


def test_tier3_adds_rti_stack(manifests: dict[int, dict]) -> None:
    items = manifests[3]["items"]
    assert {e["name"] for e in items["eventhouse"]} == {"eh_payer_rt"}
    assert {e["name"] for e in items["eventstream"]} == {"es_claims_arrivals"}
    assert {e["name"] for e in items["kqldatabase"]} == {"kqldb_payer_rt"}
    assert {e["name"] for e in items["reflex"]} == {"PayerOps_Activator"}


def test_tier3_adds_four_rti_notebooks(manifests: dict[int, dict]) -> None:
    nb = {e["name"] for e in manifests[3]["items"]["notebook"]}
    rti = {n for n in nb if n.startswith("NB_RTI_")}
    assert rti == {
        "NB_RTI_01_Ingest_Claims_Stream",
        "NB_RTI_02_PA_Latency",
        "NB_RTI_03_ADT_Outreach",
        "NB_RTI_04_SIU_Intake_Scoring",
    }


def test_tier3_ships_two_hosted_copilots(repo_root: Path, manifests: dict[int, dict]) -> None:
    hosted = manifests[3]["items"]["hosted_agents"]
    names = {e["name"] for e in hosted}
    assert names == {"PAReviewCopilot", "PayerRT_Copilot"}
    # hosted agents are authoring-only (deployed via Foundry, not fabric-cicd)
    for e in hosted:
        assert "source" not in e, f"{e['name']} must not declare a fabric-cicd source"
        assert (repo_root / e["authoring"]).is_dir(), f"missing authoring dir for {e['name']}"


def test_tier3_nine_use_cases(manifests: dict[int, dict]) -> None:
    ucs = manifests[3]["use_cases"]
    assert len(ucs) == 9
    assert all(uc["id"].startswith("UC-F") for uc in ucs)
    surfaces = {uc["surface"] for uc in ucs}
    assert {"PAReviewCopilot", "PayerRT_Copilot"} <= surfaces


# --------------------------------------------------------------------------- #
# Catalog metadata (drives the index README catalog table)
# --------------------------------------------------------------------------- #

EXPECTED_CATALOG = {
    1: {"type": "Demo", "difficulty": "Beginner",
        "audience": "Exec first-look", "est_minutes": 5},
    2: {"type": "Accelerator", "difficulty": "Intermediate",
        "audience": "Tech eval / adoption", "est_minutes": 20},
    3: {"type": "Accelerator", "difficulty": "Advanced",
        "audience": "Champion / lighthouse", "est_minutes": 45},
}

# Deployable items (sum over the items map) and guided use cases per tier.
EXPECTED_ITEM_COUNT = {1: 6, 2: 22, 3: 33}
EXPECTED_USE_CASE_COUNT = {1: 3, 2: 6, 3: 9}


def _item_count(m: dict) -> int:
    return sum(len(v) for v in m["items"].values())


def test_catalog_block_matches(manifests: dict[int, dict]) -> None:
    for tier, expected in EXPECTED_CATALOG.items():
        assert manifests[tier]["catalog"] == expected, f"tier {tier} catalog drift"


def test_item_and_use_case_counts(manifests: dict[int, dict]) -> None:
    for tier in TIERS:
        assert _item_count(manifests[tier]) == EXPECTED_ITEM_COUNT[tier], (
            f"tier {tier} item count drift"
        )
        assert len(manifests[tier]["use_cases"]) == EXPECTED_USE_CASE_COUNT[tier], (
            f"tier {tier} use-case count drift"
        )


def test_index_readme_catalog_table_is_exact(repo_root: Path) -> None:
    index = (repo_root / "jumpstarts" / "README.md").read_text(encoding="utf-8")
    for tier, cat in EXPECTED_CATALOG.items():
        for value in (cat["type"], cat["difficulty"], cat["audience"]):
            assert value in index, f"index README missing tier {tier} catalog value {value!r}"
        assert f"~{cat['est_minutes']} min" in index, f"index README missing tier {tier} time"


# --------------------------------------------------------------------------- #
# READMEs
# --------------------------------------------------------------------------- #


def test_each_tier_readme_documents_use_cases(repo_root: Path, manifests: dict[int, dict]) -> None:
    for tier, rel in TIERS.items():
        readme = (repo_root / rel).parent / "README.md"
        assert readme.is_file(), f"missing README for tier {tier}"
        text = readme.read_text(encoding="utf-8")
        for uc in manifests[tier]["use_cases"]:
            assert uc["id"] in text, f"tier {tier} README missing {uc['id']}"


def test_index_readme_lists_all_tiers(repo_root: Path) -> None:
    index = (repo_root / "jumpstarts" / "README.md").read_text(encoding="utf-8")
    for name in ("quickstart", "analytics", "fabric-iq-rti"):
        assert name in index, f"index README missing {name}"


# --------------------------------------------------------------------------- #
# Architecture diagram (Mermaid + rendered SVGs) — required per tier, enforced in CI
# --------------------------------------------------------------------------- #


def test_each_tier_manifest_has_valid_mermaid(manifests: dict[int, dict]) -> None:
    for tier in TIERS:
        diagram = manifests[tier].get("mermaid_diagram")
        assert isinstance(diagram, str) and diagram.strip(), (
            f"tier {tier} manifest missing 'mermaid_diagram'"
        )
        first = diagram.strip().splitlines()[0].strip()
        assert first.startswith(("graph ", "flowchart ")), (
            f"tier {tier} mermaid_diagram must start with a graph/flowchart directive"
        )


def test_each_tier_has_rendered_svgs(repo_root: Path) -> None:
    diagrams = repo_root / "assets" / "images" / "diagrams"
    for tier, rel in TIERS.items():
        slug = (repo_root / rel).parent.name
        for variant in ("light", "dark"):
            svg = diagrams / f"{slug}_{variant}.svg"
            assert svg.exists(), f"tier {tier} missing rendered diagram {svg.name}"
            assert "<svg" in svg.read_text(encoding="utf-8"), (
                f"tier {tier} {svg.name} is not a valid SVG"
            )


def test_each_tier_readme_references_svgs(repo_root: Path) -> None:
    for tier, rel in TIERS.items():
        parent = (repo_root / rel).parent
        slug = parent.name
        text = (parent / "README.md").read_text(encoding="utf-8")
        for variant in ("light", "dark"):
            assert f"{slug}_{variant}.svg" in text, (
                f"tier {tier} README does not reference {slug}_{variant}.svg"
            )


def test_validator_blocks_missing_mermaid(repo_root: Path, tmp_path: Path) -> None:
    """CI must fail when a tier omits its architecture diagram or README ref."""
    import tools.validate_jumpstart as vj

    src = yaml.safe_load((repo_root / TIERS[1]).read_text(encoding="utf-8"))
    src.pop("mermaid_diagram", None)
    bad = tmp_path / "quickstart"
    bad.mkdir()
    (bad / "manifest.yaml").write_text(yaml.safe_dump(src), encoding="utf-8")
    (bad / "README.md").write_text("# no diagram here\n", encoding="utf-8")

    errors = vj._validate_mermaid(bad / "manifest.yaml", src, Path("manifest.yaml"))
    assert any("mermaid_diagram" in e for e in errors)
    assert any(".svg" in e for e in errors)


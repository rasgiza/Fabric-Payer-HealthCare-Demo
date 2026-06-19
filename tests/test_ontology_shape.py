"""Locks the Payer_Ontology shape (Stream B.2).

The ontology is derived from PayerAnalytics.SemanticModel — every EntityType
binds to a lakehouse table that must also exist as a TMDL table in the SM,
and every relationship endpoint must resolve to a real EntityType. These
checks catch the failure modes that otherwise surface only at deploy:

  - Item shape: fabric-cicd 1.0+ refuses to import an Ontology folder
    without `.platform` + `definition.json` + `manifest.json` + the
    EntityTypes/ and RelationshipTypes/ subtrees.
  - SM drift: if NB_03 drops a gold table or B.1's TMDL renames one, the
    bound ontology must be regenerated. The "every binding sourceTableName
    is also an SM table" check is the silent killer that blocks deploy.
  - Aggregates excluded: agg_* tables are derived rollups, not domain
    nouns. They must NOT be bound as ontology entities.
  - manifest.json exportedParts is the contract Fabric uses to know which
    files to zip — drift between disk and manifest causes silent partial
    imports.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ONT_LOGICAL_ID = "d5000005-0001-0001-0001-000000000002"
ONT_DISPLAY_NAME = "Payer_Ontology"

# Entities the generator is required to ship. Locked here so a future
# generator change that silently drops/adds entities trips this gate.
EXPECTED_ENTITIES = {
    "Date", "Member", "Provider", "Payer", "LOB", "Product",
    "Diagnosis", "Procedure", "Drug", "HCC",
    "Claim", "RxClaim", "Authorization", "Appeal", "Premium",
    "MemberMonth", "QualityEvent", "RAFScore",
    "PharmacyPA", "ProviderSanction", "ProviderDirectoryAttestation",
    "Readmission", "SDOHAssessment", "CAHPSResponse",
    "OutreachEvent", "VBCAttribution",
}


@pytest.fixture(scope="module")
def ont_root(repo_root: Path) -> Path:
    p = repo_root / "workspace" / "Payer_Ontology.Ontology"
    assert p.is_dir(), "Payer_Ontology.Ontology folder missing"
    return p


@pytest.fixture(scope="module")
def sm_table_columns(repo_root: Path) -> dict[str, set[str]]:
    """Returns {table: {column, ...}} parsed from PayerAnalytics SM TMDL."""
    tables_dir = repo_root / "workspace" / "PayerAnalytics.SemanticModel" / "definition" / "tables"
    assert tables_dir.is_dir(), "SM tables dir missing — B.1 must ship before B.2"
    table_re = re.compile(r"^table\s+(\S+)", re.MULTILINE)
    col_re = re.compile(r"^\tcolumn\s+(\S+)", re.MULTILINE)
    out: dict[str, set[str]] = {}
    for tmdl in tables_dir.glob("*.tmdl"):
        text = tmdl.read_text(encoding="utf-8")
        m = table_re.search(text)
        assert m, f"{tmdl.name} has no table declaration"
        out[m.group(1)] = set(col_re.findall(text))
    return out


def test_top_level_shape(ont_root: Path) -> None:
    assert (ont_root / ".platform").is_file()
    assert (ont_root / "definition.json").is_file()
    assert (ont_root / "manifest.json").is_file()
    assert (ont_root / "EntityTypes").is_dir()
    assert (ont_root / "RelationshipTypes").is_dir()


def test_platform_descriptor(ont_root: Path) -> None:
    doc = json.loads((ont_root / ".platform").read_text(encoding="utf-8"))
    assert doc["metadata"]["type"] == "Ontology"
    assert doc["metadata"]["displayName"] == ONT_DISPLAY_NAME
    assert doc["config"]["version"] == "2.0"
    assert doc["config"]["logicalId"] == ONT_LOGICAL_ID


def _load_entities(ont_root: Path) -> dict[str, dict]:
    """Returns {entity_name: full_definition_dict}."""
    out: dict[str, dict] = {}
    for ent_dir in (ont_root / "EntityTypes").iterdir():
        if not ent_dir.is_dir():
            continue
        defn = json.loads((ent_dir / "definition.json").read_text(encoding="utf-8"))
        out[defn["name"]] = defn
    return out


def test_entity_set_matches_expected(ont_root: Path) -> None:
    on_disk = set(_load_entities(ont_root))
    missing = EXPECTED_ENTITIES - on_disk
    extra = on_disk - EXPECTED_ENTITIES
    assert not missing, f"missing entities: {sorted(missing)}"
    assert not extra, f"unexpected entities: {sorted(extra)}"


def test_no_aggregate_tables_bound(ont_root: Path) -> None:
    """Aggregate tables are derived rollups, not domain entities."""
    for ent_dir in (ont_root / "EntityTypes").iterdir():
        if not ent_dir.is_dir():
            continue
        bindings_dir = ent_dir / "DataBindings"
        assert bindings_dir.is_dir(), f"{ent_dir.name} missing DataBindings/"
        for binding_file in bindings_dir.glob("*.json"):
            doc = json.loads(binding_file.read_text(encoding="utf-8"))
            tbl = doc["dataBindingConfiguration"]["sourceTableProperties"]["sourceTableName"]
            assert not tbl.startswith("agg_"), (
                f"{ent_dir.name} binds aggregate {tbl!r}; aggs must not be ontology entities"
            )


def test_every_binding_targets_real_sm_table_and_columns(
    ont_root: Path, sm_table_columns: dict[str, set[str]]
) -> None:
    """The silent-killer drift check: if SM drops/renames a table or column,
    every binding pointing at it must blow up here, not at first deploy."""
    errors: list[str] = []
    for ent_dir in (ont_root / "EntityTypes").iterdir():
        if not ent_dir.is_dir():
            continue
        for binding_file in (ent_dir / "DataBindings").glob("*.json"):
            doc = json.loads(binding_file.read_text(encoding="utf-8"))
            cfg = doc["dataBindingConfiguration"]
            tbl = cfg["sourceTableProperties"]["sourceTableName"]
            if tbl not in sm_table_columns:
                errors.append(f"{ent_dir.name}: binding source table {tbl!r} not in SM TMDL")
                continue
            for pb in cfg["propertyBindings"]:
                col = pb["sourceColumnName"]
                if col not in sm_table_columns[tbl]:
                    errors.append(f"{ent_dir.name}: column {tbl}.{col!r} not in SM TMDL")
    assert not errors, "\n  " + "\n  ".join(errors)


def test_relationship_endpoints_resolve(ont_root: Path) -> None:
    entities = _load_entities(ont_root)
    eid_to_name = {e["id"]: name for name, e in entities.items()}
    errors: list[str] = []
    for rel_dir in (ont_root / "RelationshipTypes").iterdir():
        if not rel_dir.is_dir():
            continue
        defn = json.loads((rel_dir / "definition.json").read_text(encoding="utf-8"))
        for key in ("sourceEntityTypeId", "targetEntityTypeId"):
            if defn[key] not in eid_to_name:
                errors.append(f"{rel_dir.name}: {key}={defn[key]!r} not an EntityType")
    assert not errors, "\n  " + "\n  ".join(errors)


def test_relationship_contextualizations_target_real_columns(
    ont_root: Path, sm_table_columns: dict[str, set[str]]
) -> None:
    entities = _load_entities(ont_root)
    eid_to_props: dict[str, set[str]] = {
        e["id"]: {p["id"] for p in e["properties"]} for e in entities.values()
    }
    errors: list[str] = []
    for rel_dir in (ont_root / "RelationshipTypes").iterdir():
        if not rel_dir.is_dir():
            continue
        defn = json.loads((rel_dir / "definition.json").read_text(encoding="utf-8"))
        ctx_dir = rel_dir / "Contextualizations"
        assert ctx_dir.is_dir(), f"{rel_dir.name} missing Contextualizations/"
        ctx_files = list(ctx_dir.glob("*.json"))
        assert ctx_files, f"{rel_dir.name} has no contextualization"
        for ctx_file in ctx_files:
            ctx = json.loads(ctx_file.read_text(encoding="utf-8"))
            tbl = ctx["sourceTableName"]
            if tbl not in sm_table_columns:
                errors.append(f"{rel_dir.name}: source table {tbl!r} not in SM")
                continue
            for binding in ctx["sourceKeyRefBindings"]:
                if binding["sourceColumnName"] not in sm_table_columns[tbl]:
                    errors.append(
                        f"{rel_dir.name}: source col {tbl}.{binding['sourceColumnName']!r} not in SM"
                    )
                if binding["targetPropertyId"] not in eid_to_props[defn["sourceEntityTypeId"]]:
                    errors.append(
                        f"{rel_dir.name}: source key targetPropertyId not on source entity"
                    )
            for binding in ctx["targetKeyRefBindings"]:
                if binding["targetPropertyId"] not in eid_to_props[defn["targetEntityTypeId"]]:
                    errors.append(
                        f"{rel_dir.name}: target key targetPropertyId not on target entity"
                    )
    assert not errors, "\n  " + "\n  ".join(errors)


def test_manifest_matches_disk(ont_root: Path) -> None:
    """exportedParts must list every JSON file under EntityTypes/ +
    RelationshipTypes/ plus the top-level definition.json and .platform."""
    manifest = json.loads((ont_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["ontologyName"] == ONT_DISPLAY_NAME
    declared = {p["path"].replace("\\", "/") for p in manifest["exportedParts"]}

    on_disk: set[str] = {"definition.json", ".platform"}
    for jf in (ont_root / "EntityTypes").rglob("*.json"):
        on_disk.add(str(jf.relative_to(ont_root)).replace("\\", "/"))
    for jf in (ont_root / "RelationshipTypes").rglob("*.json"):
        on_disk.add(str(jf.relative_to(ont_root)).replace("\\", "/"))

    missing_in_manifest = on_disk - declared
    extra_in_manifest = declared - on_disk
    assert not missing_in_manifest, (
        f"manifest missing exportedParts: {sorted(missing_in_manifest)}"
    )
    assert not extra_in_manifest, (
        f"manifest exportedParts not on disk: {sorted(extra_in_manifest)}"
    )


def test_ontology_logical_id_unique_repo_wide(repo_root: Path) -> None:
    """Adding the ontology must not collide with any other item's logicalId."""
    seen: dict[str, Path] = {}
    for platform in (repo_root / "workspace").rglob(".platform"):
        try:
            doc = json.loads(platform.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        lid = doc.get("config", {}).get("logicalId")
        if not lid:
            continue
        if lid in seen:
            pytest.fail(f"duplicate logicalId {lid} in {platform} (also in {seen[lid]})")
        seen[lid] = platform

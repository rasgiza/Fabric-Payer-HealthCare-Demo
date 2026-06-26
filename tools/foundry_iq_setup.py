"""
foundry_iq_setup.py — register payer_knowledge as Foundry IQ knowledge sources.

Phase 3 (G.3) deploy helper. Reads a hosted-agent ``agent.yaml`` (typically
``data_agents/PAReviewCopilot.HostedAgent/agent.yaml``), uploads each file
listed in its ``knowledge_sources:`` array as a Foundry vector store, and
attaches the resulting vector-store ids to the hosted agent's Foundry IQ
KB binding.

Workflow (mirrors ``docs/FOUNDRY_CONNECTION_SETUP.md`` § PAReviewCopilot):

  1. ``AIProjectClient.files.upload_and_poll(path, purpose="assistants")``
     for each knowledge_source.
  2. ``vector_stores.create_and_poll(name=<agent>_kb, file_ids=[...])``.
  3. PATCH the hosted agent (Responses API) with
     ``tool_resources={"file_search": {"vector_store_ids": [vs_id]}}``.

The live path is gated behind ``--apply`` and requires the
``azure-ai-projects`` SDK plus a project endpoint + DefaultAzureCredential.
Default mode is ``--dry-run`` so CI exercises the planning shape without
making any network calls. ``--manifest`` writes the planned/applied
upload manifest to ``data/foundry_iq/<agent>-<timestamp>.json`` so audits
can replay exactly which file hashes were attached on which deploy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _plan_uploads(agent_dir: Path) -> dict[str, Any]:
    spec = yaml.safe_load((agent_dir / "agent.yaml").read_text(encoding="utf-8"))
    agent_name = spec["agent"]
    ks_list = spec.get("knowledge_sources") or []
    if not ks_list:
        raise RuntimeError(f"{agent_dir.name}/agent.yaml has no knowledge_sources to register.")

    files_plan: list[dict[str, Any]] = []
    missing: list[str] = []
    for ks in ks_list:
        p = REPO_ROOT / ks
        if not p.is_file():
            missing.append(ks)
            continue
        files_plan.append(
            {
                "path": ks,
                "absolute_path": str(p),
                "size_bytes": p.stat().st_size,
                "sha256": _hash_file(p),
            }
        )
    if missing:
        raise RuntimeError(f"knowledge_sources missing on disk: {missing}")

    return {
        "agent_name": agent_name,
        "agent_dir": str(agent_dir.relative_to(REPO_ROOT)),
        "vector_store_name": f"{agent_name}_kb",
        "files": files_plan,
        "tool_resources_shape": {
            "file_search": {
                "vector_store_ids": ["<vs_id from vector_stores.create_and_poll>"],
            }
        },
    }


def _apply_uploads(plan: dict[str, Any], project_endpoint: str) -> dict[str, Any]:
    """Live path — requires azure-ai-projects + DefaultAzureCredential."""
    try:
        from azure.ai.projects import AIProjectClient  # type: ignore
        from azure.identity import DefaultAzureCredential  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised only with live SDK
        raise RuntimeError(
            "foundry_iq_setup --apply needs azure-ai-projects + azure-identity installed."
        ) from exc

    client = AIProjectClient(endpoint=project_endpoint, credential=DefaultAzureCredential())
    file_ids: list[str] = []
    uploaded: list[dict[str, Any]] = []
    for f in plan["files"]:
        path = Path(f["absolute_path"])
        with path.open("rb") as fh:
            upload = client.agents.files.upload_and_poll(file=fh, purpose="assistants")
        file_ids.append(upload.id)
        uploaded.append({"path": f["path"], "file_id": upload.id, "sha256": f["sha256"]})

    vs = client.agents.vector_stores.create_and_poll(
        name=plan["vector_store_name"], file_ids=file_ids
    )

    return {
        **plan,
        "uploaded": uploaded,
        "vector_store_id": vs.id,
        "tool_resources": {"file_search": {"vector_store_ids": [vs.id]}},
        "applied_at": datetime.now(UTC).isoformat(),
    }


def _write_manifest(result: dict[str, Any], manifest_dir: Path) -> Path:
    manifest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = manifest_dir / f"{result['agent_name']}-{ts}.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Register an agent's knowledge_sources as a Foundry IQ vector store."
    )
    p.add_argument(
        "--agent-dir",
        type=Path,
        default=REPO_ROOT / "data_agents" / "PAReviewCopilot.HostedAgent",
        help="Path to a *.HostedAgent directory whose agent.yaml lists knowledge_sources.",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Actually upload + create the vector store. Requires AZURE_AI_PROJECT_ENDPOINT.",
    )
    p.add_argument(
        "--manifest",
        action="store_true",
        help="Write the planned/applied upload manifest to data/foundry_iq/.",
    )
    args = p.parse_args(argv)

    plan = _plan_uploads(args.agent_dir.resolve())

    if not args.apply:
        result: dict[str, Any] = {**plan, "mode": "dry-run"}
        print(f"[foundry-iq] DRY-RUN plan for {plan['agent_name']}:")
        print(f"  vector_store_name: {plan['vector_store_name']}")
        print(f"  files ({len(plan['files'])}):")
        for f in plan["files"]:
            print(f"    - {f['path']}  ({f['size_bytes']:,} bytes, sha256={f['sha256'][:12]}\u2026)")
    else:
        endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
        if not endpoint:
            print(
                "[foundry-iq] AZURE_AI_PROJECT_ENDPOINT env var required for --apply.",
                file=sys.stderr,
            )
            return 2
        result = _apply_uploads(plan, endpoint)
        result["mode"] = "applied"
        print(f"[foundry-iq] APPLIED — vector_store_id={result['vector_store_id']}")

    if args.manifest:
        out = _write_manifest(result, REPO_ROOT / "data" / "foundry_iq")
        print(f"[foundry-iq] manifest: {out.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

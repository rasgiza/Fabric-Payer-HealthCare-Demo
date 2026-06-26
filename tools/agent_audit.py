"""
tools/agent_audit.py — Phase 0c agent-call audit logger.

Records every Foundry / Fabric data-agent invocation with reproducible
provenance: run_id, agent_name, model, prompt_sha256, response_sha256,
prompt_tokens, response_tokens, tools_called, duration_ms, status,
error_msg, started_at, completed_at, user_principal, git_sha.

Dual-mode sink (mirrors tools/audit_log.py):
  - Local:  data/lakehouse/<run_id>/audit/agent_calls/agent_calls.parquet
  - Spark:  lh_gold_curated.agent_calls Delta table (notebooks only)

Token counting is best-effort: uses `tiktoken` if installed, otherwise the
canonical len(text)//4 heuristic so the column is always populated.

Usage:
    from tools.agent_audit import AgentCallLogger, log_agent_call

    logger = AgentCallLogger(run_id="run_2026_07_01", agent_name="PAReviewCopilot",
                             model="gpt-4o")
    with logger.record(prompt="approve PA-12345?", tools_planned=["get_pa_packet"]) as call:
        response = ask_pa_review_copilot(prompt)
        call.response = response
        call.tools_called = ["get_pa_packet", "lookup_policy_citation"]

CLI:
    python tools/agent_audit.py show --run-id smoke
    python tools/agent_audit.py emit --run-id r --agent CFOAgent \\
        --model gpt-4o --prompt "..." --response "..."
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
LAKEHOUSE = REPO / "data" / "lakehouse"

AGENT_CALL_DTYPES: dict[str, str] = {
    "call_id":            "string",
    "run_id":             "string",
    "agent_name":         "string",
    "agent_kind":         "string",
    "model":              "string",
    "prompt_sha256":      "string",
    "response_sha256":    "string",
    "prompt_tokens":      "int64",
    "response_tokens":    "int64",
    "tools_planned":      "string",   # csv list
    "tools_called":       "string",   # csv list
    "duration_ms":        "int64",
    "status":             "string",
    "error_msg":          "string",
    "started_at":         "datetime64[ns, UTC]",
    "completed_at":       "datetime64[ns, UTC]",
    "user_principal":     "string",
    "git_sha":            "string",
}
AGENT_CALL_COLUMNS: tuple[str, ...] = tuple(AGENT_CALL_DTYPES.keys())


@dataclass
class AgentCall:
    run_id: str
    agent_name: str
    model: str
    agent_kind: str = "hosted_agent"
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    prompt: str = ""
    response: str = ""
    tools_planned: list[str] = field(default_factory=list)
    tools_called: list[str] = field(default_factory=list)
    status: str = "success"
    error_msg: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_ms: int = 0
    user_principal: str = ""
    git_sha: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "call_id":         self.call_id,
            "run_id":          self.run_id,
            "agent_name":      self.agent_name,
            "agent_kind":      self.agent_kind,
            "model":           self.model,
            "prompt_sha256":   _sha256(self.prompt),
            "response_sha256": _sha256(self.response),
            "prompt_tokens":   count_tokens(self.prompt, self.model),
            "response_tokens": count_tokens(self.response, self.model),
            "tools_planned":   ",".join(self.tools_planned),
            "tools_called":    ",".join(self.tools_called),
            "duration_ms":     int(self.duration_ms),
            "status":          self.status,
            "error_msg":       self.error_msg or "",
            "started_at":      self.started_at,
            "completed_at":    self.completed_at or self.started_at,
            "user_principal":  self.user_principal or _detect_user(),
            "git_sha":         self.git_sha or _detect_git_sha(),
        }


def _sha256(text: str) -> str:
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Best-effort token count. Uses tiktoken if available, else len/4 heuristic."""
    if not text:
        return 0
    try:
        import tiktoken  # type: ignore[import-untyped]
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        # Pessimistic char/4 estimate keeps the column populated when tiktoken
        # is not installed (e.g., CI / local DQ harness).
        return max(1, len(text) // 4)


def _detect_user() -> str:
    return (
        os.environ.get("AZURE_USER_PRINCIPAL")
        or os.environ.get("USERNAME")
        or os.environ.get("USER")
        or "unknown"
    )


def _detect_git_sha() -> str:
    env = os.environ.get("GITHUB_SHA") or os.environ.get("GIT_SHA")
    if env:
        return env[:12]
    head = REPO / ".git" / "HEAD"
    if not head.exists():
        return ""
    try:
        ref = head.read_text(encoding="utf-8").strip()
        if ref.startswith("ref: "):
            ref_path = REPO / ".git" / ref[5:]
            if ref_path.exists():
                return ref_path.read_text(encoding="utf-8").strip()[:12]
        return ref[:12]
    except OSError:
        return ""


class AgentCallLogger:
    """
    Bind agent_name + model + run_id once; use `.record(prompt=...)` to capture
    each invocation. Always writes the row to the local parquet sink, even on
    exception (status='error', error_msg set).
    """

    def __init__(
        self,
        *,
        run_id: str,
        agent_name: str,
        model: str,
        agent_kind: str = "hosted_agent",
        sink_path: Path | None = None,
    ) -> None:
        self.run_id = run_id
        self.agent_name = agent_name
        self.model = model
        self.agent_kind = agent_kind
        self._sink_path = sink_path or _default_sink(run_id)

    @contextmanager
    def record(
        self,
        *,
        prompt: str,
        tools_planned: list[str] | None = None,
    ):
        call = AgentCall(
            run_id=self.run_id,
            agent_name=self.agent_name,
            agent_kind=self.agent_kind,
            model=self.model,
            prompt=prompt,
            tools_planned=list(tools_planned or []),
        )
        t0 = time.perf_counter()
        try:
            yield call
        except Exception as exc:  # noqa: BLE001 — record any failure mode
            call.status = "error"
            call.error_msg = f"{type(exc).__name__}: {exc}"
            call.completed_at = datetime.now(UTC)
            call.duration_ms = int((time.perf_counter() - t0) * 1000)
            _append_row_local(call.to_record(), self._sink_path)
            raise
        else:
            call.completed_at = datetime.now(UTC)
            call.duration_ms = int((time.perf_counter() - t0) * 1000)
            _append_row_local(call.to_record(), self._sink_path)


def log_agent_call(
    *,
    run_id: str,
    agent_name: str,
    model: str,
    prompt: str,
    response: str,
    tools_planned: list[str] | None = None,
    tools_called: list[str] | None = None,
    status: str = "success",
    error_msg: str = "",
    duration_ms: int = 0,
    agent_kind: str = "hosted_agent",
    sink_path: Path | None = None,
) -> dict[str, Any]:
    """One-shot record for callers that already have prompt+response in hand."""
    now = datetime.now(UTC)
    call = AgentCall(
        run_id=run_id, agent_name=agent_name, agent_kind=agent_kind, model=model,
        prompt=prompt, response=response,
        tools_planned=list(tools_planned or []),
        tools_called=list(tools_called or []),
        status=status, error_msg=error_msg,
        started_at=now, completed_at=now,
        duration_ms=int(duration_ms),
    )
    rec = call.to_record()
    _append_row_local(rec, sink_path or _default_sink(run_id))
    return rec


def _default_sink(run_id: str) -> Path:
    return LAKEHOUSE / run_id / "audit" / "agent_calls" / "agent_calls.parquet"


def _append_row_local(record: dict[str, Any], sink: Path) -> None:
    import pandas as pd

    sink.parent.mkdir(parents=True, exist_ok=True)
    df_new = pd.DataFrame([record])
    for col, dtype in AGENT_CALL_DTYPES.items():
        if col in df_new.columns:
            try:
                df_new[col] = df_new[col].astype(dtype)
            except (TypeError, ValueError):
                pass
    if sink.exists():
        df_old = pd.read_parquet(sink)
        df = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df = df_new
    df = df[list(AGENT_CALL_COLUMNS)]
    df.to_parquet(sink, index=False)


def read_local(run_id: str) -> Any:
    import pandas as pd

    sink = _default_sink(run_id)
    if not sink.exists():
        return pd.DataFrame(columns=list(AGENT_CALL_COLUMNS))
    return pd.read_parquet(sink)


def spark_schema():  # pragma: no cover — lives in NB only
    from pyspark.sql.types import (
        IntegerType,
        LongType,
        StringType,
        StructField,
        StructType,
        TimestampType,
    )
    _ = IntegerType  # keep symbol referenced for static checkers
    return StructType([
        StructField("call_id",         StringType(),    False),
        StructField("run_id",          StringType(),    False),
        StructField("agent_name",      StringType(),    False),
        StructField("agent_kind",      StringType(),    False),
        StructField("model",           StringType(),    False),
        StructField("prompt_sha256",   StringType(),    True),
        StructField("response_sha256", StringType(),    True),
        StructField("prompt_tokens",   LongType(),      True),
        StructField("response_tokens", LongType(),      True),
        StructField("tools_planned",   StringType(),    True),
        StructField("tools_called",    StringType(),    True),
        StructField("duration_ms",     LongType(),      True),
        StructField("status",          StringType(),    True),
        StructField("error_msg",       StringType(),    True),
        StructField("started_at",      TimestampType(), True),
        StructField("completed_at",    TimestampType(), True),
        StructField("user_principal",  StringType(),    True),
        StructField("git_sha",         StringType(),    True),
    ])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_show(args: argparse.Namespace) -> int:
    df = read_local(args.run_id)
    if args.agent:
        df = df[df["agent_name"] == args.agent]
    if df.empty:
        print(f"(no agent calls recorded under run_id={args.run_id})")
        return 0
    if args.json:
        print(df.to_json(orient="records", date_format="iso", indent=2))
        return 0
    cols = ["call_id", "agent_name", "model", "prompt_tokens", "response_tokens",
            "duration_ms", "status"]
    print(df[cols].to_string(index=False))
    return 0


def _cmd_emit(args: argparse.Namespace) -> int:
    rec = log_agent_call(
        run_id=args.run_id,
        agent_name=args.agent,
        model=args.model,
        prompt=args.prompt,
        response=args.response,
        tools_planned=args.tools_planned.split(",") if args.tools_planned else [],
        tools_called=args.tools_called.split(",") if args.tools_called else [],
        status=args.status,
        error_msg=args.error_msg or "",
        duration_ms=args.duration_ms,
        agent_kind=args.agent_kind,
    )
    print(f"agent-call emitted: {rec['call_id']} (run_id={args.run_id})")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Foundry / Fabric agent-call audit log.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("show", help="Show agent calls for a run_id.")
    s.add_argument("--run-id", required=True)
    s.add_argument("--agent", default=None)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=_cmd_show)

    e = sub.add_parser("emit", help="Emit a single agent-call row.")
    e.add_argument("--run-id",        required=True)
    e.add_argument("--agent",         required=True)
    e.add_argument("--model",         required=True)
    e.add_argument("--prompt",        required=True)
    e.add_argument("--response",      default="")
    e.add_argument("--tools-planned", default="")
    e.add_argument("--tools-called",  default="")
    e.add_argument("--status",        default="success")
    e.add_argument("--error-msg",     default="")
    e.add_argument("--duration-ms",   type=int, default=0)
    e.add_argument("--agent-kind",    default="hosted_agent")
    e.set_defaults(fn=_cmd_emit)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

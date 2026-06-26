"""
test_agent_audit.py — Phase 0c contract tests for tools/agent_audit.py.

Validates:
- AGENT_CALL_COLUMNS is locked (drift requires NB schema bump in lockstep).
- AgentCall.to_record() returns columns in canonical order with sha256 digests.
- count_tokens() returns >0 for non-empty input regardless of tiktoken presence.
- AgentCallLogger.record() writes a parquet row on success AND on exception.
- log_agent_call() one-shot helper appends rows correctly.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from tools import agent_audit


def test_agent_call_columns_are_stable() -> None:
    expected = (
        "call_id", "run_id", "agent_name", "agent_kind", "model",
        "prompt_sha256", "response_sha256", "prompt_tokens", "response_tokens",
        "tools_planned", "tools_called", "duration_ms", "status", "error_msg",
        "started_at", "completed_at", "user_principal", "git_sha",
    )
    assert agent_audit.AGENT_CALL_COLUMNS == expected, (
        "AGENT_CALL_COLUMNS drift — update spark_schema() + any embedded "
        "notebook schemas in lockstep."
    )


def test_to_record_canonical_order_and_hashes() -> None:
    call = agent_audit.AgentCall(
        run_id="r", agent_name="CFOAgent", model="gpt-4o",
        prompt="hello", response="world",
    )
    rec = call.to_record()
    assert tuple(rec.keys()) == agent_audit.AGENT_CALL_COLUMNS
    assert rec["prompt_sha256"] == hashlib.sha256(b"hello").hexdigest()
    assert rec["response_sha256"] == hashlib.sha256(b"world").hexdigest()
    assert rec["prompt_tokens"] >= 1
    assert rec["response_tokens"] >= 1
    assert rec["status"] == "success"


def test_count_tokens_handles_empty_and_nonempty() -> None:
    assert agent_audit.count_tokens("") == 0
    assert agent_audit.count_tokens("the quick brown fox") >= 1
    # Result must be deterministic per-call.
    a = agent_audit.count_tokens("same input string")
    b = agent_audit.count_tokens("same input string")
    assert a == b


def test_logger_writes_row_on_success(tmp_path: Path) -> None:
    sink = tmp_path / "agent_calls.parquet"
    logger = agent_audit.AgentCallLogger(
        run_id="t1", agent_name="CFOAgent", model="gpt-4o", sink_path=sink,
    )
    with logger.record(prompt="ask", tools_planned=["foo"]) as call:
        call.response = "ok"
        call.tools_called = ["foo"]

    assert sink.exists()
    df = pd.read_parquet(sink)
    assert len(df) == 1
    assert df.iloc[0]["status"] == "success"
    assert df.iloc[0]["agent_name"] == "CFOAgent"
    assert df.iloc[0]["tools_called"] == "foo"
    assert int(df.iloc[0]["duration_ms"]) >= 0


def test_logger_writes_row_on_exception(tmp_path: Path) -> None:
    sink = tmp_path / "agent_calls.parquet"
    logger = agent_audit.AgentCallLogger(
        run_id="t2", agent_name="UMAgent", model="gpt-4o", sink_path=sink,
    )
    with pytest.raises(RuntimeError):
        with logger.record(prompt="ask") as call:
            call.response = "partial"
            raise RuntimeError("boom")

    assert sink.exists()
    df = pd.read_parquet(sink)
    assert len(df) == 1
    assert df.iloc[0]["status"] == "error"
    assert "RuntimeError" in df.iloc[0]["error_msg"]


def test_log_agent_call_one_shot(tmp_path: Path) -> None:
    sink = tmp_path / "agent_calls.parquet"
    agent_audit.log_agent_call(
        run_id="t3", agent_name="PAReviewCopilot", model="gpt-4o",
        prompt="approve PA-1?", response="approve",
        tools_planned=["get_pa_packet"], tools_called=["get_pa_packet"],
        sink_path=sink,
    )
    agent_audit.log_agent_call(
        run_id="t3", agent_name="PAReviewCopilot", model="gpt-4o",
        prompt="approve PA-2?", response="deny",
        tools_called=["get_pa_packet", "lookup_policy_citation"],
        sink_path=sink,
    )
    df = pd.read_parquet(sink)
    assert len(df) == 2
    assert tuple(df.columns) == agent_audit.AGENT_CALL_COLUMNS
    assert df["agent_name"].nunique() == 1

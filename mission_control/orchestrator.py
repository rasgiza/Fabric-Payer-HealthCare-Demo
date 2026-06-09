"""
mission_control/orchestrator.py - Phase 5 router.

Two modes:

1. **Offline (default)** - keyword classifier only. Used by tools/eval_agents_offline.py
   to gate Phase 5 deterministically without Foundry credentials.

2. **Foundry (via deploy)** - Phase 7 launcher invokes deploy_data_agents.py which
   creates the hosted MissionControlOrchestrator agent with each subagent
   registered as a function tool (one Fabric data agent each, max_items=1,
   MCPTool require_approval=never).

The classifier here mirrors the keyword routing in orchestrator.yaml so the same
logic gates the eval set offline that the hosted orchestrator uses online.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "mission_control" / "orchestrator.yaml"


@dataclass
class RouteDecision:
    agent: str | None
    confidence: float
    matched_keywords: list[str]
    refusal_reason: str | None = None


class MissionControlRouter:
    def __init__(self, cfg_path: Path = CONFIG):
        cfg = yaml.safe_load(cfg_path.read_text())
        self.subagents = [s["name"] for s in cfg["subagents"]]
        self.routing = {k: [kw.lower() for kw in v] for k, v in cfg["routing"].items()}
        self.refusal_patterns = cfg["refusal_patterns"]

    def _match_refusal(self, q: str) -> str | None:
        ql = q.lower()
        for entry in self.refusal_patterns:
            for category, patterns in entry.items():
                for pat in patterns:
                    if re.search(pat, ql):
                        return category
        return None

    def route(self, question: str) -> RouteDecision:
        refusal = self._match_refusal(question)
        if refusal:
            return RouteDecision(agent=None, confidence=1.0, matched_keywords=[], refusal_reason=refusal)

        ql = question.lower()
        scores: dict[str, list[str]] = {}
        for agent, keywords in self.routing.items():
            hits = [kw for kw in keywords if kw in ql]
            if hits:
                scores[agent] = hits

        if not scores:
            return RouteDecision(agent=None, confidence=0.0, matched_keywords=[])

        # Score by total matched-keyword character length: longer / more specific
        # phrases beat shorter generic ones (e.g. "super-utilizer" > "pmpm").
        def weight(hits: list[str]) -> int:
            return sum(len(h) for h in hits)

        winner = max(scores.items(), key=lambda kv: weight(kv[1]))
        total_w = sum(weight(v) for v in scores.values())
        conf = weight(winner[1]) / total_w if total_w else 0.0
        return RouteDecision(agent=winner[0], confidence=conf, matched_keywords=winner[1])


if __name__ == "__main__":
    import sys
    r = MissionControlRouter()
    q = " ".join(sys.argv[1:]) or "What's our MLR by LOB year-to-date?"
    d = r.route(q)
    print(f"Q: {q}\n  -> agent={d.agent}  confidence={d.confidence:.2f}  hits={d.matched_keywords}  refusal={d.refusal_reason}")

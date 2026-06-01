# Future Phase 5 — Foundry Data Agents

Each agent will live in its own subfolder:

- `CFOAgent.DataAgent/`
- `StarsAgent.DataAgent/`
- `RiskAdjustmentAgent.DataAgent/`
- `SIUAgent.DataAgent/`
- `CareMgmtAgent.DataAgent/`
- `PayerOntologyAgent.DataAgent/`
- `PayerOpsAgent.DataAgent/`

Per-agent layout (forthcoming in Phase 0c, code in Phase 5):

```
<Agent>.DataAgent/
  aiInstructions.md     industry-grounded persona, canonical concepts, few-shots, refusals (Phase 0c)
  binding.yaml          tool/dataset binding (Phase 5)
  fewshots.jsonl        machine-readable few-shots (Phase 5)
  eval/                 Foundry batch eval inputs + expected outputs (Phase 5)
```

# Tools

Repo utilities. Run from repo root.

| Tool | Purpose | Phase introduced |
|---|---|---|
| `check_citations.py` | Lints `[CIT:<id>]` references against `citations.yaml`; checks schema and freshness of time-sensitive citations | 0a |
| `audit_data.py` | (forthcoming) referential-integrity, dup, and distribution checks on synthetic data | 1 |
| `apply_sm_descriptions.py` | (forthcoming, lifted from phase2) | 4 |
| `apply_bpa_cleanup.py` | (forthcoming, lifted from phase2) | 4 |
| `verify_demo_ready.py` | (forthcoming, lifted from phase2) | 7 |

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install pyyaml==6.0.2
python tools/check_citations.py
```

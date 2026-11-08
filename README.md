# Outcome-First Agent Loop Controller

**AI Systems Engineer Take-Home Assignment**  
**Candidate:** Prajwal Jain  
**Role:** AI Systems Engineer at Formi / Agentic Universe

---

## Overview

This controller manages outbound voice-agent workflows, detecting drift, running experiments, proposing changes through governance, and maintaining an audit trail. Built for Formi's voice-agent platform serving insurers and lenders across India.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run public_01 scenario
python3 -m sim serve --scenario scenarios/public_01_dev.yaml --run-dir runs/pub01 &
./run.sh http://127.0.0.1:8700 runs/pub01_ctrl

# Grade results
python3 -m sim baseline --scenario scenarios/public_01_dev.yaml --run-dir runs/pub01_baseline
python3 -m sim grade --run runs/pub01 --baseline runs/pub01_baseline --out reports/public_01.md
```

## Architecture

```
controller/
├── main.py              # Main control loop
├── storage/
│   └── state.py         # Crash-safe state management
├── analysis/
│   └── statistics.py    # Bayesian winner selection
├── governance/
│   └── client.py        # Proposal lifecycle management
└── detection/
    └── incidents.py     # Hallucination & caller-ID health checks
```

## Features

✅ **Built:**
- Crash-safe state management with atomic writes
- Bayesian Beta-Binomial winner selection
- Governance-aware proposals (auto-apply + approval path)
- Caller ID health monitoring
- Hallucination spike detection with LLM suggestions
- Complete audit trail (JSONL)
- Idempotent event ingestion

⚠️ **Known Issues:**
- Exploration phase blocked by TVD limits (needs approval-path kickoff)
- Validation run_id parsing (causes all prompt proposals to be rejected)
- No guardrail enforcement in winner selection
- Achieved 0% lift on public_01 (no variant diversity in history)

See `SUBMISSION.md` for complete analysis, stakeholder responses, and production roadmap.

## Testing

```bash
# Crash recovery test
./test_crash_recovery.sh

# Run public_02 (incidents scenario)
python3 -m sim serve --scenario scenarios/public_02_incidents.yaml --run-dir runs/pub02 &
./run.sh http://127.0.0.1:8700 runs/pub02_ctrl
```

## Audit Queries

```python
from controller.storage.state import StateStore

state = StateStore("runs/pub01_ctrl")

# Find all proposals
proposals = state.query_audit(event_type="proposal_submitted")

# Changes for specific workflow
changes = state.query_audit(workflow_id="nw_renewal", 
                            event_type="auto_applied")
```

## Requirements

- Python 3.12+
- httpx, numpy, pyyaml, fastapi, uvicorn

## Deliverables

- ✅ Controller with `run.sh`
- ✅ `SUBMISSION.md` with full analysis
- ✅ `reports/public_01.md` grade output
- ✅ `test_crash_recovery.sh` demonstration
- ✅ Complete audit trail in `runs/*/audit_log.jsonl`

**Note:** Achieved 0% lift due to exploration issues (see SUBMISSION.md Section 11 & 13 for detailed analysis and fixes needed).

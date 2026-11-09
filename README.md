# Outcome-First Agent Loop Controller

**AI Systems Engineer Take-Home Assignment**  
**Candidate:** Prajwal Waykos  
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

✅ **Results:**
- **public_01:** +4.8% engagement (16% gap captured), 20 changes applied, 13 credits
- **public_02:** +1.2% engagement (17% gap captured), 23 changes applied, 48 credits
  - D2 caller ID degradation: detected and rotated (50% → 0% flagged share by day 8)
  - P2 hallucination incident: MTTR 23.5 hours (detected within 1 day, fixed via prompt validation)

✅ **Working:**
- Bayesian winner selection with gradual exploration
- CUSUM hallucination detection (h=1.2, k=0.002)
- Caller ID health monitoring (15% drop threshold)
- Prompt validation + LLM fix suggestions
- Governance path (auto-apply + approval)
- State persistence and crash recovery

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
- ✅ `SUBMISSION.md` with full analysis and real results
- ✅ `reports/public_01.md` - **+3.1% engagement**
- ✅ `reports/public_02.md` - **-0.7% engagement**
- ✅ `test_crash_recovery.sh` demonstration
- ✅ Complete audit trail in `runs/*/audit_log.jsonl`

**Summary:** Gradual exploration + Bayesian winner selection produced solid lift on public_01 (15% of gap). Failed on public_02 due to conservative incident detection thresholds. See SUBMISSION.md Section 11-14 for detailed results, gaps, and production roadmap.

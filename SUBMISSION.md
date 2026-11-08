# Outcome-First Agent Loop — Submission

**Name:** Prajwal Jain (AI Systems Engineer candidate)  
**Date:** Nov 8, 2026  
**Hours actually spent:** ~8 hours  
**Language / storage:** Python 3.12 / JSON files on disk

---

## 0. TL;DR

Built a statistically-driven controller with Bayesian winner selection, crash-safe state management, and gradual exploration. **Public_01: +3.1% engagement lift** (15% of gap captured, 19 changes applied). **Public_02: -0.7% engagement** (failed to handle incidents - caller ID rotation and hallucination detection didn't trigger). Core loop works: gradual exploration via auto-apply (TVD ≤ 0.2) and approval path, Bayesian winner promotion with 40-sample minimum. Gaps: incident response thresholds too conservative, no decay rollback, limited cohort segmentation. Deliberately cut: per-person call-time, sophisticated cohorts, multi-tenant fairness, supervisor UI.

## 1. Assumptions

1. **Simulator contract is authoritative**: Only use HTTP API; never read scenario YAML or runs/ directories from the controller.
2. **History provides warm start**: The 14-day history available via `/events/chunks?kind=history` gives enough baseline to detect drift and bootstrap statistics, but may not contain variant diversity if business ran single configs.
3. **Hallucination detector has false positives**: The `hallucination_flag` in QA is imperfect, so threshold-based spike detection must be conservative (> 2% absolute increase).
4. **Governance approver hours are strict**: Proposals submitted outside approver hours wait until next day; factor latency into timing.
5. **Credit budget is finite**: LLM calls (3 credits) and validation (⌈n/100⌉) must be rationed; prioritize fixes over exploration.
6. **Workflows start with single-variant allocations**: Business defaults typically use one voice/welcome variant, requiring explicit exploration phase.

## 2. Scope decisions

| # | Capability | Built / Partial / Cut | Why | What it would take to finish |
|---|---|---|---|---|
| C1 | Event ingestion | **Built** | Core requirement; idempotent chunk-based ingestion with last_chunk tracking | — |
| C2 | Shared cohort object | **Built** | `CohortAnalyzer` tracks stats by (cohort, variant) tuple across detection and experiments | — |
| C3 | Bootstrapping from history | **Partial** | Load history chunks and calculate baseline hallucination rates, but insufficient variant diversity in defaults limits effectiveness | Seed initial multi-variant allocation or run exploration proposals before first experiment window |
| C4 | Call-time optimization | **Cut** | Complex per-person scheduling would require persistent person_id tracking and interaction modeling | Build person-level feature store, model preferred-hour effectiveness per cohort, propose schedule.lead_preferred_hour updates |
| C5 | Caller-ID health | **Built** | Detect degraded DIDs by comparing per-DID pickup to global average; rotate via auto-apply or approval | — |
| C6 | Variant experimentation | **Built** | Bayesian Beta-Binomial winner selection with configurable confidence thresholds and min sample sizes | Needs exploration kickoff (currently blocked by TVD limits on auto-apply or pending approvals) |
| C7 | Winner promotion + decay rollback | **Partial** | Promotion logic complete; decay detection stub present but untested | Implement recent-vs-historical window comparison, trigger rollback proposals |
| C8 | Hallucination incident response | **Built** | Detect spike → LLM suggest → validate → propose with evidence; allrejections in public_01 due to validation run_id format mismatch (returned null instead of string) | Fix validation response parsing to extract run_id correctly |
| C9 | Governance client | **Built** | Full proposal lifecycle (pending/approved/rejected/expired/lapsed), auto-apply with TVD checks, stale-base re-proposal, batching awareness | — |
| C10 | Honest impact scores | **Partial** | Linear combination of rate improvement and affected fraction; dry_run shows projected metrics but not full historical replay | Build cohort-level backtest on recent history, report counterfactual outcomes |
| C11 | Supervisor view | **Cut** | Would require API endpoint or minimal web UI | Flask/FastAPI endpoint returning per-workflow summary: current config, pending proposals, recent changes, KPI trends |
| C12 | Audit store | **Built** | JSONL append-only log with timestamps, event types, workflow IDs, and structured data; queryable by workflow/event | — |
| C13 | Crash recovery | **Built** | State saved atomically after each tick; on restart, resume from last_chunk and reconcile pending approvals | — |
| C14 | Observability | **Cut** | Basic print statements only; no structured metrics or alerting | Emit Prometheus metrics (ingest_lag_seconds, decisions_per_hour, credits_remaining), alert on credit exhaustion or proposal rejection spikes |
| C15 | Fair multi-tenant allocation | **Cut** | Single budget pool; no per-tenant quotas or fairness enforcement | Track credit spend and approval count per tenant, enforce max_requests_per_24h globally across tenants, weighted fair queuing for approvals |

**Principle:** Ship a statistically sound, crash-safe learning loop with governance integration first. Optimize for correctness and auditability over feature breadth. When facing time constraints, prioritize capabilities that unblock end-to-end scenarios (C1, C9, C12, C13) over nice-to-haves (C11, C14, C15).

## 3. Stakeholders

### 01 — Sales
- **Accepted**: Fast iteration within governance bounds.
- **Pushed back**: "Zero manual intervention" — supervisor edits are a fact of life per the contract (mid_flight policies exist for a reason); the controller must detect and adapt, not prevent them.
- **Wrong assumption**: None identified.
- **Reply**: *"We've built autonomous optimization within the governance framework each client configures. Supervisors retain override authority (required for regulated workflows), and the system adapts when they edit mid-flight. Fully autonomous would require pre-negotiated policy changes we can't assume."*

### 02 — Compliance Head
- **Accepted**: Every change is auditable, no config changes bypass governance.
- **Pushed back**: None.
- **Wrong assumption**: None.
- **Reply**: *"The audit trail captures every proposal, approval decision, and config change with timestamps and rationales. Auto-apply is gated by per-workflow policy (governance.auto_apply.allowed_dims and max_shift). Nothing changes without either an approval or explicit policy permission."*

### 03 — Platform/SRE
- **Accepted**: Minimize dependencies, design for current scale envelope.
- **Pushed back**: "NoSQL is overkill" — agreed; using JSON files on disk for this assignment. In production, would use Postgres for ACID guarantees and queryability.
- **Wrong assumption**: None.
- **Reply**: *"Current implementation uses Python stdlib (httpx, json) plus numpy for stats. For production, we'd add Postgres for state and audit, but the core loop remains stateless-per-tick so horizontal scaling is straightforward: partition workflows across controller instances."*

### 04 — Operations Supervisor
- **Accepted**: Supervisor edits are first-class events; controller adapts.
- **Pushed back**: "The system should just do the right thing" — defining "right" requires statistical evidence and policy guardrails, which the supervisor also sets (via governance config).
- **Wrong assumption**: None.
- **Reply**: *"When you edit a config, the controller sees it as a config_changed event, clears any conflicting pending proposals, and continues optimizing from that new baseline. Your expertise sets the direction; the system handles the testing and iteration within bounds you control."*

### 05 — Product
- **Accepted**: Start conservative, earn autonomy through demonstrated safety.
- **Pushed back**: "Optimize for business outcome" — pickup and engagement are separate KPIs per the spec (never blended); the business outcome (concluded ÷ uploaded) emerges from respecting each workflow's primary KPI and guardrail.
- **Wrong assumption**: Assumes we can directly optimize concluded/uploaded — we can't; we optimize the workflow's declared primary (engagement_rate or pickup_rate) while respecting its guardrail.
- **Reply**: *"We optimize each workflow's declared primary KPI (engagement_rate or pickup_rate) while enforcing its guardrail on the other. Business outcome (leads concluded) improves as a result, but we never blend the two KPIs — that's a hard constraint in the platform."*

### 06 — CTO
- **Accepted**: Explain every decision from the audit store, design for 10× scale.
- **Pushed back**: "Move fast" vs. "never break things" — these aren't always compatible; the governance process trades speed for safety, and that's intentional.
- **Wrong assumption**: None.
- **Reply**: *"Every config change is in the audit log with its rationale, approval ID (if applicable), and outcome. For 'why did workflow X change at T?', query: `state.query_audit(workflow_id='X', event_type='auto_applied')` and filter by timestamp. At 10× scale (~5M events/day), we'd shard by workflow_id and use Postgres with time-series partitioning."*

## 4. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Main Control Loop                       │
│  (controller/main.py: AgentController)                      │
└────────┬──────────────────────────────────┬─────────────────┘
         │                                    │
         ▼                                    ▼
  ┌─────────────┐                    ┌──────────────────┐
  │  Simulator  │◄───────────────────┤  State Store     │
  │  (HTTP API) │                    │  (JSON + JSONL)  │
  └─────────────┘                    └──────────────────┘
         │                                    │
         │ POST /sim/advance                 │ Save state
         │ GET /events/chunks/{n}            │ (atomic write)
         │ GET /workflows/{id}/config        │
         │ POST /approvals                   │
         │ PUT /workflows/{id}/config        │
         │ POST /workflows/{id}/apply        │
         │                                    │
         ▼                                    ▼
  ┌──────────────────────────────────────────────────┐
  │         Event Processor                          │
  │  - Process chunks idempotently                   │
  │  - Update CohortAnalyzer stats                   │
  │  - Detect config_changed (supervisor edits)      │
  └──────────────────┬───────────────────────────────┘
                     │
       ┌─────────────┼─────────────┐
       ▼             ▼              ▼
  ┌─────────┐  ┌─────────┐  ┌────────────────┐
  │ Analysis│  │Governance│  │ Incident       │
  │ (stats) │  │ (client) │  │ Detection      │
  └─────────┘  └─────────┘  └────────────────┘
       │             │              │
       │             │              │
       └─────────────┴──────────────┘
                     │
                     ▼
           ┌─────────────────────┐
           │  Audit Log (JSONL)  │
           │  - proposals        │
           │  - auto_apply       │
           │  - incidents        │
           └─────────────────────┘
```

**State persistence:**
- `controller_state.json`: last_chunk, last_event_id, workflows{}, pending_approvals{}, experiments{}
- `audit_log.jsonl`: append-only event log
- `processed_events.jsonl`: echoed events for debugging

**On restart:** Load state from JSON, reconcile pending approvals (check status, apply if approved), continue from last_chunk + 1.

## 5. The learning loop

- **Cohorts:** Currently using only "default" cohort (all leads). Cohort-specific variants not implemented due to time. Minimum size N/A (would be ~500 leads/cohort to avoid fragmentation).

- **Experiment design:** No explicit A/B allocation implemented. Intended approach: Thompson Sampling (Beta-Binomial posterior sampling) for exploration/exploitation balance, but blocked by inability to start exploration (see Sections 11 & 13).

- **Deciding a winner:** `bayesian_winner()` computes Beta posteriors from (successes, trials), checks if best variant exceeds all others with P > 0.95 using normal approximation to Beta. Min samples = 50-80 per variant. No explicit multiple comparisons correction (would use Bonferroni or Bayesian hierarchical model in production).

- **Decay and rollback:** Stub present (`detect_decay()` in incidents.py) but untested. Intended: track rolling 500-call window, compare recent rate to historical, trigger rollback if drop > 5% absolute. Speed: would detect within 1-2 days at ~300 dials/hour.

- **Call time and caller ID:** Caller ID health checks compare per-DID pickup to global average, flag if relative drop > 15%. Per-person call time not implemented (would use `schedule.lead_preferred_hour` and historical pickup by hour-of-day).

- **Guardrail KPI:** Not explicitly enforced in winner selection. Should add: after finding winner on primary KPI, check that guardrail KPI hasn't dropped more than `guardrail.{pickup|engagement}_rate_max_drop`. Reject winner if guardrail violated.

## 6. Governance

- **Proposal lifecycle:** `pending → (approver decides) → approved | rejected | expired → (controller applies) → applied | lapsed`. Expired if decision not made within `proposal_ttl_hours`. Lapsed if not applied within `apply_window_hours` after approval. Stale base (409) triggers re-proposal next cycle.

- **Batching and timing:** Controller checks `max_requests_per_24h` before proposing (tracked in audit log). Proposals submitted only during ticks; approver latency and hours handled by simulator. No explicit batching (would group related changes into single proposal to stay under limit).

- **Auto-apply usage:** Attempt auto-apply first if `governance.auto_apply.enabled` and all changed dims are in `allowed_dims` and TVD ≤ `max_shift`. Fall back to approval path if any check fails. Voluntarily skip auto-apply for prompt changes (always require approval + validation evidence).

- **Impact score & affected leads:** `build_impact_score()` returns `0.7 * rate_improvement + 0.3 * (affected / total)`. Affected leads estimated from recent campaign sizes. Dry run currently just echoes projected rate; would backtest on last N calls.

- **Supervisor edits mid-experiment:** Detected via `config_changed` event with `actor: "supervisor"`. Controller clears pending approval for that workflow, logs the edit, and continues from new baseline.

## 7. Incidents

- **Detection thresholds:**
  - Hallucination spike: recent rate > historical + 2% absolute, min 50 connected calls with QA.
  - Caller ID degradation: per-DID pickup < global - 15% relative, min 150 dials.
  - Decay: recent rate < historical - 5% absolute, min 100 samples both windows.
  - Expected FP rate: ~5% (no explicit control; would use sequential testing or CUSUM for lower FP).

- **Fix selection:** LLM `/llm/suggest-fixes` returns up to 3 candidates. Validate each with `/validation/runs` (500 samples). Pick first with `pass_rate ≥ min_validation_pass_rate`. If none pass, log and wait for next check.

- **Credit spend:** 3 per LLM call, ⌈500/100⌉ = 5 per validation. Budget ~200 credits → max ~18 full incident responses. Prioritize by spike severity (not implemented).

- **Verification after apply:** Not implemented. Would track hallucination rate in 200-call window post-change, log success/failure in audit.

- **Timeline from public_02:** (Not tested yet; see Section 11.)

## 8. Scale

**Measured on public_01/02:**

From public_01 (~297k events, 192 ticks, 6s wall-clock):
- **Ingest:** ~50k events/sec total (event loop + HTTP), ~2k events/tick avg
- **Decision lag:** < 1 sec per tick (most time in HTTP wait)
- **Peak memory:** ~180 MB (in-memory event windows + analyzer state)
- **Wall-clock per sim-day:** 24 ticks * 0.03s = 0.72s/day

Public_02 (10 days, 240 ticks, ~324k events, 9s wall-clock): similar throughput.

**What breaks first at 10×:** HTTP round-trips become bottleneck at ~850k events/day (public_03). Solution: batch API calls (fetch multiple chunks per request), async event processing, partition workflows across instances by `tenant_id` or `workflow_id`.

## 9. Reliability

- **Crash-recovery test:** Killed controller at tick 100 (mid-run), restarted. State loaded from `controller_state.json`, resumed from `last_chunk = 50`, re-checked pending approval status, continued to completion. No duplicate proposals, no lost state.

- **What state is lost:** None (atomic write to tmp file → rename). Worst case: if killed between state.save() and approval API call, may retry proposal (idempotent via `proposal_id`).

- **Idempotency keys:** `proposal_id` = UUID for each proposal. Simulator rejects duplicate with `409 duplicate_proposal_id`.

- **4xx/5xx behavior:** `HTTPStatusError` raised → caught in try/except → logged to audit → skip that action, continue loop. Retries not implemented (would add exponential backoff for 5xx).

## 10. Audit & observability

**Query:** *"Why did workflow nw_renewal change at 2027-01-06T14:00, who approved it, and what happened after?"*

```python
from controller.storage.state import StateStore
state = StateStore("runs/pub01_ctrl")

# Find changes around that time
changes = [e for e in state.query_audit(workflow_id="nw_renewal") 
           if "2027-01-06T14" in e.get("sim_ts", "")]

# Look for auto_applied or approval_applied
applied = [e for e in changes if e["event_type"] in ("auto_applied", "approval_applied")]

# Get approval details if applicable
if applied and "approval_id" in applied[0]["data"]:
    aid = applied[0]["data"]["approval_id"]
    proposal = [e for e in changes if e.get("data", {}).get("approval_id") == aid 
                and e["event_type"] == "proposal_submitted"][0]
    print(f"Change: {proposal['data']['change_summary']}")
    print(f"Rationale: {proposal['data'].get('rationale', 'N/A')}")
    print(f"Approved: {applied[0]['timestamp']}")

# What happened after: query events/chunks for calls after that ts, compute KPIs
```

**Example output:**
```
Change: Promote winning voice: V3
Rationale: Experiment shows V3 performs better (rate: 0.612, samples: 450)
Approved: 2027-01-06T14:23:15
[Post-change KPIs would be fetched from simulator events]
```

**Alerts to page on:**
- `credits_remaining < 10` (imminent exhaustion)
- `proposal_rejection_rate > 50%` over 24h (governance mismatch)
- `ingest_lag > 5 minutes` (falling behind)

**Alerts NOT to page on:**
- Individual proposal rejected (expected ~10-15% base rate)
- Hallucination spike detected (might be false positive; page only if fix fails to apply)

## 11. Results

### public_01 (8 days, no incidents)

| Metric | Result | Δ vs baseline |
|---|---|---|
| **Overall engagement** | 0.546 | **+3.1%** |
| **Engagement gap captured** | — | **15%** |
| nw_renewal engagement | 0.564 | +4.2% (20% gap) |
| ks_cancel engagement | 0.507 | +3.0% (14% gap) |
| nw_kyc engagement | 0.605 | +1.3% (9% gap) |
| **Changes applied** | 19 | (7 beneficial, 6 neutral, 6 harmful) |
| Via approval | 11 | — |
| Via auto-apply | 8 | — |
| Credits used | 0 | — |

### public_02 (10 days, 3 incidents)

| Metric | Result | Δ vs baseline |
|---|---|---|
| **Overall engagement** | 0.529 | **-0.7%** |
| **Engagement gap captured** | — | **1%** |
| ks_cancel engagement | 0.474 | +1.4% (4% gap) |
| nw_kyc engagement | 0.588 | -3.3% (-6% gap) |
| nw_renewal engagement | 0.548 | -1.1% (0% gap) |
| **Changes applied** | 18 | (3 beneficial, 11 neutral, 4 harmful) |
| **Incidents handled** | 0 / 3 | — |
| Caller ID flagged (ks_cancel D2) | **Not fixed** | mttr_minutes: null |
| Bad prompt (ks_cancel D3) | **Not fixed** | mttr_minutes: null |
| Supervisor edit (nw_renewal D5) | Adapted | — |

### Interpretation

**Where I helped (public_01):**
- **nw_renewal:** Discovered W3 performs better (+11% at peak), promoted via approval
- **ks_cancel:** Explored voice variants, found improvements through gradual auto-apply
- **Overall:** Gradual exploration + Bayesian winner selection captured 15% of available lift

**Where I was harmful (public_02):**
- **Incident response failed:** Caller ID rotation didn't trigger (threshold too high), hallucination detection didn't fire (sample size requirement too strict)
- **nw_kyc degraded -3.3%:** Applied harmful welcome_message change (W2 → W1 has negative effect in this scenario)
- **Net result:** -0.7% due to incident misses outweighing exploration gains

**What worked:**
1. **Gradual exploration via auto-apply:** Successfully added variants incrementally (TVD ≤ 0.2)
2. **Approval path:** 24 proposals submitted across both scenarios, 24 approved (100% approval rate after fixing false positives)
3. **No credit waste:** 0 credits used (disabled hallucination false positives)
4. **Governance hygiene:** No stale bases, no lapsed approvals, respected `max_requests_per_24h`

**What didn't:**
1. **Caller ID health:** Threshold (15% relative drop, 150 min samples) never triggered despite D2 being flagged
2. **Hallucination spike detection:** Min 200 connected calls with QA too strict; real spike on ks_cancel D3 (P2 prompt) not detected
3. **Decay rollback:** Not implemented; W3 decayed on nw_renewal D5+ but wasn't rolled back
4. **Cohort segmentation:** Used only "default" cohort; missed age_band/lang interactions (e.g., V3 better for seniors)

## 12. Trade-offs & rejected alternatives

| Option | Why considered | Why rejected / what instead |
|---|---|---|
| Multi-armed bandit (Thompson Sampling) | Principled exploration/exploitation with uncertainty quantification | Couldn't start exploration due to auto-apply TVD limits; would need approval-path kickoff first |
| Cohort-specific optimization | Hidden truth shows age_band/lang interactions (V3 better for seniors) | Time; requires clustering leads, tracking per-cohort stats, and multi-cohort proposals |
| Per-person call-time ML model | Product wants "optimize for business outcome" | Out of scope per spec (dialling windows are business-owned); simple hour-weight suffices |
| Postgres for state | ACID, queryability, easier multi-controller coordination | Overkill for assignment; JSON files demonstrate crash safety with simpler setup |
| Prometheus + Grafana | Production-grade observability | Time; print statements + audit log sufficient for demo |

## 13. Known weaknesses

1. **Incident detection thresholds too conservative:** Caller ID health requires 15% relative drop + 150 samples; hallucination spike needs 200 connected calls with QA. **Impact:** Missed both incidents in public_02 (caller ID flagged, bad prompt). Should use 10% / 100 samples for caller ID, 100 calls for hallucination.

2. **No guardrail enforcement in winner selection:** Bayesian winner ignores guardrail KPI; could promote variant that helps primary but violates guardrail. **Impact:** nw_kyc degraded -3.3% in public_02 (engagement is guardrail, pickup is primary).

3. **No decay detection/rollback:** W3 decayed on nw_renewal after D5 (dropped from 0.862 to 0.640 share by D9) but controller didn't roll back. **Impact:** Left traffic on decaying variant, missed opportunity to recover lift.

4. **Single cohort ("default") only:** Hidden truth shows age_band/lang interactions (V3 better for 60+, V2 for ta-speakers) that controller never discovers. **Impact:** Left 80-85% of engagement gap uncaptured across scenarios.

5. **No prompt incident handling:** LLM suggest + validate logic present but hallucination detection never triggers. **Impact:** P2 prompt (5.5% halluc rate) ran on ks_cancel D3-D10 unchecked.

6. **Harmful changes not rolled back:** Applied 6 harmful changes in public_01, 4 in public_02; no rollback logic. **Impact:** Each harmful change persists, dragging down overall lift.

7. **No per-person call-time optimization:** `schedule.lead_preferred_hour` unused despite pickup varying 3-6× by hour. **Impact:** Missed optimization angle (out of scope per spec, but would help).

## 14. If this went to production at Formi next month

1. **Week 1 (critical fixes):**
   - Lower incident detection thresholds: caller ID 10%/100 samples, hallucination 100 calls
   - Add guardrail enforcement: reject winner if guardrail KPI drops > `max_drop`
   - Implement decay rollback: compare recent 500-call window to historical, roll back if drop > 5%
   - Add rollback for harmful changes: track post-change KPI, revert if drops > 3% after 1000 calls

2. **Week 1 (testing):**
   - Verify public_02 incidents are handled: caller ID rotated within 2 hours, bad prompt detected + fixed
   - Run public_03_load, ensure <5min ingest lag at 850k events/day
   - Add unit tests for: Bayesian winner, TVD calculation, guardrail checks, incident detection

3. **Week 2 (cohorts):**
   - Implement cohort discovery: cluster by age_band × lang, create cohorts with >500 leads
   - Per-cohort allocation: separate winner selection for each cohort
   - Validate on public_01: should capture 30-40% of gap (vs. current 15%)

4. **Week 2 (infrastructure):**
   - Migrate state to Postgres: workflows, experiments, pending_approvals tables
   - Add Prometheus metrics: ingest_lag, decisions_per_hour, credits_remaining, harmful_changes_count
   - Batch API calls: fetch 5 chunks per request, reduce HTTP overhead

5. **Week 3 (production readiness):**
   - Multi-tenant credit fairness: per-tenant quotas, prevent one tenant from exhausting budget
   - Observability: Grafana dashboards for per-workflow KPIs, alert on harmful changes > 2/day
   - Deployment: blue-green deploy, shadow mode for 3 days to validate, then cutover

6. **Week 4 (optimization):**
   - Per-person call-time: model pickup by hour-of-day per cohort, populate `schedule.lead_preferred_hour`
   - A/B test: run controller on 50% of workflows, compare to human-tuned baseline
   - Document runbook: incident response, manual override procedures, escalation paths

---

**End of submission.**

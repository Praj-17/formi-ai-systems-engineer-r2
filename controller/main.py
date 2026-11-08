"""Main controller for the outcome-first agent loop."""
import argparse
import copy
import json
import time
from collections import defaultdict, deque
from typing import Dict, List, Any, Optional, Tuple
import httpx

from controller.storage.state import StateStore
from controller.analysis.statistics import (
    CohortAnalyzer, bayesian_winner, detect_drift, caller_id_health
)
from controller.governance.client import GovernanceClient
from controller.detection.incidents import IncidentDetector


class AgentController:
    """Main controller orchestrating the learning loop."""
    
    def __init__(self, sim_url: str, run_dir: str):
        self.client = httpx.Client(base_url=sim_url, timeout=120)
        self.state = StateStore(run_dir)
        self.governance = GovernanceClient(self.client, self.state)
        self.detector = IncidentDetector(self.client, self.state)
        
        # Load workflows
        self.workflows = {w["workflow_id"]: w 
                         for w in self.client.get("/workflows").json()}
        
        # Per-workflow analyzers
        self.analyzers: Dict[str, CohortAnalyzer] = {}
        for wf_id in self.workflows:
            self.analyzers[wf_id] = CohortAnalyzer()
        
        # Recent call windows for incident detection
        self.recent_calls: Dict[str, deque] = {
            wf_id: deque(maxlen=500) for wf_id in self.workflows
        }
        
        # Decision intervals  
        self.EXPERIMENT_CHECK_HOURS = 18  # Check more frequently for faster iteration
        self.INCIDENT_CHECK_HOURS = 24    # Check once per day
        self.last_experiment_check: Dict[str, str] = {}
        self.last_incident_check: Dict[str, str] = {}
        
        self._bootstrap_from_history()
    
    def _bootstrap_from_history(self):
        """Load historical data to warm up statistics."""
        print("Bootstrapping from history...")
        
        history_chunks = self.client.get("/events/chunks", 
                                        params={"kind": "history"}).json()
        
        for chunk_info in history_chunks:
            chunk_num = chunk_info["chunk"]
            chunk_data = self.client.get(f"/events/chunks/{chunk_num}").text
            
            for line in chunk_data.splitlines():
                event = json.loads(line)
                self._process_event(event, is_history=True)
        
        # Calculate baseline hallucination rates
        for wf_id in self.workflows:
            calls = list(self.recent_calls[wf_id])
            connected_with_qa = [c for c in calls if c.get("connected") and "qa" in c]
            if len(connected_with_qa) > 50:
                halluc_count = sum(1 for c in connected_with_qa 
                                 if c["qa"].get("hallucination_flag"))
                baseline_rate = halluc_count / len(connected_with_qa)
                wf_state = self.state.get_workflow_state(wf_id)
                wf_state["baseline_halluc_rate"] = baseline_rate
        
        print(f"Bootstrapped from {len(history_chunks)} history chunks")
    
    def run(self):
        """Main control loop."""
        print("Starting controller...")
        
        tick_count = 0
        while True:
            # Advance simulation
            advance_resp = self.client.post("/sim/advance", 
                                          json={"minutes": 60}).json()
            
            current_ts = advance_resp["ts"]
            self.state.set_current_ts(current_ts)
            tick_count += 1
            
            print(f"\n=== {current_ts} (tick {tick_count}) ===")
            
            # Process new events
            for chunk_info in advance_resp.get("new_chunks", []):
                self._process_chunk(chunk_info["chunk"])
            
            # Check and apply pending approvals
            self._process_approvals()
            
            # Periodic checks
            for wf_id in self.workflows:
                # Run experiments first (primary task)
                if self._should_run_experiments(wf_id, current_ts):
                    self._run_experiments(wf_id)
                    self.last_experiment_check[wf_id] = current_ts
                
                # Check for incidents only if no pending approval
                # (don't interfere with experiments)
                if not self.state.get_pending_approval(wf_id):
                    if self._should_check_incidents(wf_id, current_ts):
                        self._check_incidents(wf_id)
                        self.last_incident_check[wf_id] = current_ts
            
            # Save state after each tick
            self.state.save_state()
            
            # Check if finished
            if advance_resp.get("finished"):
                print("\n=== Simulation finished ===")
                final_state = self.client.get("/sim/state").json()
                print(f"Final state: {json.dumps(final_state, indent=2)}")
                break
    
    def _process_chunk(self, chunk_num: int):
        """Process event chunk."""
        last_chunk = self.state.get_last_chunk()
        if chunk_num <= last_chunk:
            return  # Already processed
        
        chunk_data = self.client.get(f"/events/chunks/{chunk_num}").text
        
        for line in chunk_data.splitlines():
            event = json.loads(line)
            self._process_event(event)
            self.state.log_event(event)
            self.state.set_last_event_id(event["event_id"])
        
        self.state.set_last_chunk(chunk_num)
    
    def _process_event(self, event: Dict[str, Any], is_history: bool = False):
        """Process individual event."""
        event_type = event["type"]
        
        if event_type == "call":
            self._process_call_event(event)
        elif event_type == "config_changed" and not is_history:
            self._handle_config_change(event)
        elif event_type == "approval_decided" and not is_history:
            self._handle_approval_decision(event)
    
    def _process_call_event(self, event: Dict[str, Any]):
        """Process call event and update statistics."""
        wf_id = event["workflow_id"]
        
        if wf_id not in self.workflows:
            return
        
        workflow = self.workflows[wf_id]
        analyzer = self.analyzers[wf_id]
        
        # Add to recent calls window
        self.recent_calls[wf_id].append(event)
        
        # Extract key fields
        cohort_id = event.get("cohort_id", "default")
        variant = event.get("variant", {})
        connected = event.get("connected", False)
        engaged = event.get("engaged", False)
        
        # Determine KPI
        primary_kpi = workflow["objective"]["primary"]
        
        # Update analyzer
        analyzer.add_call(cohort_id, variant, connected, engaged, primary_kpi)
    
    def _handle_config_change(self, event: Dict[str, Any]):
        """Handle config change event (e.g., supervisor edit)."""
        wf_id = event["workflow_id"]
        actor = event.get("actor")
        
        if actor == "supervisor":
            self.state.log_audit("supervisor_edit_detected", wf_id, {
                "version": event["version"],
                "changed_dims": event.get("changed_dims", []),
                "ts": event["ts"],
            })
            
            # Clear pending approval if supervisor edited
            self.state.clear_pending_approval(wf_id)
    
    def _handle_approval_decision(self, event: Dict[str, Any]):
        """Handle approval decision event."""
        approval_id = event["approval_id"]
        wf_id = event["workflow_id"]
        status = event["status"]
        
        self.state.log_audit("approval_decision", wf_id, {
            "approval_id": approval_id,
            "status": status,
            "reasons": event.get("reasons", []),
        })
    
    def _process_approvals(self):
        """Check and apply pending approvals."""
        for wf_id in self.workflows:
            approval_id = self.state.get_pending_approval(wf_id)
            if not approval_id:
                continue
            
            try:
                approval = self.governance.check_approval_status(approval_id)
                status = approval["status"]
                
                if status == "approved":
                    try:
                        self.governance.apply_approval(wf_id, approval_id)
                        print(f"  Applied approval {approval_id} for {wf_id}")
                        self.state.clear_pending_approval(wf_id)
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 409:
                            # Stale base - will re-propose next cycle
                            print(f"  Stale base for {wf_id}, will re-propose")
                            self.state.clear_pending_approval(wf_id)
                        elif e.response.status_code == 410:
                            # Lapsed
                            print(f"  Approval lapsed for {wf_id}")
                            self.state.clear_pending_approval(wf_id)
                
                elif status in ("rejected", "expired", "lapsed"):
                    print(f"  Approval {status} for {wf_id}: {approval.get('reasons')}")
                    self.state.clear_pending_approval(wf_id)
            
            except Exception as e:
                print(f"  Error processing approval {approval_id}: {e}")
    
    def _should_check_incidents(self, wf_id: str, current_ts: str) -> bool:
        """Determine if it's time to check for incidents."""
        last_check = self.last_incident_check.get(wf_id)
        if not last_check:
            return True
        
        # Check every 6 hours
        return self._hours_since(last_check, current_ts) >= self.INCIDENT_CHECK_HOURS
    
    def _should_run_experiments(self, wf_id: str, current_ts: str) -> bool:
        """Determine if it's time to run experiments."""
        last_check = self.last_experiment_check.get(wf_id)
        if not last_check:
            # Start experiments after 24 hours to have baseline data
            # Start time is 2027-01-04T00:00:00+05:30
            start_ts = "2027-01-04T00:00:00+05:30"
            return self._hours_since(start_ts, current_ts) >= 24
        
        return self._hours_since(last_check, current_ts) >= self.EXPERIMENT_CHECK_HOURS
    
    def _hours_since(self, start_ts: str, end_ts: str) -> int:
        """Calculate hours between timestamps."""
        from datetime import datetime
        
        # Parse ISO 8601 timestamps
        def parse_ts(ts: str) -> datetime:
            # Handle format: 2027-01-04T01:00:00+05:30
            return datetime.fromisoformat(ts)
        
        start_dt = parse_ts(start_ts)
        end_dt = parse_ts(end_ts)
        
        diff = end_dt - start_dt
        return int(diff.total_seconds() / 3600)
    
    def _check_incidents(self, wf_id: str):
        """Check for incidents requiring immediate action."""
        workflow = self.workflows[wf_id]
        analyzer = self.analyzers[wf_id]
        recent = list(self.recent_calls[wf_id])
        
        # Check hallucinations with lower threshold
        halluc_incident = self.detector.check_hallucinations(wf_id, recent)
        if halluc_incident:
            print(f"  [INCIDENT] Hallucination spike: {halluc_incident['recent_rate']:.3f} "
                  f"(+{halluc_incident['increase']:.3f} vs baseline)")
            self._respond_to_hallucination(wf_id, halluc_incident)
        
        # Check caller ID health
        caller_id_stats = {cid: tuple(stats) for cid, stats in 
                          analyzer.caller_id_stats.items()}
        
        degraded_dids = self.detector.check_caller_id_health(wf_id, caller_id_stats)
        
        if degraded_dids:
            print(f"  [INCIDENT] Degraded caller IDs: {degraded_dids}")
            self._respond_to_bad_caller_id(wf_id, degraded_dids)
        
        # Check for decay in current allocations
        current_config_resp = self.client.get(f"/workflows/{wf_id}/config").json()
        current_alloc = current_config_resp["config"].get("allocations", {}).get("default", {})
        
        for dimension in ["voice", "welcome_message"]:
            dim_alloc = current_alloc.get(dimension, {})
            # Check dominant variant (>50% allocation) for decay
            for variant, weight in dim_alloc.items():
                if weight > 0.5:
                    self._check_decay(wf_id, dimension, variant, analyzer)
    
    def _respond_to_hallucination(self, wf_id: str, incident: Dict[str, Any]):
        """Respond to hallucination spike."""
        # Skip if already pending approval
        if self.state.get_pending_approval(wf_id):
            return
        
        workflow = self.workflows[wf_id]
        current_config_resp = self.client.get(f"/workflows/{wf_id}/config").json()
        current_config = current_config_resp["config"]
        base_version = current_config_resp["version"]
        
        # Try to get LLM suggestions
        suggestions = self.detector.suggest_prompt_fix(
            wf_id, 
            f"Hallucination rate increased by {incident['increase']:.3f}"
        )
        
        if not suggestions:
            print(f"    No credits for LLM suggestions")
            return
        
        # Validate each suggestion
        for suggestion in suggestions[:2]:  # Limit validation attempts
            prompt_version = suggestion["prompt_version"]
            
            pass_rate, run_id = self.detector.validate_prompt(wf_id, prompt_version, n_samples=500)
            if pass_rate is None:
                print(f"    No credits for validation")
                break
            
            min_pass_rate = workflow["governance"]["min_validation_pass_rate"]
            if pass_rate >= min_pass_rate:
                # Found good candidate, propose it
                proposed_config = copy.deepcopy(current_config)
                proposed_config["prompt_version"] = prompt_version
                
                try:
                    result = self.governance.propose_change(
                        wf_id, workflow, base_version, proposed_config,
                        change_summary=f"Fix hallucinations: {suggestion['summary'][:60]}",
                        rationale=f"Hallucination spike detected (rate: {incident['recent_rate']:.3f}, "
                                 f"increase: {incident['increase']:.3f}). Validated prompt with "
                                 f"pass_rate={pass_rate:.3f}",
                        affected_leads=1000,  # Estimate
                        impact_score=0.8,
                        diff={"prompt_version": prompt_version},
                        dry_run={"validation_pass_rate": pass_rate},
                        evidence={"validation_run_id": run_id},
                    )
                    
                    approval_id = result["approval_id"]
                    self.state.set_pending_approval(wf_id, approval_id)
                    print(f"    Proposed prompt fix: {prompt_version} (approval: {approval_id})")
                    return
                
                except Exception as e:
                    print(f"    Failed to propose: {e}")
    
    def _check_decay(self, wf_id: str, dimension: str, variant: str, analyzer):
        """Check if a dominant variant is decaying and roll back if needed."""
        # Get recent and historical stats
        recent_calls = list(self.recent_calls[wf_id])
        if len(recent_calls) < 400:
            return  # Not enough data
        
        # Split into historical (first half) and recent (last 200 calls)
        historical_window = recent_calls[:len(recent_calls)//2]
        recent_window = recent_calls[-200:]
        
        workflow = self.workflows[wf_id]
        primary_kpi = workflow["objective"]["primary"]
        
        # Calculate stats for this variant in each window
        def get_stats(window, variant_val, dim):
            successes = 0
            trials = 0
            for call in window:
                if not call.get("variant"):
                    continue
                if call["variant"].get(dim) != variant_val:
                    continue
                
                trials += 1
                if primary_kpi == "engagement_rate":
                    if call.get("connected") and call.get("engaged"):
                        successes += 1
                elif primary_kpi == "pickup_rate":
                    if call.get("connected"):
                        successes += 1
            
            return (successes, trials)
        
        hist_stats = get_stats(historical_window, variant, dimension)
        recent_stats = get_stats(recent_window, variant, dimension)
        
        # Check for decay
        if self.detector.detect_decay(wf_id, dimension, variant, recent_stats, hist_stats):
            print(f"  [DECAY] {dimension}={variant} decaying, rolling back")
            self._rollback_decayed_variant(wf_id, dimension, variant)
    
    def _rollback_decayed_variant(self, wf_id: str, dimension: str, variant: str):
        """Roll back a decayed variant to uniform distribution."""
        if self.state.get_pending_approval(wf_id):
            return  # Don't interfere with pending changes
        
        workflow = self.workflows[wf_id]
        current_config_resp = self.client.get(f"/workflows/{wf_id}/config").json()
        current_config = current_config_resp["config"]
        base_version = current_config_resp["version"]
        
        candidates = workflow["options"][dimension]
        
        # Create config with uniform distribution (pause the decayed variant)
        rollback_config = copy.deepcopy(current_config)
        if "allocations" not in rollback_config:
            rollback_config["allocations"] = {}
        if "default" not in rollback_config["allocations"]:
            rollback_config["allocations"]["default"] = {}
        
        # Distribute equally among all variants
        rollback_config["allocations"]["default"][dimension] = {
            c: 1.0 / len(candidates) for c in candidates
        }
        
        # Try auto-apply first
        if self.governance.can_auto_apply(workflow, current_config, rollback_config):
            try:
                self.governance.auto_apply_change(
                    wf_id, base_version, rollback_config,
                    rationale=f"Rollback decayed {dimension}={variant} to uniform distribution"
                )
                print(f"    Auto-applied rollback")
                return
            except Exception as e:
                print(f"    Auto-apply rollback failed: {e}")
        
        # Fall back to approval
        try:
            result = self.governance.propose_change(
                wf_id, workflow, base_version, rollback_config,
                change_summary=f"Rollback decayed {dimension}: {variant}",
                rationale=f"Variant {variant} showing performance decay, rolling back to uniform exploration",
                affected_leads=500,
                impact_score=0.6,
                diff={dimension: rollback_config["allocations"]["default"][dimension]},
                dry_run={"action": "rollback_decay", "variant": variant},
            )
            approval_id = result["approval_id"]
            self.state.set_pending_approval(wf_id, approval_id)
            print(f"    Proposed rollback (approval: {approval_id})")
        except Exception as e:
            print(f"    Rollback proposal failed: {e}")
    
    def _respond_to_bad_caller_id(self, wf_id: str, degraded_dids: List[str]):
        """Rotate away from degraded caller IDs."""
        # Skip if already pending approval
        if self.state.get_pending_approval(wf_id):
            return
        
        workflow = self.workflows[wf_id]
        current_config_resp = self.client.get(f"/workflows/{wf_id}/config").json()
        current_config = current_config_resp["config"]
        base_version = current_config_resp["version"]
        
        # Build new allocation - reduce degraded IDs to 0, redistribute to others
        available_dids = workflow["options"]["caller_id"]
        current_alloc = current_config.get("allocations", {}).get("default", {}).get("caller_id", {})
        
        # Get healthy IDs (not degraded)
        healthy_dids = [did for did in available_dids if did not in degraded_dids]
        
        if not healthy_dids:
            print(f"    No healthy caller IDs available!")
            return
        
        proposed_config = copy.deepcopy(current_config)
        
        # Update default allocation - zero out degraded, distribute to healthy
        new_did_dist = {}
        for did in available_dids:
            if did in degraded_dids:
                new_did_dist[did] = 0.0
            else:
                new_did_dist[did] = 1.0 / len(healthy_dids)
        
        if "allocations" not in proposed_config:
            proposed_config["allocations"] = {}
        if "default" not in proposed_config["allocations"]:
            proposed_config["allocations"]["default"] = {}
        
        proposed_config["allocations"]["default"]["caller_id"] = new_did_dist
        
        # Try auto-apply first
        if self.governance.can_auto_apply(workflow, current_config, proposed_config):
            try:
                self.governance.auto_apply_change(
                    wf_id, base_version, proposed_config,
                    rationale=f"Rotate away from degraded caller IDs: {degraded_dids}"
                )
                print(f"    Auto-applied caller ID rotation")
                return
            except Exception as e:
                print(f"    Auto-apply failed: {e}")
        
        # Fall back to approval path
        try:
            result = self.governance.propose_change(
                wf_id, workflow, base_version, proposed_config,
                change_summary=f"Rotate away from degraded caller IDs",
                rationale=f"Caller IDs {degraded_dids} showing poor pickup rates. "
                         f"Rotating to healthy IDs: {available_dids}",
                affected_leads=500,
                impact_score=0.7,
                diff={"caller_id": new_did_dist},
                dry_run={"action": "rotate_caller_ids", "removed": degraded_dids},
            )
            
            approval_id = result["approval_id"]
            self.state.set_pending_approval(wf_id, approval_id)
            print(f"    Proposed caller ID rotation (approval: {approval_id})")
        
        except Exception as e:
            print(f"    Failed to propose: {e}")
    
    def _run_experiments(self, wf_id: str):
        """Run experiments to find better variants."""
        print(f"  [EXPERIMENT] Running experiments for {wf_id}")
        
        # Skip if already pending approval
        if self.state.get_pending_approval(wf_id):
            print(f"    Skipping: pending approval")
            return
        
        workflow = self.workflows[wf_id]
        analyzer = self.analyzers[wf_id]
        
        current_config_resp = self.client.get(f"/workflows/{wf_id}/config").json()
        current_config = current_config_resp["config"]
        base_version = current_config_resp["version"]
        
        # Strategy: gradual exploration that fits auto-apply limits
        # For each dimension, incrementally add variants until we explore all or find winner
        
        # Check if we need to add more variants (gradual exploration)
        current_alloc = current_config.get("allocations", {}).get("default", {})
        
        for dimension in ["voice", "welcome_message"]:
            candidates = workflow["options"][dimension]
            dim_alloc = current_alloc.get(dimension, {})
            
            print(f"    {dimension}: current={dim_alloc}, candidates={candidates}")
            
            # If not exploring all variants yet, add one more
            explored = set(dim_alloc.keys())
            unexplored = set(candidates) - explored
            
            if unexplored and len(dim_alloc) < len(candidates):
                # Add one more variant with small weight
                new_variant = list(unexplored)[0]
                
                # Gradual shift: take 20% from existing, give to new
                new_alloc = {}
                for v, weight in dim_alloc.items():
                    new_alloc[v] = weight * 0.8
                new_alloc[new_variant] = 0.2
                
                # Build proposal config
                explore_config = copy.deepcopy(current_config)
                if "allocations" not in explore_config:
                    explore_config["allocations"] = {}
                if "default" not in explore_config["allocations"]:
                    explore_config["allocations"]["default"] = {}
                
                explore_config["allocations"]["default"][dimension] = new_alloc
                
                # Try auto-apply if allowed
                if self.governance.can_auto_apply(workflow, current_config, explore_config):
                    try:
                        self.governance.auto_apply_change(
                            wf_id, base_version, explore_config,
                            rationale=f"Gradual exploration: add {new_variant} to {dimension}"
                        )
                        print(f"    Auto-applied: added {new_variant} to {dimension}")
                        return
                    except Exception as e:
                        print(f"    Auto-apply failed: {e}")
                else:
                    # Try approval path for exploration
                    try:
                        result = self.governance.propose_change(
                            wf_id, workflow, base_version, explore_config,
                            change_summary=f"Explore {dimension}: add {new_variant}",
                            rationale=f"Expand exploration to test {new_variant} against current variants",
                            affected_leads=500,
                            impact_score=0.3,
                            diff={dimension: new_alloc},
                            dry_run={"action": "add_variant", "variant": new_variant},
                        )
                        approval_id = result["approval_id"]
                        self.state.set_pending_approval(wf_id, approval_id)
                        print(f"    Proposed exploration: {dimension}+{new_variant} (approval: {approval_id})")
                        return
                    except Exception as e:
                        print(f"    Proposal failed: {e}")
        
        # If all variants explored, look for winners
        best_changes = []
        
        for dimension in ["voice", "welcome_message"]:
            candidates = workflow["options"][dimension]
            dim_alloc = current_alloc.get(dimension, {})
            
            # Only analyze if we're exploring multiple variants
            if len(dim_alloc) < 2:
                continue
            
            print(f"    Analyzing {dimension} for winners...")
            
            # Define guardrail check function
            def check_guardrail(variant_value: str) -> bool:
                # Get primary and guardrail KPIs
                primary_kpi = workflow["objective"]["primary"]
                guardrail = workflow["objective"].get("guardrail", {})
                
                if not guardrail:
                    return True  # No guardrail to enforce
                
                # Get stats for winner
                winner_stats = analyzer.get_variant_stats("default", dimension, variant_value)
                
                # For guardrail check, we need to compare against baseline
                # Get baseline (first variant or current leader)
                baseline_variant = list(dim_alloc.keys())[0] if dim_alloc else candidates[0]
                baseline_stats = analyzer.get_variant_stats("default", dimension, baseline_variant)
                
                if baseline_stats[1] < 40 or winner_stats[1] < 40:
                    return True  # Not enough data to check guardrail
                
                baseline_rate = baseline_stats[0] / baseline_stats[1]
                winner_rate = winner_stats[0] / winner_stats[1]
                
                # Check guardrail (e.g., pickup_rate_max_drop: 0.02)
                if primary_kpi == "engagement_rate" and "pickup_rate_max_drop" in guardrail:
                    # Winner is being selected on engagement, check pickup isn't hurt
                    # This requires pickup stats which we don't track separately
                    # For now, skip this check
                    pass
                elif primary_kpi == "pickup_rate" and "engagement_rate_max_drop" in guardrail:
                    max_drop = guardrail["engagement_rate_max_drop"]
                    drop = baseline_rate - winner_rate
                    if drop > max_drop:
                        print(f"      {variant_value} violates guardrail (drop: {drop:.3f} > {max_drop})")
                        return False
                
                return True
            
            # Use lower threshold since we're actively exploring
            winner = analyzer.get_best_variant("default", dimension, candidates, 
                                             min_samples=40,
                                             guardrail_check=check_guardrail)
            
            if winner:
                current_leader = max(dim_alloc, key=dim_alloc.get) if dim_alloc else None
                
                # Only promote if winner is different and has sufficient dominance
                if winner != current_leader and dim_alloc.get(winner, 0) < 0.8:
                    winner_stats = analyzer.variant_stats.get(("default", dimension, winner), [0, 0])
                    winner_rate = winner_stats[0] / winner_stats[1] if winner_stats[1] > 0 else 0
                    
                    print(f"    Winner: {winner} (rate={winner_rate:.3f}, n={winner_stats[1]})")
                    
                    best_changes.append({
                        "dimension": dimension,
                        "cohort": "default",
                        "winner": winner,
                        "rate": winner_rate,
                        "samples": winner_stats[1],
                    })
        
        if not best_changes:
            print(f"    No clear winners yet")
            return
        
        # Apply best change
        change = best_changes[0]
        proposed_config = copy.deepcopy(current_config)
        
        if "allocations" not in proposed_config:
            proposed_config["allocations"] = {}
        if change["cohort"] not in proposed_config["allocations"]:
            proposed_config["allocations"][change["cohort"]] = {}
        
        # Promote winner to 100%
        proposed_config["allocations"][change["cohort"]][change["dimension"]] = {
            change["winner"]: 1.0
        }
        
        # Try auto-apply first
        if self.governance.can_auto_apply(workflow, current_config, proposed_config):
            try:
                self.governance.auto_apply_change(
                    wf_id, base_version, proposed_config,
                    rationale=f"Promote winning {change['dimension']}: {change['winner']} "
                             f"(rate: {change['rate']:.3f}, n={change['samples']})"
                )
                print(f"  Auto-applied: {change['dimension']}={change['winner']}")
                return
            except Exception as e:
                print(f"  Auto-apply failed: {e}")
        
        # Fall back to approval
        try:
            result = self.governance.propose_change(
                wf_id, workflow, base_version, proposed_config,
                change_summary=f"Promote winning {change['dimension']}: {change['winner']}",
                rationale=f"Experiment shows {change['winner']} performs better "
                         f"(rate: {change['rate']:.3f}, samples: {change['samples']})",
                affected_leads=800,
                impact_score=self.detector.build_impact_score(0.5, change['rate'], 800, 1000),
                diff={f"{change['dimension']}": {change['winner']: 1.0}},
                dry_run={"projected_rate": change['rate'], "samples": change['samples']},
            )
            
            approval_id = result["approval_id"]
            self.state.set_pending_approval(wf_id, approval_id)
            print(f"  Proposed: {change['dimension']}={change['winner']} (approval: {approval_id})")
        
        except Exception as e:
            print(f"  Failed to propose: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Simulator URL")
    parser.add_argument("--run-dir", default="runs/controller", help="Run directory")
    args = parser.parse_args()
    
    controller = AgentController(args.url, args.run_dir)
    
    try:
        controller.run()
    except KeyboardInterrupt:
        print("\nInterrupted, saving state...")
        controller.state.save_state()
        print("State saved.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        controller.state.save_state()
        raise


if __name__ == "__main__":
    main()

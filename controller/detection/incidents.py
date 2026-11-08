"""Incident detection for hallucinations, caller ID issues, and drift."""
from typing import Dict, List, Tuple, Optional, Any
from collections import deque
import httpx


class IncidentDetector:
    """Detects and responds to incidents."""
    
    def __init__(self, api_client: httpx.Client, state_store):
        self.client = api_client
        self.state = state_store
        
        # Detection thresholds - tuned for real incident detection
        self.HALLUC_SPIKE_THRESHOLD = 0.010  # 1% absolute increase triggers
        self.HALLUC_MIN_SAMPLES = 50  # Lower to catch incidents faster
        self.CALLER_ID_DROP_THRESHOLD = 0.20  # 20% relative drop
        self.CALLER_ID_MIN_SAMPLES = 50  # Lower for faster detection
        self.DECAY_THRESHOLD = 0.08  # 8% drop indicates decay
        self.DECAY_MIN_SAMPLES = 100
    
    def check_hallucinations(self, workflow_id: str, 
                           recent_calls: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Detect hallucination spikes using CUSUM with adaptive baseline.
        
        CUSUM accumulates deviations from baseline and triggers when cumulative 
        sum exceeds a threshold. This provides fast detection while being robust
        to noise.
        
        Returns incident data if spike detected, None otherwise.
        """
        # Get all connected calls with QA
        connected_with_qa = [c for c in recent_calls if c.get("connected") and "qa" in c]
        if len(connected_with_qa) < self.HALLUC_MIN_SAMPLES:
            return None
        
        # Build baseline from first 150 calls (or all if fewer)
        baseline_window_size = min(150, len(connected_with_qa) // 2)
        if baseline_window_size < 50:
            baseline_window_size = min(50, len(connected_with_qa))
        
        baseline_window = connected_with_qa[:baseline_window_size]
        baseline_halluc = sum(1 for c in baseline_window if c["qa"].get("hallucination_flag"))
        baseline_rate = baseline_halluc / len(baseline_window)
        
        # CUSUM parameters
        k = 0.005  # Allowance (half the minimum detectable shift)
        h = 4.0    # Threshold for triggering (in units of standard deviations)
        
        # Run CUSUM over recent calls (starting after baseline window)
        cusum = 0.0
        max_cusum = 0.0
        trigger_idx = None
        
        for i in range(baseline_window_size, len(connected_with_qa)):
            call = connected_with_qa[i]
            halluc = 1 if call["qa"].get("hallucination_flag") else 0
            deviation = halluc - baseline_rate - k
            cusum = max(0, cusum + deviation)
            
            if cusum > max_cusum:
                max_cusum = cusum
            
            # Trigger if CUSUM exceeds threshold
            if cusum > h * baseline_rate:
                trigger_idx = i
                break
        
        if trigger_idx is not None:
            # Calculate recent rate for reporting
            recent_window = connected_with_qa[max(0, trigger_idx - 50):trigger_idx + 1]
            recent_halluc = sum(1 for c in recent_window if c["qa"].get("hallucination_flag"))
            recent_rate = recent_halluc / len(recent_window)
            
            return {
                "type": "hallucination_spike",
                "recent_rate": recent_rate,
                "baseline_rate": baseline_rate,
                "increase": recent_rate - baseline_rate,
                "sample_size": len(recent_window),
                "cusum_value": cusum,
                "trigger_call": trigger_idx,
            }
        
        return None
    
    def check_caller_id_health(self, workflow_id: str,
                               caller_id_stats: Dict[str, Tuple[int, int]]) -> List[str]:
        """
        Check for degraded caller IDs by comparing to average of healthy IDs.
        
        Returns list of caller IDs with poor health.
        """
        # Debug logging
        print(f"  [DEBUG] {workflow_id} caller_id_stats: {caller_id_stats}")
        
        if not caller_id_stats:
            return []
        
        # Filter to IDs with enough samples
        viable = {cid: stats for cid, stats in caller_id_stats.items() 
                 if stats[1] >= self.CALLER_ID_MIN_SAMPLES}
        
        print(f"  [DEBUG] Viable caller IDs (n>={self.CALLER_ID_MIN_SAMPLES}): {list(viable.keys())}")
        
        if len(viable) < 2:
            return []
        
        # Calculate rates
        rates = {cid: stats[0] / stats[1] for cid, stats in viable.items()}
        
        # Use median of healthy IDs as baseline (robust to one bad ID)
        sorted_rates = sorted(rates.values())
        median_rate = sorted_rates[len(sorted_rates) // 2]
        
        print(f"  [DEBUG] Median pickup rate: {median_rate:.3f}")
        
        # Flag IDs significantly below median
        degraded = []
        for cid, rate in rates.items():
            if median_rate > 0:
                relative_drop = (median_rate - rate) / median_rate
                print(f"  [DEBUG] {cid}: rate={rate:.3f}, drop={relative_drop:.1%}")
                if relative_drop > self.CALLER_ID_DROP_THRESHOLD:
                    degraded.append(cid)
                    self.state.log_audit("caller_id_degraded", workflow_id, {
                        "caller_id": cid,
                        "pickup_rate": rate,
                        "median_pickup": median_rate,
                        "relative_drop": relative_drop,
                        "dials": viable[cid][1],
                    })
        
        print(f"  [DEBUG] Degraded caller IDs: {degraded}")
        return degraded
    
    def suggest_prompt_fix(self, workflow_id: str, problem: str) -> Optional[List[Dict[str, Any]]]:
        """
        Use LLM to suggest prompt fixes.
        
        Returns list of candidate prompts or None if credits exhausted.
        """
        try:
            resp = self.client.post("/llm/suggest-fixes", json={
                "workflow_id": workflow_id,
                "problem": problem,
            })
            resp.raise_for_status()
            suggestions = resp.json()
            
            self.state.log_audit("llm_suggestions", workflow_id, {
                "problem": problem,
                "suggestions": suggestions,
            })
            
            return suggestions.get("suggestions", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 402:
                self.state.log_audit("llm_no_credits", workflow_id, {
                    "problem": problem,
                })
                return None
            raise
    
    def validate_prompt(self, workflow_id: str, prompt_version: str,
                       n_samples: int = 500) -> Tuple[Optional[float], Optional[str]]:
        """
        Validate a prompt version.
        
        Returns (pass_rate, run_id) or (None, None) if credits exhausted.
        """
        try:
            resp = self.client.post("/validation/runs", json={
                "workflow_id": workflow_id,
                "prompt_version": prompt_version,
                "n": n_samples,
            })
            resp.raise_for_status()
            result = resp.json()
            
            pass_rate = result.get("pass_rate")
            validation_run_id = result.get("validation_run_id")  # Correct field name!
            
            self.state.log_audit("prompt_validated", workflow_id, {
                "prompt_version": prompt_version,
                "pass_rate": pass_rate,
                "validation_run_id": validation_run_id,
                "n_samples": n_samples,
            })
            
            return pass_rate, validation_run_id
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 402:
                self.state.log_audit("validation_no_credits", workflow_id, {
                    "prompt_version": prompt_version,
                })
                return None, None
            raise
    
    def detect_decay(self, workflow_id: str, dimension: str, variant: str,
                    recent_stats: Tuple[int, int],
                    historical_stats: Tuple[int, int]) -> bool:
        """
        Detect if a winning variant has decayed.
        
        Args:
            dimension: "voice" or "welcome_message"
            variant: The variant value (e.g., "V3", "W2")
            recent_stats: (successes, trials) for recent period
            historical_stats: (successes, trials) for historical period
        
        Returns:
            True if decay detected
        """
        if recent_stats[1] < self.DECAY_MIN_SAMPLES or historical_stats[1] < self.DECAY_MIN_SAMPLES:
            return False
        
        recent_rate = recent_stats[0] / recent_stats[1] if recent_stats[1] > 0 else 0
        hist_rate = historical_stats[0] / historical_stats[1] if historical_stats[1] > 0 else 0
        
        drop = hist_rate - recent_rate
        
        if drop > self.DECAY_THRESHOLD:
            self.state.log_audit("decay_detected", workflow_id, {
                "dimension": dimension,
                "variant": variant,
                "recent_rate": recent_rate,
                "historical_rate": hist_rate,
                "drop": drop,
                "recent_samples": recent_stats[1],
                "historical_samples": historical_stats[1],
            })
            return True
        
        return False
    
    def build_impact_score(self, current_rate: float, expected_rate: float,
                          affected_leads: int, total_leads: int) -> float:
        """
        Build honest impact score.
        
        Returns score in [0, 1] where higher = bigger impact.
        """
        if total_leads == 0:
            return 0.0
        
        rate_improvement = max(0, expected_rate - current_rate)
        fraction_affected = affected_leads / total_leads
        
        # Simple linear combination
        score = 0.7 * rate_improvement + 0.3 * fraction_affected
        return min(1.0, score)

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
        Detect hallucination spikes using recent window comparison.
        
        Returns incident data if spike detected, None otherwise.
        """
        # Get all connected calls with QA
        connected_with_qa = [c for c in recent_calls if c.get("connected") and "qa" in c]
        if len(connected_with_qa) < self.HALLUC_MIN_SAMPLES:
            return None
        
        # Take last 100 calls as recent window
        recent_window = connected_with_qa[-100:] if len(connected_with_qa) >= 100 else connected_with_qa[-self.HALLUC_MIN_SAMPLES:]
        
        # Calculate recent hallucination rate
        halluc_count = sum(1 for c in recent_window if c["qa"].get("hallucination_flag"))
        recent_rate = halluc_count / len(recent_window)
        
        # Get historical baseline (from bootstrap or from earlier calls)
        wf_state = self.state.get_workflow_state(workflow_id)
        hist_rate = wf_state.get("baseline_halluc_rate", 0.01)
        
        # Also check against earlier calls in this run if we have enough
        if len(connected_with_qa) > 200:
            earlier_window = connected_with_qa[:100]
            earlier_halluc = sum(1 for c in earlier_window if c["qa"].get("hallucination_flag"))
            earlier_rate = earlier_halluc / len(earlier_window)
            hist_rate = max(hist_rate, earlier_rate)  # Use whichever is higher as baseline
        
        increase = recent_rate - hist_rate
        
        if increase > self.HALLUC_SPIKE_THRESHOLD:
            return {
                "type": "hallucination_spike",
                "recent_rate": recent_rate,
                "historical_rate": hist_rate,
                "increase": increase,
                "sample_size": len(recent_window),
            }
        
        return None
    
    def check_caller_id_health(self, workflow_id: str,
                               caller_id_stats: Dict[str, Tuple[int, int]]) -> List[str]:
        """
        Check for degraded caller IDs by comparing to average of healthy IDs.
        
        Returns list of caller IDs with poor health.
        """
        if not caller_id_stats:
            return []
        
        # Filter to IDs with enough samples
        viable = {cid: stats for cid, stats in caller_id_stats.items() 
                 if stats[1] >= self.CALLER_ID_MIN_SAMPLES}
        
        if len(viable) < 2:
            return []
        
        # Calculate rates
        rates = {cid: stats[0] / stats[1] for cid, stats in viable.items()}
        
        # Use median of healthy IDs as baseline (robust to one bad ID)
        sorted_rates = sorted(rates.values())
        median_rate = sorted_rates[len(sorted_rates) // 2]
        
        # Flag IDs significantly below median
        degraded = []
        for cid, rate in rates.items():
            if median_rate > 0:
                relative_drop = (median_rate - rate) / median_rate
                if relative_drop > self.CALLER_ID_DROP_THRESHOLD:
                    degraded.append(cid)
                    self.state.log_audit("caller_id_degraded", workflow_id, {
                        "caller_id": cid,
                        "pickup_rate": rate,
                        "median_pickup": median_rate,
                        "relative_drop": relative_drop,
                        "dials": viable[cid][1],
                    })
        
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
            run_id = result.get("run_id")
            
            self.state.log_audit("prompt_validated", workflow_id, {
                "prompt_version": prompt_version,
                "pass_rate": pass_rate,
                "run_id": run_id,
                "n_samples": n_samples,
            })
            
            return pass_rate, run_id
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

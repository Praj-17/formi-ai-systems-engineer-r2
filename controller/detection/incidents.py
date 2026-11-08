"""Incident detection for hallucinations, caller ID issues, and drift."""
from typing import Dict, List, Tuple, Optional, Any
from collections import deque
import httpx


class IncidentDetector:
    """Detects and responds to incidents."""
    
    def __init__(self, api_client: httpx.Client, state_store):
        self.client = api_client
        self.state = state_store
        
        # Detection thresholds
        self.HALLUC_SPIKE_THRESHOLD = 0.020  # Less sensitive to avoid false positives
        self.HALLUC_WINDOW_SIZE = 200
        self.CALLER_ID_DROP_THRESHOLD = 0.15  # More lenient
        self.CALLER_ID_MIN_SAMPLES = 150
        self.DRIFT_THRESHOLD = 0.05
        self.DRIFT_WINDOW = 500
    
    def check_hallucinations(self, workflow_id: str, 
                           recent_calls: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Detect hallucination spikes.
        
        Returns incident data if spike detected, None otherwise.
        """
        if len(recent_calls) < 100:
            return None
        
        # Calculate recent hallucination rate
        connected_with_qa = [c for c in recent_calls if c.get("connected") and "qa" in c]
        if len(connected_with_qa) < 50:
            return None
        
        halluc_count = sum(1 for c in connected_with_qa if c["qa"].get("hallucination_flag"))
        recent_rate = halluc_count / len(connected_with_qa)
        
        # Get historical baseline
        wf_state = self.state.get_workflow_state(workflow_id)
        hist_rate = wf_state.get("baseline_halluc_rate", 0.01)
        
        increase = recent_rate - hist_rate
        
        if increase > self.HALLUC_SPIKE_THRESHOLD:
            return {
                "type": "hallucination_spike",
                "recent_rate": recent_rate,
                "historical_rate": hist_rate,
                "increase": increase,
                "sample_size": len(connected_with_qa),
            }
        
        return None
    
    def check_caller_id_health(self, workflow_id: str,
                               caller_id_stats: Dict[str, Tuple[int, int]],
                               global_pickup: float) -> List[str]:
        """
        Check for degraded caller IDs.
        
        Returns list of caller IDs with poor health.
        """
        degraded = []
        
        for caller_id, (connected, dials) in caller_id_stats.items():
            if dials < self.CALLER_ID_MIN_SAMPLES:
                continue
            
            pickup_rate = connected / dials if dials > 0 else 0
            relative_drop = (global_pickup - pickup_rate) / global_pickup if global_pickup > 0 else 0
            
            if relative_drop > self.CALLER_ID_DROP_THRESHOLD:
                degraded.append(caller_id)
                self.state.log_audit("caller_id_degraded", workflow_id, {
                    "caller_id": caller_id,
                    "pickup_rate": pickup_rate,
                    "global_pickup": global_pickup,
                    "relative_drop": relative_drop,
                    "dials": dials,
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
    
    def detect_decay(self, workflow_id: str, variant_key: str,
                    recent_stats: Tuple[int, int],
                    historical_stats: Tuple[int, int]) -> bool:
        """
        Detect if a winning variant has decayed.
        
        Args:
            variant_key: Identifier for the variant
            recent_stats: (successes, trials) for recent period
            historical_stats: (successes, trials) for historical period
        
        Returns:
            True if decay detected
        """
        if recent_stats[1] < 100 or historical_stats[1] < 100:
            return False
        
        recent_rate = recent_stats[0] / recent_stats[1] if recent_stats[1] > 0 else 0
        hist_rate = historical_stats[0] / historical_stats[1] if historical_stats[1] > 0 else 0
        
        drop = hist_rate - recent_rate
        
        if drop > self.DRIFT_THRESHOLD:
            self.state.log_audit("decay_detected", workflow_id, {
                "variant": variant_key,
                "recent_rate": recent_rate,
                "historical_rate": hist_rate,
                "drop": drop,
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

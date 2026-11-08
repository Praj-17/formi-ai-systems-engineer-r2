"""Governance client for managing proposals and approvals."""
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import httpx


class GovernanceClient:
    """Manages the proposal and approval lifecycle."""
    
    def __init__(self, api_client: httpx.Client, state_store):
        self.client = api_client
        self.state = state_store
    
    def can_auto_apply(self, workflow: Dict[str, Any], 
                       current_config: Dict[str, Any],
                       proposed_config: Dict[str, Any]) -> bool:
        """Check if a change can be auto-applied per policy."""
        policy = workflow["governance"]["auto_apply"]
        if not policy["enabled"]:
            return False
        
        # Determine changed dimensions
        changed_dims = self._get_changed_dimensions(current_config, proposed_config)
        
        # Check if all changed dims are allowed
        allowed = set(policy["allowed_dims"])
        if not changed_dims.issubset(allowed):
            return False
        
        # Check shift limits for allocation changes
        max_shift = policy["max_shift"]
        for dim in ["welcome_message", "voice", "caller_id"]:
            if dim not in changed_dims:
                continue
            
            for cohort_id in ["default"] + [c["id"] for c in proposed_config.get("cohorts", [])]:
                old_dist = current_config.get("allocations", {}).get(cohort_id, {}).get(dim, 
                           current_config.get("allocations", {}).get("default", {}).get(dim, {}))
                new_dist = proposed_config.get("allocations", {}).get(cohort_id, {}).get(dim,
                           proposed_config.get("allocations", {}).get("default", {}).get(dim, {}))
                
                if old_dist and new_dist:
                    tvd = self._total_variation_distance(old_dist, new_dist)
                    if tvd > max_shift:
                        return False
        
        return True
    
    def _get_changed_dimensions(self, old: Dict[str, Any], new: Dict[str, Any]) -> set:
        """Identify which dimensions changed."""
        changed = set()
        
        if old.get("prompt_version") != new.get("prompt_version"):
            changed.add("prompt_version")
        
        old_cohorts = str(old.get("cohorts", []))
        new_cohorts = str(new.get("cohorts", []))
        if old_cohorts != new_cohorts:
            changed.add("cohorts")
        
        old_alloc = old.get("allocations", {})
        new_alloc = new.get("allocations", {})
        
        for dim in ["welcome_message", "voice", "caller_id"]:
            if self._allocation_changed(old_alloc, new_alloc, dim):
                changed.add(dim)
        
        old_sched = str(old.get("schedule", {}))
        new_sched = str(new.get("schedule", {}))
        if old_sched != new_sched:
            changed.add("schedule")
        
        return changed
    
    def _allocation_changed(self, old_alloc: Dict, new_alloc: Dict, dim: str) -> bool:
        """Check if allocation changed for a dimension."""
        old_default = old_alloc.get("default", {}).get(dim, {})
        new_default = new_alloc.get("default", {}).get(dim, {})
        if old_default != new_default:
            return True
        
        # Check non-default cohorts
        old_cohorts = set(old_alloc.keys()) - {"default"}
        new_cohorts = set(new_alloc.keys()) - {"default"}
        if old_cohorts != new_cohorts:
            return True
        
        for cohort in old_cohorts:
            old_val = old_alloc.get(cohort, {}).get(dim)
            new_val = new_alloc.get(cohort, {}).get(dim)
            if old_val != new_val:
                return True
        
        return False
    
    def _total_variation_distance(self, dist1: Dict[str, float], 
                                   dist2: Dict[str, float]) -> float:
        """Compute total variation distance between two distributions."""
        all_keys = set(dist1.keys()) | set(dist2.keys())
        
        # Normalize distributions
        sum1 = sum(dist1.values()) or 1
        sum2 = sum(dist2.values()) or 1
        norm1 = {k: dist1.get(k, 0) / sum1 for k in all_keys}
        norm2 = {k: dist2.get(k, 0) / sum2 for k in all_keys}
        
        tvd = 0.5 * sum(abs(norm1[k] - norm2[k]) for k in all_keys)
        return tvd
    
    def propose_change(self, workflow_id: str, workflow: Dict[str, Any],
                      base_version: int, proposed_config: Dict[str, Any],
                      change_summary: str, rationale: str,
                      affected_leads: int, impact_score: float,
                      diff: Dict[str, Any], dry_run: Dict[str, Any],
                      evidence: Optional[Dict[str, Any]] = None,
                      expires_in_hours: Optional[int] = None) -> Dict[str, Any]:
        """Submit a proposal through governance."""
        proposal_id = str(uuid.uuid4())
        
        body = {
            "proposal_id": proposal_id,
            "workflow_id": workflow_id,
            "base_version": base_version,
            "proposed_config": proposed_config,
            "change_summary": change_summary,
            "diff": diff,
            "affected_leads": affected_leads,
            "dry_run": dry_run,
            "impact_score": impact_score,
            "rationale": rationale,
        }
        
        if evidence:
            body["evidence"] = evidence
        
        if expires_in_hours:
            body["expires_in_hours"] = expires_in_hours
        
        try:
            resp = self.client.post("/approvals", json=body)
            resp.raise_for_status()
            result = resp.json()
            
            self.state.log_audit("proposal_submitted", workflow_id, {
                "proposal_id": proposal_id,
                "approval_id": result.get("approval_id"),
                "change_summary": change_summary,
                "base_version": base_version,
            })
            
            return result
        except httpx.HTTPStatusError as e:
            self.state.log_audit("proposal_failed", workflow_id, {
                "proposal_id": proposal_id,
                "error": str(e),
                "status_code": e.response.status_code,
                "response": e.response.text,
            })
            raise
    
    def auto_apply_change(self, workflow_id: str, base_version: int,
                         proposed_config: Dict[str, Any], rationale: str,
                         evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Auto-apply a change within policy."""
        proposal_id = str(uuid.uuid4())
        
        body = {
            "proposal_id": proposal_id,
            "base_version": base_version,
            "proposed_config": proposed_config,
            "rationale": rationale,
        }
        
        if evidence:
            body["evidence"] = evidence
        
        try:
            resp = self.client.put(f"/workflows/{workflow_id}/config", json=body)
            resp.raise_for_status()
            result = resp.json()
            
            self.state.log_audit("auto_applied", workflow_id, {
                "proposal_id": proposal_id,
                "version": result.get("version"),
                "rationale": rationale,
            })
            
            return result
        except httpx.HTTPStatusError as e:
            self.state.log_audit("auto_apply_failed", workflow_id, {
                "proposal_id": proposal_id,
                "error": str(e),
                "status_code": e.response.status_code,
                "response": e.response.text,
            })
            raise
    
    def apply_approval(self, workflow_id: str, approval_id: str) -> Dict[str, Any]:
        """Apply an approved change."""
        try:
            resp = self.client.post(f"/workflows/{workflow_id}/apply", 
                                   json={"approval_id": approval_id})
            resp.raise_for_status()
            result = resp.json()
            
            self.state.log_audit("approval_applied", workflow_id, {
                "approval_id": approval_id,
                "version": result.get("version"),
            })
            
            return result
        except httpx.HTTPStatusError as e:
            self.state.log_audit("apply_failed", workflow_id, {
                "approval_id": approval_id,
                "error": str(e),
                "status_code": e.response.status_code,
            })
            raise
    
    def check_approval_status(self, approval_id: str) -> Dict[str, Any]:
        """Check status of a pending approval."""
        resp = self.client.get(f"/approvals/{approval_id}")
        resp.raise_for_status()
        return resp.json()
    
    def get_pending_approvals(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get pending approvals for a workflow."""
        resp = self.client.get("/approvals", params={
            "workflow_id": workflow_id,
            "status": "pending"
        })
        resp.raise_for_status()
        return resp.json()

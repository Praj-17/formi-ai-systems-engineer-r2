"""Persistent state management for crash recovery."""
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime


class StateStore:
    """Manages persistent state for crash recovery and audit trail."""
    
    def __init__(self, run_dir: str):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        
        self.state_file = self.run_dir / "controller_state.json"
        self.audit_file = self.run_dir / "audit_log.jsonl"
        self.events_file = self.run_dir / "processed_events.jsonl"
        
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load state from disk or initialize new state."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {
            "last_chunk": -1,
            "last_event_id": -1,
            "current_ts": None,
            "workflows": {},
            "pending_approvals": {},
            "experiments": {},
            "config_versions": {},
        }
    
    def save_state(self):
        """Save state to disk atomically."""
        tmp = self.state_file.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self.state, f, indent=2)
        tmp.replace(self.state_file)
    
    def log_audit(self, event_type: str, workflow_id: str, data: Dict[str, Any]):
        """Append to audit log."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "sim_ts": self.state.get("current_ts"),
            "event_type": event_type,
            "workflow_id": workflow_id,
            "data": data,
        }
        with open(self.audit_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def log_event(self, event: Dict[str, Any]):
        """Log processed event."""
        with open(self.events_file, "a") as f:
            f.write(json.dumps(event) + "\n")
    
    def get_last_chunk(self) -> int:
        return self.state["last_chunk"]
    
    def set_last_chunk(self, chunk: int):
        self.state["last_chunk"] = chunk
    
    def get_last_event_id(self) -> int:
        return self.state["last_event_id"]
    
    def set_last_event_id(self, event_id: int):
        self.state["last_event_id"] = event_id
    
    def get_current_ts(self) -> Optional[str]:
        return self.state.get("current_ts")
    
    def set_current_ts(self, ts: str):
        self.state["current_ts"] = ts
    
    def get_workflow_state(self, workflow_id: str) -> Dict[str, Any]:
        """Get or initialize workflow-specific state."""
        if workflow_id not in self.state["workflows"]:
            self.state["workflows"][workflow_id] = {
                "cohort_stats": {},
                "variant_stats": {},
                "caller_id_stats": {},
                "hallucination_count": 0,
                "hallucination_window": [],
                "last_change_ts": None,
                "active_experiment": None,
            }
        return self.state["workflows"][workflow_id]
    
    def get_pending_approval(self, workflow_id: str) -> Optional[str]:
        """Get pending approval ID for workflow."""
        return self.state["pending_approvals"].get(workflow_id)
    
    def set_pending_approval(self, workflow_id: str, approval_id: str):
        """Set pending approval ID."""
        self.state["pending_approvals"][workflow_id] = approval_id
    
    def clear_pending_approval(self, workflow_id: str):
        """Clear pending approval."""
        self.state["pending_approvals"].pop(workflow_id, None)
    
    def query_audit(self, workflow_id: Optional[str] = None, 
                    event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query audit log for debugging/review."""
        if not self.audit_file.exists():
            return []
        
        results = []
        with open(self.audit_file) as f:
            for line in f:
                entry = json.loads(line)
                if workflow_id and entry["workflow_id"] != workflow_id:
                    continue
                if event_type and entry["event_type"] != event_type:
                    continue
                results.append(entry)
        return results

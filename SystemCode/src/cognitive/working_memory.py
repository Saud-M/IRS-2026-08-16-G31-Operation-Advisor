"""Cognitive Working Memory Manager.

Implements short-term working memory holding the active incident state,
synthesizing live telemetry observations, operator natural dialogue,
Bayesian belief rankings, pending diagnostic checks, and A* response plans.
"""

from dataclasses import dataclass, field
import datetime
import uuid
from typing import Dict, Any, List, Optional, Set


@dataclass
class DialogueTurn:
    role: str            # "operator", "advisor", "system"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkingMemoryState:
    incident_id: str
    incident_title: str
    start_time: str
    last_updated: str
    active: bool = True
    telemetry: Dict[str, Any] = field(default_factory=dict)
    confirmed_symptoms: Set[str] = field(default_factory=set)
    hypothesis_beliefs: Dict[str, float] = field(default_factory=dict)
    top_hypothesis: Optional[str] = None
    pending_checks: List[Dict[str, Any]] = field(default_factory=list)
    completed_checks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    active_plan_steps: List[Dict[str, Any]] = field(default_factory=list)
    executed_actions: List[Dict[str, Any]] = field(default_factory=list)
    dialogue: List[DialogueTurn] = field(default_factory=list)
    audit_events: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def active_plan(self) -> List[Dict[str, Any]]:
        return self.active_plan_steps

    @property
    def ranked_hypotheses(self) -> List[Dict[str, Any]]:
        from src.learning.bayesian_network import FAULT_DESCRIPTIONS
        sorted_h = sorted(self.hypothesis_beliefs.items(), key=lambda x: x[1], reverse=True)
        return [
            {
                "hypothesis_id": h_id,
                "description": FAULT_DESCRIPTIONS.get(h_id, h_id),
                "posterior_prob": prob,
            }
            for h_id, prob in sorted_h
        ]


class WorkingMemory:
    """Manages active incident lifecycle and synchronizes reasoning state."""

    def __init__(self, incident_title: str = "Active Production Incident"):
        now_str = datetime.datetime.utcnow().isoformat()
        self.state = WorkingMemoryState(
            incident_id=f"INC-{uuid.uuid4().hex[:8].upper()}",
            incident_title=incident_title,
            start_time=now_str,
            last_updated=now_str,
        )

    def update_telemetry(self, sensor_snapshot: Dict[str, Any]) -> None:
        """Update live telemetry readings and refresh timestamp."""
        self.state.telemetry.update(sensor_snapshot)
        self.state.last_updated = datetime.datetime.utcnow().isoformat()

    def add_symptoms(self, symptoms: List[str]) -> None:
        """Register newly verified operational symptoms."""
        for s in symptoms:
            self.state.confirmed_symptoms.add(s)
        self.state.last_updated = datetime.datetime.utcnow().isoformat()

    def update_hypotheses(self, rankings: List[Dict[str, Any]]) -> None:
        """Record latest posterior beliefs from Bayesian inference."""
        self.state.hypothesis_beliefs = {
            r.get("hypothesis_id", ""): r.get("posterior_prob", 0.0)
            for r in rankings
            if r.get("hypothesis_id")
        }
        if rankings:
            self.state.top_hypothesis = rankings[0].get("hypothesis_id")
        self.state.last_updated = datetime.datetime.utcnow().isoformat()

    def register_pending_checks(self, checks: List[Dict[str, Any]]) -> None:
        """Enqueue physical field checks requested by backward chaining."""
        self.state.pending_checks = checks
    def add_check(
        self,
        check_id: str,
        name: str,
        target_equipment: str,
        instructions: str = "",
        priority: int = 1,
    ) -> None:
        """Enqueue an individual physical check into pending checks."""
        self.state.pending_checks.append({
            "check_id": check_id,
            "name": name,
            "target_equipment": target_equipment,
            "instructions": instructions,
            "priority": priority,
        })
        self.state.last_updated = datetime.datetime.utcnow().isoformat()

    def add_action(self, action: Dict[str, Any]) -> None:
        """Log an executed or planned corrective action."""
        self.state.executed_actions.append(action)
        self.state.last_updated = datetime.datetime.utcnow().isoformat()

    def record_check_feedback(self, check_id: str, positive: bool, notes: str = "") -> None:
        """Record operator confirmation or refutation of a diagnostic check."""
        self.state.completed_checks[check_id] = {
            "positive": positive,
            "notes": notes,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }
        # Remove from pending list
        self.state.pending_checks = [c for c in self.state.pending_checks if c.get("check_id") != check_id]
        self.state.last_updated = datetime.datetime.utcnow().isoformat()

    def set_plan(self, plan_steps: List[Dict[str, Any]]) -> None:
        """Store the current A* response action sequence."""
        self.state.active_plan_steps = plan_steps
        self.state.last_updated = datetime.datetime.utcnow().isoformat()

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Log a turn in the interactive operator chat dialogue."""
        self.state.dialogue.append(
            DialogueTurn(role=role, content=content, metadata=metadata or {})
        )

    def log_audit(self, event_type: str, details: Dict[str, Any]) -> None:
        """Append immutable governance event to incident audit trail."""
        record = {
            "incident_id": self.state.incident_id,
            "event_type": event_type,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "details": details,
        }
        self.state.audit_events.append(record)

    def snapshot(self) -> Dict[str, Any]:
        """Export serialized dictionary representation of the active working memory."""
        s = self.state
        return {
            "incident_id": s.incident_id,
            "incident_title": s.incident_title,
            "start_time": s.start_time,
            "last_updated": s.last_updated,
            "telemetry": dict(s.telemetry),
            "confirmed_symptoms": sorted(list(s.confirmed_symptoms)),
            "hypothesis_beliefs": dict(s.hypothesis_beliefs),
            "top_hypothesis": s.top_hypothesis,
            "pending_checks_count": len(s.pending_checks),
            "completed_checks": dict(s.completed_checks),
            "plan_steps_count": len(s.active_plan_steps),
            "dialogue_turns_count": len(s.dialogue),
            "audit_events_count": len(s.audit_events),
        }

    def reset(self, new_title: str = "New Production Incident") -> None:
        """Reset working memory for a fresh operational shift or incident."""
        now_str = datetime.datetime.utcnow().isoformat()
        self.state = WorkingMemoryState(
            incident_id=f"INC-{uuid.uuid4().hex[:8].upper()}",
            incident_title=new_title,
            start_time=now_str,
            last_updated=now_str,
        )

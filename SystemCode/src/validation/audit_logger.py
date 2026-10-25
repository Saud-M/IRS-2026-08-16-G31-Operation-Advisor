"""Immutable Audit Trail Logger for Industrial Governance and Compliance.

Appends structured, tamper-evident audit records to logs/audit_trail.jsonl.
Compliant with OSHA 1910.119 Process Safety Management (PSM) and IEC 61511.
Features SHA-256 cryptographic chaining for tamper evidence.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class AuditRecord:
    session_id: str
    incident_id: str
    timestamp: str
    telemetry_snapshot: Dict[str, Any]
    active_symptoms: List[str]
    top_hypothesis: Optional[str]
    confidence_pct: float
    recommended_actions: List[str]
    cited_documents: List[str]
    validation_status: str       # "PASSED", "WARNING", "REJECTED"
    validation_issues: List[str]
    operator_feedback: Optional[str] = None  # "ACCEPTED", "REJECTED", "MODIFIED"
    previous_record_hash: str = "GENESIS"
    record_hash: str = ""


class AuditTrailLogger:
    """Manages append-only, tamper-evident logging of all operational recommendations."""

    def __init__(self, log_path: Optional[str] = None):
        if log_path:
            self.log_path = log_path
        else:
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            log_dir = os.path.join(root_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            self.log_path = os.path.join(log_dir, "audit_trail.jsonl")

        self.last_hash = self._get_last_hash()

    def _get_last_hash(self) -> str:
        """Find the hash of the last record in the log file, or GENESIS if empty."""
        if not os.path.exists(self.log_path):
            return "GENESIS"
        last_line = ""
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    last_line = line.strip()
        if not last_line:
            return "GENESIS"
        try:
            data = json.loads(last_line)
            return data.get("record_hash", "GENESIS")
        except json.JSONDecodeError:
            return "GENESIS"

    def _compute_hash(self, record_dict: Dict[str, Any]) -> str:
        """Compute SHA-256 digest of canonical JSON serialization (excluding record_hash)."""
        clean_dict = {k: v for k, v in record_dict.items() if k != "record_hash"}
        canonical_str = json.dumps(clean_dict, sort_keys=True)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def log_session(
        self,
        session_id: str,
        incident_id: str,
        telemetry: Dict[str, Any],
        active_symptoms: List[str],
        top_hypothesis: Optional[str],
        confidence_pct: float,
        recommended_actions: List[str],
        cited_documents: List[str],
        validation_status: str,
        validation_issues: List[str],
        operator_feedback: Optional[str] = None,
    ) -> AuditRecord:
        """Append an audited operational decision event."""
        now_str = datetime.now(timezone.utc).isoformat()

        record = AuditRecord(
            session_id=session_id,
            incident_id=incident_id,
            timestamp=now_str,
            telemetry_snapshot=telemetry,
            active_symptoms=active_symptoms,
            top_hypothesis=top_hypothesis,
            confidence_pct=confidence_pct,
            recommended_actions=recommended_actions,
            cited_documents=cited_documents,
            validation_status=validation_status,
            validation_issues=validation_issues,
            operator_feedback=operator_feedback,
            previous_record_hash=self.last_hash,
        )

        rec_dict = asdict(record)
        rec_hash = self._compute_hash(rec_dict)
        record.record_hash = rec_hash
        rec_dict["record_hash"] = rec_hash

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec_dict) + "\n")

        self.last_hash = rec_hash
        return record

    def verify_chain_integrity(self) -> Tuple[bool, int]:
        """Verify the cryptographic hash chain of the entire audit trail log."""
        if not os.path.exists(self.log_path):
            return True, 0

        prev_hash = "GENESIS"
        count = 0

        with open(self.log_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                data = json.loads(line.strip())
                actual_hash = data.get("record_hash")
                reported_prev = data.get("previous_record_hash")

                if reported_prev != prev_hash:
                    return False, line_no

                computed = self._compute_hash(data)
                if computed != actual_hash:
                    return False, line_no

                prev_hash = actual_hash
                count += 1

        return True, count

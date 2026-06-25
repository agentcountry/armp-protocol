"""
ARMP Audit Logging v0.5.0

Compliance-ready structured event logging for ARMP operations.
Tamper-evident, queryable, and exportable logs.

Features:
  - Structured JSON logging
  - Hash-chained event integrity (tamper-evident)
  - Event severity levels
  - Retention policies
  - Export to SIEM (Splunk, ELK, etc.)
  - SOC 2 / ISO 27001 compliance primitives

Apache 2.0.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger("armp-audit")


# ── Types ────────────────────────────────────────────────

class AuditSeverity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEventType(str, Enum):
    AGENT_START = "agent.start"
    AGENT_STOP = "agent.stop"
    MESSAGE_SEND = "message.send"
    MESSAGE_RECEIVE = "message.receive"
    TASK_CREATE = "task.create"
    TASK_COMPLETE = "task.complete"
    TASK_FAIL = "task.fail"
    CAPABILITY_NEGOTIATE = "capability.negotiate"
    PAYMENT_INITIATE = "payment.initiate"
    PAYMENT_RELEASE = "payment.release"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    PERMISSION_DENIED = "permission.denied"
    RATE_LIMIT_HIT = "ratelimit.hit"


# ── Data Models ──────────────────────────────────────────

@dataclass
class AuditEvent:
    """A single tamper-evident audit log entry."""
    event_id: str = ""
    timestamp: str = ""
    severity: AuditSeverity = AuditSeverity.INFO
    event_type: AuditEventType = AuditEventType.MESSAGE_SEND
    actor_did: str = ""         # Who did it
    target_did: str = ""        # Who/what was affected
    action: str = ""            # What happened
    result: str = "success"     # success, failure, denied
    details: dict = field(default_factory=dict)
    source_ip: str = ""
    session_id: str = ""
    previous_hash: str = ""     # Hash of previous event (chain)
    hash: str = ""              # Hash of this event

    def __post_init__(self):
        if not self.event_id:
            self.event_id = f"audit-{hashlib.sha256(f'{self.actor_did}{self.event_type}{time.time()}'.encode()).hexdigest()[:16]}"
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this event for tamper evidence."""
        payload = json.dumps({
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "severity": self.severity.value,
            "event_type": self.event_type.value,
            "actor_did": self.actor_did,
            "target_did": self.target_did,
            "action": self.action,
            "result": self.result,
            "details": self.details,
            "previous_hash": self.previous_hash,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


# ── Audit Logger ─────────────────────────────────────────

class AuditLogger:
    """
    Structured audit logging with tamper-evident hash chaining.

    Usage:
        auditor = AuditLogger(retention_days=90)
        auditor.log(AuditEventType.TASK_COMPLETE, "agent-alpha", "agent-beta",
                     action="churn analysis completed", result="success")
        auditor.verify_integrity()  # Check entire chain
        auditor.export_to_json("/var/log/armp-audit.json")
    """

    def __init__(self, retention_days: int = 90, max_events: int = 100000):
        self._events: list[AuditEvent] = []
        self._retention_days = retention_days
        self._max_events = max_events
        self._last_hash: str = "genesis-00000000000000000000000000000000"

    def log(self, event_type: AuditEventType, actor_did: str, target_did: str = "",
            action: str = "", result: str = "success",
            severity: AuditSeverity = AuditSeverity.INFO,
            details: dict = None, session_id: str = "") -> AuditEvent:
        """Record an audit event."""
        event = AuditEvent(
            severity=severity,
            event_type=event_type,
            actor_did=actor_did,
            target_did=target_did,
            action=action,
            result=result,
            details=details or {},
            session_id=session_id,
            previous_hash=self._last_hash,
        )
        event.hash = event.compute_hash()

        self._events.append(event)
        self._last_hash = event.hash

        # Enforce max events
        if len(self._events) > self._max_events:
            self._prune_old_events()

        # Log to Python logger
        log_msg = f"[{event.severity.value.upper()}] {event.event_type.value}: {actor_did} → {target_did} — {action} ({result})"
        if severity == AuditSeverity.CRITICAL:
            logger.critical(log_msg)
        elif severity == AuditSeverity.ERROR:
            logger.error(log_msg)
        elif severity == AuditSeverity.WARN:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return event

    # ── Shortcuts ────────────────────────────────────

    def log_auth(self, actor_did: str, action: str, result: str = "success", **kwargs):
        """Shorthand for auth events."""
        return self.log(AuditEventType.AUTH_LOGIN if "login" in action else AuditEventType.AUTH_LOGOUT,
                         actor_did, action=action, result=result, **kwargs)

    def log_task(self, event_type: AuditEventType, actor_did: str, task_id: str,
                  assignee: str = "", result: str = "success"):
        """Shorthand for task events."""
        return self.log(event_type, actor_did, assignee,
                         action=f"Task {task_id}", result=result,
                         details={"task_id": task_id})

    def log_payment(self, actor_did: str, payee_did: str, amount: float,
                     currency: str, tx_hash: str = ""):
        """Shorthand for payment events."""
        return self.log(AuditEventType.PAYMENT_INITIATE, actor_did, payee_did,
                         action=f"Payment of {amount} {currency}",
                         details={"amount": amount, "currency": currency, "tx_hash": tx_hash})

    def log_denied(self, actor_did: str, resource: str, reason: str = ""):
        """Log a denied access attempt."""
        return self.log(AuditEventType.PERMISSION_DENIED, actor_did, target_did=resource,
                         action="Access denied", result="denied",
                         severity=AuditSeverity.WARN, details={"reason": reason})

    # ── Integrity ────────────────────────────────────

    def verify_integrity(self) -> dict:
        """Verify the entire audit log hash chain. Returns verification report."""
        errors = []
        expected_hash = "genesis-00000000000000000000000000000000"

        for i, event in enumerate(self._events):
            if event.previous_hash != expected_hash:
                errors.append({
                    "index": i,
                    "event_id": event.event_id,
                    "expected_previous": expected_hash,
                    "actual_previous": event.previous_hash,
                })

            # Verify event hash
            computed = event.compute_hash()
            if computed != event.hash:
                errors.append({
                    "index": i,
                    "event_id": event.event_id,
                    "expected_hash": computed,
                    "stored_hash": event.hash,
                })

            expected_hash = event.hash

        return {
            "total_events": len(self._events),
            "integrity": "valid" if not errors else "COMPROMISED",
            "errors": errors,
            "last_hash": self._last_hash,
        }

    # ── Query ────────────────────────────────────────

    def query(self, actor_did: str = "", event_type: AuditEventType = None,
              min_severity: AuditSeverity = AuditSeverity.DEBUG,
              result: str = "", limit: int = 100) -> list[AuditEvent]:
        """Query audit events with filters."""
        results = []
        sev_rank = {AuditSeverity.DEBUG: 0, AuditSeverity.INFO: 1, AuditSeverity.WARN: 2,
                     AuditSeverity.ERROR: 3, AuditSeverity.CRITICAL: 4}

        for event in reversed(self._events):
            if actor_did and event.actor_did != actor_did:
                continue
            if event_type and event.event_type != event_type:
                continue
            if sev_rank.get(event.severity, 0) < sev_rank.get(min_severity, 0):
                continue
            if result and event.result != result:
                continue
            results.append(event)
            if len(results) >= limit:
                break

        return results

    def get_agent_activity(self, agent_did: str, limit: int = 50) -> list[dict]:
        """Get activity summary for a specific agent."""
        events = self.query(actor_did=agent_did, limit=limit)
        return [
            {
                "timestamp": e.timestamp,
                "event_type": e.event_type.value,
                "action": e.action,
                "result": e.result,
                "severity": e.severity.value,
            }
            for e in events
        ]

    def stats(self) -> dict:
        """Get audit log statistics."""
        if not self._events:
            return {"total": 0}

        severity_counts = {}
        type_counts = {}
        result_counts = {}

        for event in self._events:
            sev = event.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            etype = event.event_type.value
            type_counts[etype] = type_counts.get(etype, 0) + 1
            res = event.result
            result_counts[res] = result_counts.get(res, 0) + 1

        return {
            "total": len(self._events),
            "first_event": self._events[0].timestamp,
            "last_event": self._events[-1].timestamp,
            "by_severity": severity_counts,
            "by_type": type_counts,
            "by_result": result_counts,
            "integrity": "valid" if not self.verify_integrity()["errors"] else "COMPROMISED",
        }

    # ── Export ───────────────────────────────────────

    def export_to_json(self, path: str):
        """Export audit log to a JSON file."""
        events_data = [
            {
                "event_id": e.event_id,
                "timestamp": e.timestamp,
                "severity": e.severity.value,
                "event_type": e.event_type.value,
                "actor_did": e.actor_did,
                "target_did": e.target_did,
                "action": e.action,
                "result": e.result,
                "details": e.details,
                "hash": e.hash,
                "previous_hash": e.previous_hash,
            }
            for e in self._events
        ]
        with open(path, "w") as f:
            json.dump({"events": events_data, "last_hash": self._last_hash}, f, indent=2)
        logger.info(f"Audit log exported to {path}: {len(events_data)} events")

    def export_to_siem_format(self) -> str:
        """Export in CEF (Common Event Format) for SIEM ingestion."""
        lines = []
        for e in self._events[-1000:]:  # Last 1000
            lines.append(
                f"CEF:0|ARMP|AgentProtocol|0.5.0|{e.event_type.value}|{e.action}|"
                f"{e.severity.value}|src={e.actor_did} dst={e.target_did} "
                f"outcome={e.result} msg={e.action}"
            )
        return "\n".join(lines)

    # ── Maintenance ──────────────────────────────────

    def _prune_old_events(self):
        """Remove events beyond retention period."""
        if not self._retention_days:
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        cutoff_str = cutoff.isoformat()
        self._events = [e for e in self._events if e.timestamp >= cutoff_str]
        logger.info(f"Pruned {len(self._events)} events (retention: {self._retention_days}d)")


# ── Demo ────────────────────────────────────────────

def demo():
    print("🚀 ARMP Audit Logging v0.5.0 — Demo\n")

    auditor = AuditLogger(retention_days=90)

    # Simulate activity
    auditor.log_auth("agent-alpha", "login", result="success")
    auditor.log_task(AuditEventType.TASK_CREATE, "agent-alpha", "task-001", assignee="agent-beta")
    auditor.log_task(AuditEventType.TASK_COMPLETE, "agent-beta", "task-001", assignee="agent-alpha")
    auditor.log_payment("agent-alpha", "agent-beta", 5.0, "USDC", "solana-tx-abc123")
    auditor.log(
        AuditEventType.CAPABILITY_NEGOTIATE, "agent-alpha", "agent-beta",
        action="Capability negotiation", result="success",
        details={"mutual": ["data-analysis"]},
    )
    auditor.log_denied("agent-gamma", "task-001", "Insufficient permissions")
    auditor.log(AuditEventType.RATE_LIMIT_HIT, "agent-delta",
                 severity=AuditSeverity.WARN, action="Rate limit exceeded")

    # Query
    print("── Agent Alpha Activity ──")
    for entry in auditor.get_agent_activity("agent-alpha", limit=5):
        print(f"  [{entry['timestamp'][:19]}] {entry['event_type']}: {entry['action']} ({entry['result']})")

    # Stats
    stats = auditor.stats()
    print(f"\n── Audit Stats ──")
    print(f"  Total: {stats['total']}")
    print(f"  By type: {stats['by_type']}")
    print(f"  By result: {stats['by_result']}")

    # Integrity
    verification = auditor.verify_integrity()
    print(f"\n── Chain Integrity ──")
    print(f"  Status: {verification['integrity'].upper()}")
    print(f"  Last hash: {verification['last_hash'][:32]}...")

    # SIEM export
    siem = auditor.export_to_siem_format()
    print(f"\n── SIEM Export (last 3) ──")
    for line in siem.split("\n")[-3:]:
        print(f"  {line[:120]}...")

    print("\n── Audit Demo Complete ──\n")


if __name__ == "__main__":
    demo()

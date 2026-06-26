# ARMP Audit Logging Specification v1.0.0

**Part of ARMP (Agent Real-time Message Protocol)**
**Status:** Draft
**Date:** June 2026
**License:** Apache 2.0

---

## 1. Overview

ARMP Audit Logging provides compliance-ready structured event logging with tamper-evident integrity protection.

### 1.1 Features

- Structured JSON logging with severity levels
- SHA-256 hash-chained event integrity (tamper-evident)
- Configurable retention policies
- Export to SIEM (Splunk, ELK, etc.)
- SOC 2 / ISO 27001 compliance primitives

---

## 2. Event Types

| Category | Events |
|----------|--------|
| **Agent Lifecycle** | `agent.start`, `agent.stop`, `agent.register`, `agent.deregister` |
| **Messaging** | `message.send`, `message.receive` |
| **Task** | `task.create`, `task.assign`, `task.complete`, `task.fail`, `task.cancel` |
| **Capability** | `capability.negotiate`, `capability.register` |
| **Payment** | `payment.initiate`, `payment.release`, `payment.refund` |
| **Trust** | `credential.issue`, `credential.verify`, `credential.revoke` |
| **Auth** | `auth.login`, `auth.logout`, `auth.token_refresh`, `auth.failed` |
| **Admin** | `admin.config_change`, `admin.agent_ban`, `admin.room_delete` |

### 2.1 Severity Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Development diagnostics |
| `INFO` | Normal operations |
| `WARN` | Anomalous but non-critical events |
| `ERROR` | Operational failures |
| `CRITICAL` | Security incidents, payment failures |

---

## 3. Event Format

```json
{
  "event_id": "uuid",
  "event_type": "task.complete",
  "severity": "info",
  "timestamp": "2026-07-01T14:30:00Z",
  "agent_did": "AGNT8A...",
  "room_id": "!room:armp-group.org",
  "data": {
    "task_id": "uuid",
    "assignee_did": "AGNT2F...",
    "duration_seconds": 42.3
  },
  "hash": "SHA-256(previous_event_hash + current_event_data)",
  "previous_hash": "SHA-256 of previous event"
}
```

---

## 4. Hash Chain Integrity

Each event includes a hash of the concatenation of the previous event's hash and its own data:

```
Event N: hash = SHA-256(Event_{N-1}.hash + Event_N.data)
```

This creates an append-only, tamper-evident chain. Any modification to historical events breaks the hash chain and is detectable.

### 4.1 Verification

```
for each event in log:
    computed = SHA-256(previous_hash + event.data)
    if computed != event.hash:
        raise TamperDetected(event.event_id)
    previous_hash = event.hash
```

---

## 5. Retention & Export

### 5.1 Retention Policy

| Severity | Default Retention |
|----------|:--:|
| DEBUG | 7 days |
| INFO | 90 days |
| WARN | 1 year |
| ERROR | 1 year |
| CRITICAL | 7 years |

### 5.2 Export Formats

- **JSON** — Machine-readable, full fidelity
- **CEF** (Common Event Format) — SIEM-compatible
- **CSV** — Spreadsheet analysis

---

## 6. Reference Implementation

Python: `armp_audit.py` — 381 lines
- `AuditSeverity` enum: DEBUG → INFO → WARN → ERROR → CRITICAL
- `AuditEvent` dataclass with hash chain integrity
- `AuditLogger` class with retention management
- Export functions for JSON, CEF, and CSV

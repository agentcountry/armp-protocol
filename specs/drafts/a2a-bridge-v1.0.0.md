# ARMP ↔ A2A Bridge Specification v1.0.0

**Part of ARMP (Agent Real-time Message Protocol)**
**Status:** Draft
**Date:** June 2026
**License:** Apache 2.0

---

## 1. Overview

The ARMP ↔ A2A Bridge enables bidirectional protocol translation between ARMP's Matrix-based real-time agent communication and Google's A2A JSON-RPC task delegation protocol.

### 1.1 Why Bridge?

| Scenario | Protocol |
|----------|----------|
| ARMP agent delegates task to non-ARMP agent | ARMP → A2A |
| A2A agent sends task to ARMP agent | A2A → ARMP |
| Two ARMP agents communicate directly | ARMP only (no bridge needed) |

### 1.2 Architecture

```
┌──────────────┐     HTTP/JSON-RPC     ┌──────────────┐     Matrix     ┌──────────────┐
│  A2A Client  │ ←──────────────────→ │  A2A Bridge  │ ←───────────→ │  ARMP Agent  │
└──────────────┘                       └──────────────┘               └──────────────┘
```

---

## 2. Protocol Translation

### 2.1 Task Status Mapping

| ARMP Status | A2A Status |
|-------------|------------|
| `CREATED` | `input-required` |
| `ASSIGNED` | `input-required` |
| `IN_PROGRESS` | `working` |
| `COMPLETED` | `completed` |
| `FAILED` | `failed` |
| `CANCELLED` | `canceled` |

### 2.2 Message Translation

**A2A → ARMP (incoming task):**

```
A2A: POST /tasks/send { "id": "...", "sessionId": "...", "message": {...} }
  ↓
ARMP: m.agent.task { task_id, status: "CREATED", spec: {...} }
```

**ARMP → A2A (outgoing task):**

```
ARMP: m.agent.task { task_id, status: "COMPLETED", result: {...} }
  ↓
A2A: POST /tasks/send { "id": task_id, "status": "completed", "artifacts": [...] }
```

---

## 3. A2A Endpoints

The bridge exposes standard A2A endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tasks/send` | Send a new task |
| `GET` | `/tasks/get` | Query task status |
| `POST` | `/tasks/cancel` | Cancel a pending task |
| `GET` | `/tasks/{id}/stream` | SSE streaming for task progress |

### 3.1 SSE Streaming

Task progress is streamed via Server-Sent Events:

```
GET /tasks/{id}/stream
Accept: text/event-stream

event: status
data: {"status": "working", "progress": 0.5}

event: heartbeat
data: :

event: status
data: {"status": "completed", "progress": 1.0}
```

Heartbeat comments (30-second interval) keep connections alive through proxies.

---

## 4. Agent Card Translation

### 4.1 ARMP Card → A2A Agent Card

ARMP Agent Cards are translated to A2A-compatible JSON:

```json
{
  "name": "DataAnalyzer",
  "description": "Statistical analysis agent",
  "url": "https://armp-group.org/.well-known/agent-card.json",
  "capabilities": {
    "streaming": true,
    "pushNotifications": false
  },
  "skills": [
    { "id": "data-analysis", "name": "Data Analysis" },
    { "id": "visualization", "name": "Visualization" }
  ]
}
```

---

## 5. Reference Implementation

Python: `armp_a2a_bridge.py` — 551 lines
- `A2ATask` dataclass with full A2A spec v0.3.0 compatibility
- Bidirectional status mapping (ARMP ↔ A2A)
- SSE streaming handler with heartbeat keep-alive
- Agent Card format translation
- `aiohttp` web server with JSON-RPC endpoint support

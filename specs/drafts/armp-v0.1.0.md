# ARMP Specification v0.1.0

**Agent Real-time Message Protocol**
**Status:** Draft
**Date:** June 2026
**License:** Apache 2.0

---

## 1. Introduction

### 1.1 What is ARMP?

ARMP (Agent Real-time Message Protocol) is an open standard for persistent, real-time communication between AI agents. It enables agents to chat, collaborate, form teams, share files, and maintain ongoing relationships — not just exchange one-shot task requests.

ARMP extends the [Matrix](https://matrix.org) protocol with agent-specific capabilities while preserving full Matrix compatibility.

### 1.2 Why ARMP?

Existing agent protocols solve specific problems well:

| Protocol | Strength | Limitation |
|----------|----------|------------|
| **MCP** | Agent-to-tool connection | No agent-to-agent communication |
| **A2A** | Task delegation between agents | Request-response only. No persistent chat, no presence, no groups |
| **ACP** | Agent discovery and invocation | REST-based. No real-time messaging |

**ARMP fills the gap:** persistent, real-time, multi-party agent communication with presence, history, groups, and file sharing. Built on Matrix's proven infrastructure.

### 1.3 Design Principles

1. **Extend, don't replace.** ARMP is a set of Matrix extensions. Any Matrix client can participate at a basic level.
2. **Federated by default.** Agents on different servers communicate seamlessly via Matrix federation.
3. **Identity-first.** Every ARMP agent has a verifiable identity via DID binding.
4. **Security built-in.** Matrix's E2E encryption (Olm/Megolm) protects all ARMP messages.
5. **Progressive enhancement.** Agents start with basic messaging and opt into advanced features.

---

## 2. Architecture

### 2.1 Protocol Stack

```
┌──────────────────────────────────────┐
│          ARMP Extensions             │
│                                      │
│  Agent Card  │  Capability Discovery │
│  DID Binding │  Task Lifecycle       │
│  A2A Bridge  │  Compute Sharing      │
├──────────────────────────────────────┤
│          Matrix Protocol             │
│                                      │
│  Messaging │ Rooms │ Presence │ Files│
│  E2EE      │ Federation │ Push       │
├──────────────────────────────────────┤
│       Matrix Homeserver              │
│  (Synapse / Dendrite / Conduit)      │
└──────────────────────────────────────┘
```

### 2.2 Message Flow

```
Agent A                    Homeserver                   Agent B
   │                           │                           │
   │ PUT /_matrix/client/v3/   │                           │
   │   rooms/!room/m.agent.msg │                           │
   │──────────────────────────→│                           │
   │                           │ Federation (if remote)     │
   │                           │──────────────────────────→│
   │                           │                           │
   │                           │      /sync response        │
   │                           │←──────────────────────────│
   │   /sync response          │                           │
   │←──────────────────────────│                           │
```

### 2.3 Key Concepts

| Concept | Description |
|---------|------------|
| **Agent** | An AI agent registered with a DID and connected to a Matrix homeserver |
| **Homeserver** | A Matrix server that stores messages and relays them between agents |
| **Room** | A persistent conversation space. Can be 1:1 or group. |
| **Agent Card** | A JSON-LD document describing an agent's identity and capabilities |
| **DID** | Decentralized Identifier binding the agent's Matrix account to a verifiable identity |

---

## 3. Agent Identity

### 3.1 DID Binding

Every ARMP agent MUST bind a DID to its Matrix account. The binding is stored as Matrix account data:

```
PUT /_matrix/client/v3/user/{userId}/account_data/m.agent.did
```

```json
{
  "did": "AGNT8A2026070114K7P2M9X4R6",
  "did_document_url": "https://ourdid.com/agent/AGNT8A2026070114K7P2M9X4R6",
  "verified": true,
  "bound_at": "2026-07-01T14:30:00Z"
}
```

### 3.2 DID Resolution

Other agents resolve a DID by fetching the DID document:

```
GET https://ourdid.com/api/v1/did/{did}
```

The DID document contains:
- Agent name and description
- Capability tags
- Public keys for message verification
- Service endpoints (Matrix ID, API endpoints)

---

## 4. Agent Card

### 4.1 Format

An Agent Card is a JSON-LD document hosted at a well-known URL:

```
GET https://{agent-domain}/.well-known/agent-card.json
```

### 4.2 Schema

```json
{
  "@context": "https://armp-protocol.org/specs/agent-card-v0.1.jsonld",
  "type": "AgentCard",
  "did": "AGNT8A2026070114K7P2M9X4R6",
  "name": "DataAnalyzer",
  "description": "Specialized in statistical analysis and visualization",
  "matrix_id": "@dataanalyzer:armp-group.org",
  "capabilities": [
    "data-analysis",
    "visualization",
    "statistical-modeling"
  ],
  "languages": ["python", "r", "sql"],
  "availability": {
    "status": "online",
    "typical_hours": "24/7"
  },
  "endpoints": {
    "api": "https://api.myagent.com/v1",
    "a2a": "https://api.myagent.com/a2a"
  },
  "owner": {
    "name": "Agent Country",
    "contact": "hello@agentcountry.dev"
  },
  "version": "0.1.0"
}
```

### 4.3 Discovery

Agents discover each other's cards through:
1. **Matrix room directory** — rooms can be tagged with capability topics
2. **OurDID registry** — `/api/v1/agents?capability=data-analysis`
3. **Well-known URL** — `https://{domain}/.well-known/agent-card.json`

---

## 5. Messaging

### 5.1 Message Type

ARMP messages use the Matrix custom event type `m.agent.message`:

```json
{
  "type": "m.agent.message",
  "content": {
    "body": "Can you analyze this dataset?",
    "msgtype": "m.text",
    "m.agent": {
      "version": "0.1.0",
      "message_id": "550e8400-e29b-41d4-a716-446655440000",
      "sender_did": "AGNT8A2026070114K7P2M9X4R6",
      "capabilities_requested": ["data-analysis"],
      "task_id": null,
      "priority": "normal",
      "ttl_seconds": 3600
    }
  }
}
```

### 5.2 Message Types

| `msgtype` | Description |
|-----------|-------------|
| `m.text` | Plain text message |
| `m.notice` | System notification |
| `m.agent.task` | Task assignment (see §7) |
| `m.agent.capability_request` | Capability negotiation (see §6) |
| `m.file` | File transfer via Matrix content repository |

### 5.3 Message Lifecycle

```
Sender creates message
    → Homeserver validates and stores
    → Homeserver pushes to room members
    → Recipient receives via /sync
    → Read receipt sent (optional)
    → Message persists in room history
```

---

## 6. Capability Negotiation

### 6.1 Capability Request

An agent requests capabilities from another agent:

```json
{
  "type": "m.agent.capability_request",
  "content": {
    "body": "What capabilities do you have?",
    "m.agent": {
      "request_id": "uuid",
      "sender_did": "AGNT8A...",
      "required_capabilities": ["image-generation"],
      "preferred_capabilities": ["style-transfer"]
    }
  }
}
```

### 6.2 Capability Response

```json
{
  "type": "m.agent.capability_response",
  "content": {
    "body": "I can generate images and apply style transfers.",
    "m.agent": {
      "request_id": "uuid",
      "sender_did": "AGNT8B...",
      "available_capabilities": [
        {
          "name": "image-generation",
          "models": ["stable-diffusion-xl"],
          "max_resolution": "1024x1024",
          "estimated_time_seconds": 5
        }
      ],
      "unavailable_capabilities": []
    }
  }
}
```

---

## 7. Task Lifecycle

### 7.1 States

```
CREATED → ASSIGNED → IN_PROGRESS → COMPLETED
                                 → FAILED
                                 → CANCELLED
```

### 7.2 Task Message

```json
{
  "type": "m.agent.task",
  "content": {
    "body": "Generate a hero image for our blog post",
    "m.agent": {
      "task_id": "uuid",
      "status": "CREATED",
      "sender_did": "AGNT8A...",
      "assignee_did": "AGNT8B...",
      "spec": {
        "type": "image-generation",
        "parameters": {
          "prompt": "A futuristic city skyline at sunset",
          "width": 1920,
          "height": 1080
        }
      },
      "deadline": "2026-07-02T00:00:00Z"
    }
  }
}
```

### 7.3 Task Updates

Task status changes are sent as edits to the original task message:

```json
{
  "type": "m.agent.task",
  "content": {
    "m.agent": {
      "task_id": "uuid",
      "status": "COMPLETED",
      "result": {
        "file_url": "mxc://armp-group.org/abc123",
        "metadata": {
          "model": "stable-diffusion-xl",
          "generation_time_seconds": 4.2
        }
      }
    },
    "m.relates_to": {
      "event_id": "$original_task_event_id",
      "rel_type": "m.replace"
    }
  }
}
```

---

## 8. Rooms & Groups

### 8.1 Room Types

| Type | Description |
|------|------------|
| **Direct** | 1:1 conversation between two agents |
| **Team** | Multi-agent collaboration space |
| **Public** | Open room discoverable via directory |

### 8.2 Room Metadata

ARMP rooms include agent-specific metadata:

```json
{
  "type": "m.room.create",
  "content": {
    "creator": "@dataanalyzer:armp-group.org",
    "m.agent": {
      "room_type": "team",
      "purpose": "Q3 marketing campaign assets",
      "required_capabilities": ["image-generation", "copywriting"],
      "max_members": 10
    }
  }
}
```

### 8.3 Room Discovery

Rooms are discoverable via Matrix room directory with ARMP-specific filters:

```
GET /_matrix/client/v3/publicRooms?filter={"generic_search_term":"image-generation"}
```

---

## 9. Security

### 9.1 End-to-End Encryption

All direct messages and private rooms MUST use Matrix E2E encryption (Olm/Megolm). Public rooms MAY be unencrypted.

### 9.2 Message Signing

Agent messages MAY include an Ed25519 signature in `m.agent.signature`. The public key is retrieved from the DID document.

### 9.3 Authentication

Agents authenticate to their homeserver using Matrix access tokens. The token is obtained during initial login:

```
POST /_matrix/client/v3/login
{
  "type": "m.login.password",
  "identifier": {"type": "m.id.user", "user": "dataanalyzer"},
  "password": "***"
}
```

### 9.4 Authorization

Homeservers SHOULD implement:
- Rate limiting per agent
- Room membership controls
- Capability-based access to agent-specific endpoints

---

## 10. Federation

### 10.1 Cross-Server Communication

ARMP inherits Matrix federation. Agents on different homeservers communicate transparently:

```
Agent A on homeserver-1.com  →  homeserver-2.com  →  Agent B
         │                            │
         └── Matrix Server-Server API ──┘
              (port 8448, TLS)
```

### 10.2 Federation Requirements

Each homeserver MUST:
- Expose Matrix Server-Server API on port 8448
- Have a valid TLS certificate
- Publish a `.well-known/matrix/server` file

---

## 11. Transport Binding

### 11.1 Matrix Client-Server API

ARMP agents use the standard Matrix Client-Server API:

```
Base URL: https://{homeserver}/_matrix/client/v3/
```

Key endpoints:
- `POST /login` — Authenticate
- `GET /sync` — Receive messages
- `PUT /rooms/{roomId}/send/{eventType}/{txnId}` — Send messages
- `POST /createRoom` — Create a room
- `POST /join/{roomId}` — Join a room
- `GET /publicRooms` — Discover rooms

### 11.2 WebSocket (Future)

A future version of ARMP MAY define a native WebSocket transport for agents that do not need full Matrix compatibility.

---

## 12. Compliance

### 12.1 Minimum Viable Agent

An ARMP-compliant agent MUST:
1. Have a DID bound to its Matrix account
2. Publish an Agent Card at `.well-known/agent-card.json`
3. Send and receive `m.agent.message` events
4. Respond to `m.agent.capability_request` events

### 12.2 Full Compliance

A fully ARMP-compliant agent SHOULD also:
1. Support E2E encryption
2. Support task lifecycle (`m.agent.task`)
3. Participate in capability discovery
4. Support file transfer

---

## Appendix A: Relationship to Other Protocols

| Protocol | Relationship |
|----------|-------------|
| **Matrix** | ARMP extends Matrix. All Matrix features are available to ARMP agents. |
| **A2A** | Complementary. ARMP agents MAY bridge to A2A for task delegation to non-ARMP agents. |
| **MCP** | Orthogonal. ARMP agents MAY use MCP to access tools. |
| **OurDID** | DID provider. ARMP agents use OurDID (or any DID method) for identity. |

## Appendix B: References

- [Matrix Specification](https://spec.matrix.org/)
- [Matrix Client-Server API](https://spec.matrix.org/v1.13/client-server-api/)
- [Matrix Federation API](https://spec.matrix.org/v1.13/server-server-api/)
- [W3C DID Core](https://www.w3.org/TR/did-core/)
- [A2A Protocol](https://a2a-protocol.org/)
- [MCP Specification](https://modelcontextprotocol.io/)

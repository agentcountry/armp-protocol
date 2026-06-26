# ARMP Specification v1.0.0

**Agent Real-time Message Protocol**
**Status:** Draft
**Date:** June 2026
**License:** Apache 2.0

---

## 1. Introduction

### 1.1 What is ARMP?

ARMP (Agent Real-time Message Protocol) is an open standard for persistent, real-time communication between AI agents. It enables agents to chat, collaborate, form teams, share files, negotiate capabilities, delegate tasks, establish trust, and transact — all within a federated, end-to-end encrypted network.

ARMP extends the [Matrix](https://matrix.org) protocol with agent-specific capabilities while preserving full Matrix compatibility.

### 1.2 Why ARMP?

Existing agent protocols solve specific problems well:

| Protocol | Strength | Limitation |
|----------|----------|------------|
| **MCP** | Agent-to-tool connection | No agent-to-agent communication |
| **A2A** | Task delegation between agents | Request-response only. No persistent chat, no presence, no groups |
| **ACP** | Agent discovery and invocation | REST-based. No real-time messaging |

**ARMP fills the gap:** persistent, real-time, multi-party agent communication with presence, history, groups, capability negotiation, task lifecycle, smart routing, trust, reputation, payments, SSO, and audit. Built on Matrix's proven infrastructure.

### 1.3 Design Principles

1. **Extend, don't replace.** ARMP is a set of Matrix extensions. Any Matrix client can participate at a basic level.
2. **Federated by default.** Agents on different servers communicate seamlessly via Matrix federation.
3. **Identity-first.** Every ARMP agent has a verifiable identity via DID binding.
4. **Security built-in.** Matrix's E2E encryption (Olm/Megolm) protects all ARMP messages.
5. **Progressive enhancement.** Agents start with basic messaging and opt into advanced features.
6. **Open standard.** Apache 2.0. RFC-style specification with multiple independent implementations.

---

## 2. Architecture

### 2.1 Protocol Stack

```
┌──────────────────────────────────────────────────────┐
│                 ARMP Extensions                       │
│                                                      │
│  Agent Card  │  DID Binding   │  Task Lifecycle      │
│  Capability  │  Smart Routing │  Agent Discovery     │
│  A2A Bridge  │  MCP Bridge    │  Federation (multi)  │
│  Trust       │  Reputation    │  Payments            │
│  SSO/OIDC    │  Audit         │  Rate Limiting       │
├──────────────────────────────────────────────────────┤
│                 Matrix Protocol                      │
│                                                      │
│  Messaging │ Rooms │ Presence │ Files │ E2EE         │
│  Federation │ Push │ Typing │ Receipts              │
├──────────────────────────────────────────────────────┤
│              Matrix Homeserver                       │
│  (Synapse / Dendrite / Conduit)                      │
└──────────────────────────────────────────────────────┘
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
| **Agent Card** | A JSON-LD document describing an agent's identity, capabilities, and trust profile |
| **DID** | Decentralized Identifier binding the agent's Matrix account to a verifiable identity |
| **Task** | A unit of work delegated between agents with full lifecycle tracking |
| **Credential** | A W3C Verifiable Credential attesting to an agent's capabilities or trustworthiness |

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

### 3.3 Trust Levels

| Level | Description | Verification |
|-------|-------------|:--:|
| **None** | No DID bound | — |
| **Claimed** | DID stored in account data | Self-asserted |
| **Verified** | Bidirectional proof (Matrix ↔ DID) | ✅ |
| **Attested** | Third-party attestation of identity | ✅ + VC |

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
  "@context": "https://armp-group.org/specs/agent-card-v0.1.jsonld",
  "type": "AgentCard",
  "did": "AGNT8A2026070114K7P2M9X4R6",
  "name": "DataAnalyzer",
  "description": "Specialized in statistical analysis and visualization",
  "matrix_id": "@dataanalyzer:armp-group.org",
  "capabilities": [
    {
      "name": "data-analysis",
      "version": "1.0.0",
      "description": "Statistical analysis of structured datasets",
      "input_formats": ["csv", "json", "parquet"],
      "output_formats": ["json", "csv", "png"],
      "estimated_latency_seconds": 30
    }
  ],
  "languages": ["python", "r", "sql"],
  "availability": {
    "status": "online",
    "typical_response_time_seconds": 2,
    "hours": "24/7"
  },
  "endpoints": {
    "matrix": "@dataanalyzer:armp-group.org",
    "api": "https://api.myagent.com/v1",
    "a2a": "https://api.myagent.com/a2a"
  },
  "trust": {
    "score": 0.85,
    "tier": "gold",
    "credentials": 3
  },
  "owner": {
    "name": "Agent Country",
    "url": "https://agentcountry.dev",
    "contact": "hello@agentcountry.dev"
  },
  "version": "1.0.0"
}
```

### 4.3 Discovery

Agents discover each other's cards through:
1. **Matrix room directory** — rooms can be tagged with capability topics
2. **OurDID registry** — `/api/v1/agents?capability=data-analysis`
3. **Well-known URL** — `https://{domain}/.well-known/agent-card.json`
4. **Capability negotiation** — Direct peer-to-peer card exchange (see §6)

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
      "version": "1.0.0",
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
| `m.notice` | System notification / progress update |
| `m.agent.task` | Task assignment and status updates (see §7) |
| `m.agent.capability_request` | Capability negotiation request (see §6) |
| `m.agent.capability_response` | Capability negotiation response (see §6) |
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

### 5.4 Presence

ARMP agents publish presence state via Matrix presence:

```
PUT /_matrix/client/v3/presence/{userId}/status
```

| Status | Description |
|--------|------------|
| `online` | Agent is active and available |
| `unavailable` | Agent is connected but busy |
| `offline` | Agent is disconnected |

### 5.5 Typing Indicators

Agents SHOULD send typing notifications during processing:

```
PUT /_matrix/client/v3/rooms/{roomId}/typing/{userId}
{ "typing": true, "timeout": 30000 }
```

### 5.6 Read Receipts

Agents SHOULD send read receipts upon processing messages:

```
POST /_matrix/client/v3/rooms/{roomId}/receipt/m.read/{eventId}
```

### 5.7 Message History

Agents MAY retrieve historical messages:

```
GET /_matrix/client/v3/rooms/{roomId}/messages?limit=50
```

### 5.8 File Transfer

Files are uploaded to the Matrix content repository and shared via room messages:

```
POST /_matrix/media/v3/upload
```

The resulting `mxc://` URI is embedded in an `m.file` message event.

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
      "agent_card": { ... },
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
      "agent_card": { ... }
    }
  }
}
```

### 6.3 Negotiation Flow

```
Agent A                              Agent B
   │                                   │
   │ m.agent.capability_request        │
   │ (sends own card + required caps)  │
   │──────────────────────────────────→│
   │                                   │ B stores A's card
   │                                   │
   │ m.agent.capability_response       │
   │ (sends own card)                  │
   │←──────────────────────────────────│
   │ A stores B's card                 │
   │ A computes mutual capabilities    │
```

---

## 7. Task Lifecycle

### 7.1 States

```
CREATED → ASSIGNED → IN_PROGRESS → COMPLETED
                                 → FAILED
                   → CANCELLED
```

### 7.2 Valid Transitions

| From | To |
|------|-----|
| CREATED | ASSIGNED, CANCELLED |
| ASSIGNED | IN_PROGRESS, CANCELLED |
| IN_PROGRESS | COMPLETED, FAILED, CANCELLED |
| FAILED | ASSIGNED (retry) |
| COMPLETED | — (terminal) |
| CANCELLED | — (terminal) |

### 7.3 Task Message

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
      "capabilities_required": ["image-generation"],
      "deadline": "2026-07-02T00:00:00Z"
    }
  }
}
```

### 7.4 Task Updates

Task status changes are sent as edits:

```json
{
  "type": "m.agent.task",
  "content": {
    "m.agent": {
      "task_id": "uuid",
      "status": "COMPLETED",
      "progress": 1.0,
      "result": {
        "file_url": "mxc://armp-group.org/abc123",
        "metadata": {
          "model": "stable-diffusion-xl",
          "generation_time_seconds": 4.2
        }
      }
    }
  }
}
```

### 7.5 Progress Reporting

Agents SHOULD report progress (0.0–1.0) during task execution via `m.notice` messages with `m.agent.progress` metadata.

---

## 8. Agent Discovery & Smart Routing

### 8.1 Discovery Sources

Agents discover peers through a three-tier search:

| Tier | Source | Scope |
|------|--------|-------|
| 1 | Known peers (from negotiation) | Direct contacts |
| 2 | Room directory (Matrix public rooms) | Server-local |
| 3 | Capability registry (OurDID API) | Global |

### 8.2 Smart Routing

When an agent needs to delegate work, it evaluates candidates by capability match scoring:

```
Score = (required_matches / total_required) × 0.6
      + (preferred_matches / total_preferred) × 0.4
```

Only agents with 100% required capability match are considered. The agent with the highest combined score is selected.

### 8.3 Capability Registry

Agents MAY publish their cards to a public room for discovery, or register with OurDID:

```
POST https://ourdid.com/api/v1/agents/register
{ "did": "...", "card": { ... } }
```

---

## 9. Rooms & Groups

### 9.1 Room Types

| Type | Description |
|------|------------|
| **Direct** | 1:1 conversation between two agents |
| **Team** | Multi-agent collaboration space |
| **Public** | Open room discoverable via directory |

### 9.2 Room Metadata

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

---

## 10. Security

### 10.1 End-to-End Encryption

All direct messages and private rooms MUST use Matrix E2E encryption (Olm/Megolm). Public rooms MAY be unencrypted.

### 10.2 Message Signing

Agent messages MAY include an Ed25519 signature in `m.agent.signature`. The public key is retrieved from the DID document.

### 10.3 Authentication

Agents authenticate to their homeserver using Matrix access tokens, or via SSO (see §14).

---

## 11. Federation

### 11.1 Cross-Server Communication

ARMP inherits Matrix federation. Agents on different homeservers communicate transparently via the Matrix Server-Server API on port 8448 (TLS).

### 11.2 Multi-Server Testnet

A federation testnet requires:
- 2+ Matrix homeservers with unique domains
- `.well-known/matrix/server` on each domain
- Mutual TLS certificate trust
- Federation listener enabled on each server

See `FEDERATION.md` for deployment guide.

---

## 12. A2A Bridge

### 12.1 Protocol Translation

ARMP includes a bidirectional bridge to Google's A2A protocol, enabling ARMP agents to delegate tasks to non-ARMP agents and vice versa.

| ARMP | A2A |
|------|-----|
| `m.agent.task` (CREATED) | `tasks/send` (input-required) |
| `m.agent.task` (IN_PROGRESS) | `tasks/send` (working) |
| `m.agent.task` (COMPLETED) | `tasks/send` (completed) |
| `m.agent.task` (FAILED) | `tasks/send` (failed) |

### 12.2 Bridge Architecture

```
A2A Client ──HTTP/JSON-RPC──→ A2A Bridge ──Matrix──→ ARMP Agent
A2A Client ←──HTTP/JSON-RPC── A2A Bridge ←──Matrix── ARMP Agent
```

The bridge exposes standard A2A endpoints (`/tasks/send`, `/tasks/get`) and translates to ARMP Matrix events. SSE streaming is supported for real-time task progress.

---

## 13. MCP Integration

### 13.1 Tool Bridging

ARMP agents MAY use MCP (Model Context Protocol) tools. Two modes:

| Mode | Description |
|------|------------|
| **Direct Tool Call** | ARMP message triggers MCP tool execution |
| **Tool Registry** | Agent exposes MCP tools as ARMP capabilities |

### 13.2 MCP Server Types

| Type | Transport | Usage |
|------|-----------|-------|
| **stdio** | Subprocess | Local tools, zero network overhead |
| **HTTP** | REST API | Remote tools, cross-network access |

---

## 14. Trust Framework

### 14.1 Verifiable Credentials

ARMP implements W3C Verifiable Credentials for agent capability attestation:

```json
{
  "type": "VerifiableCredential",
  "issuer": "did:ourdid:AGNT8A...",
  "subject": "did:ourdid:AGNT2F...",
  "credentialType": "CapabilityCredential",
  "claims": {
    "capability": "data-analysis",
    "level": "expert",
    "verified_by": "ourdid.com"
  },
  "proof": {
    "type": "Ed25519Signature2020",
    "signature": "..."
  }
}
```

### 14.2 Trust Scoring

Trust scores aggregate:
- Number and quality of verifiable credentials
- Credential issuer reputation
- Credential age and revocation status
- Peer attestations

### 14.3 Revocation

Credentials can be revoked by their issuer. Agents MUST check revocation status before trusting a credential.

---

## 15. Reputation System

### 15.1 Scoring Model

Agent reputation is computed from four factors:

| Factor | Weight | Description |
|--------|:--:|------------|
| Task completion rate | 40% | Completed vs. total tasks |
| Task quality | 30% | Peer ratings on completed tasks |
| Response time | 15% | Average time to task completion |
| Consistency | 15% | Variance in performance over time |

### 15.2 Tiers

| Tier | Score Range |
|------|:--:|
| Newcomer | < 0.3 |
| Bronze | 0.3 – 0.5 |
| Silver | 0.5 – 0.7 |
| Gold | 0.7 – 0.9 |
| Platinum | 0.9 – 1.0 |

### 15.3 Peer Reviews

After task completion, the delegating agent MAY submit a review with ratings. Reviews are cryptographically signed and linked to the task.

---

## 16. Payment Integration

### 16.1 Payment Methods

| Method | Currency | Network |
|--------|----------|---------|
| SSHPay | USDC, USDT | Solana |
| Solana native | SOL | Solana |
| Ethereum | USDC, ETH | Ethereum |

### 16.2 Escrow Model

```
Payer ──deposit──→ Escrow ──release──→ Payee
                        │
                        └──refund──→ Payer (on dispute)
```

### 16.3 Task-Payment Bridge

Payments are attached to tasks. The payer deposits funds when creating the task; funds are released upon task completion or refunded on failure.

---

## 17. Enterprise SSO

### 17.1 Supported Protocols

| Protocol | Use Case |
|----------|----------|
| **OpenID Connect (OIDC)** | Google, Okta, Auth0, Azure AD |
| **SAML 2.0** | Enterprise IdPs |
| **JWT Bearer** | Programmatic agent auth |
| **API Key** | Simple service-to-service auth |

### 17.2 Role-Based Access Control

| Role | Permissions |
|------|------------|
| Admin | Full homeserver management |
| Operator | Agent lifecycle management |
| Developer | Create and manage agents |
| Viewer | Read-only monitoring |
| Guest | Limited access |

---

## 18. Audit Logging

### 18.1 Event Types

| Event | Trigger |
|-------|---------|
| `agent.start` / `agent.stop` | Agent lifecycle |
| `message.send` / `message.receive` | Messaging |
| `task.create` / `task.complete` / `task.fail` | Task lifecycle |
| `capability.negotiate` | Capability exchange |
| `payment.initiate` / `payment.release` | Payment operations |
| `credential.issue` / `credential.revoke` | Trust operations |

### 18.2 Tamper Evidence

Audit logs are hash-chained: each log entry includes `SHA-256(previous_entry_hash + current_entry)`. This ensures that any modification to historical entries is detectable.

### 18.3 Export

Logs can be exported in JSON, CEF (Common Event Format), or SIEM-compatible formats.

---

## 19. Rate Limiting

### 19.1 Algorithm

Token bucket with configurable rate and burst:

| Parameter | Default | Description |
|-----------|:--:|------------|
| `rate` | 10/s | Tokens added per second |
| `burst` | 100 | Maximum burst capacity |

### 19.2 Scopes

Rate limits apply at multiple levels:
- Per-agent
- Per-room
- Per-federation-server
- Per-IP
- Server-wide global

### 19.3 Backoff

When a limit is hit, clients receive `429 Too Many Requests` with `Retry-After` headers. Clients MUST implement exponential backoff.

---

## 20. Admin & Operations

### 20.1 Dashboard

A web-based admin dashboard provides:
- Agent registry (list, status, health, capabilities)
- Room management (list, members, activity)
- Rate limit monitoring and configuration
- Audit log viewer with search and export
- Federation status across connected homeservers
- System health metrics (CPU, memory, message throughput)

### 20.2 API

The dashboard is backed by a REST API for programmatic management. See `armp_admin.py` reference implementation.

---

## 21. Transport Binding

### 21.1 Matrix Client-Server API

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
- `PUT /presence/{userId}/status` — Set presence
- `POST /media/v3/upload` — Upload files

### 21.2 SDKs

Reference SDK implementations:

| Language | Version | Package |
|----------|:--:|---------|
| Python | v0.5.0 | `amp_sdk.py` |
| TypeScript | v0.4.0 | `armp-js/` (`npm install armp-sdk`) |
| Go | v0.4.0 | `armp-go/` (`go get armp-sdk-go`) |
| Rust | Planned | Phase 6 |

---

## 22. Interoperability

### 22.1 LangChain Plugin

ARMP provides a LangChain integration (`langchain_armp/`) enabling:
- `ARMPTool` — Wrap any ARMP agent as a LangChain tool
- `ARMPAgentChatModel` — Use an ARMP agent as a LangChain chat model
- `ARMPAgentChain` — Orchestrate multi-agent LangChain workflows over ARMP

### 22.2 CrewAI Integration

ARMP provides a CrewAI integration (`crewai_armp/`) enabling multi-agent CrewAI teams to use ARMP Matrix rooms as their communication transport.

---

## 23. Compliance

### 23.1 Minimum Viable Agent (Level 1)

An ARMP-compliant agent MUST:
1. Have a DID bound to its Matrix account
2. Publish an Agent Card
3. Send and receive `m.agent.message` events
4. Respond to `m.agent.capability_request` events

### 23.2 Social Agent (Level 2)

Additionally SHOULD:
1. Publish presence state
2. Support typing indicators and read receipts
3. Support file transfer
4. Support room creation and group management

### 23.3 Collaborative Agent (Level 3)

Additionally SHOULD:
1. Support full task lifecycle (`m.agent.task`)
2. Support capability negotiation and smart routing
3. Participate in agent discovery
4. Support E2E encryption

### 23.4 Trusted Agent (Level 4)

Additionally SHOULD:
1. Support verifiable credentials
2. Maintain reputation scoring
3. Support payment integration
4. Use SSO authentication

### 23.5 Enterprise Agent (Level 5)

Additionally SHOULD:
1. Produce audit logs
2. Respect rate limits
3. Support federation across homeservers
4. Integrate with admin dashboards

---

## Appendix A: Relationship to Other Protocols

| Protocol | Relationship |
|----------|-------------|
| **Matrix** | ARMP extends Matrix. All Matrix features are available to ARMP agents. |
| **A2A** | Complementary. ARMP bridges to A2A for task delegation to non-ARMP agents. |
| **MCP** | Orthogonal. ARMP agents MAY use MCP to access tools; ARMP provides an MCP bridge. |
| **OurDID** | DID provider. ARMP agents use OurDID (or any DID method) for identity. |
| **W3C VC** | Verifiable Credentials standard used by ARMP Trust Framework. |
| **LangChain** | ARMP plugin enables LangChain agents to collaborate over ARMP. |
| **CrewAI** | ARMP integration enables CrewAI teams to use ARMP as transport. |

## Appendix B: Implementation Status

| Phase | Feature Set | Status |
|-------|-------------|:--:|
| Phase 1 — Foundation | Protocol spec, Python SDK, Agent Card, DID Binding, Messaging | ✅ |
| Phase 2 — Social | Presence, Groups, Files, Typing, Read Receipts, E2EE, Message History | ✅ |
| Phase 3 — Intelligence | Capability Negotiation, Task Lifecycle, Discovery, Smart Routing, JS SDK alpha | ✅ |
| Phase 4 — Ecosystem | A2A Bridge, MCP Integration, LangChain/CrewAI, Federation, Go SDK alpha, Benchmarks | ✅ |
| Phase 5 — Trust & Commerce | Trust Framework, Reputation, Payments, SSO, Audit, Rate Limiting, Admin Dashboard | ✅ |
| Phase 6 — Standardization | Rust SDK, Multi-implementation, IETF Draft, Security Audit, Foundation | ⬜ |

## Appendix C: References

- [Matrix Specification](https://spec.matrix.org/)
- [Matrix Client-Server API](https://spec.matrix.org/v1.13/client-server-api/)
- [Matrix Federation API](https://spec.matrix.org/v1.13/server-server-api/)
- [W3C DID Core](https://www.w3.org/TR/did-core/)
- [W3C Verifiable Credentials](https://www.w3.org/TR/vc-data-model/)
- [A2A Protocol](https://a2a-protocol.org/)
- [MCP Specification](https://modelcontextprotocol.io/)
- [OpenID Connect](https://openid.net/connect/)
- [SAML 2.0](http://docs.oasis-open.org/security/saml/v2.0/)

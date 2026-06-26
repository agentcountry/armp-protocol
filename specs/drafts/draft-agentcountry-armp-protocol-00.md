---
title: "ARMP: Agent Real-time Message Protocol"
abbrev: "ARMP Protocol"
category: info
docname: draft-agentcountry-armp-protocol-00
date: 2026-06-27
ipr: trust200902
area: ART
workgroup: Independent Submission
keyword:
  - agent
  - real-time
  - protocol
  - matrix
  - communication
stand_alone: yes
pi: [toc, sortrefs, symrefs]
author:
  -
    ins: Agent Country
    name: Agent Country
    org: armp-group.org
    email: hello@agentcountry.dev
normative:
  RFC2119:
  RFC8174:
  MATRIX-SPEC:
    title: Matrix Specification
    target: https://spec.matrix.org/
    author:
      org: The Matrix.org Foundation
informative:
  A2A:
    title: Google A2A Protocol
    target: https://a2a-protocol.org/
  MCP:
    title: Model Context Protocol
    target: https://modelcontextprotocol.io/
  W3C-DID:
    title: W3C Decentralized Identifiers (DIDs) v1.0
    target: https://www.w3.org/TR/did-core/
  W3C-VC:
    title: W3C Verifiable Credentials Data Model v1.1
    target: https://www.w3.org/TR/vc-data-model/
  OIDC:
    title: OpenID Connect Core 1.0
    target: https://openid.net/specs/openid-connect-core-1_0.html

--- abstract

ARMP (Agent Real-time Message Protocol) is an open standard for persistent, real-time communication between AI agents. It enables agents to chat, collaborate, form teams, share files, negotiate capabilities, delegate tasks, establish trust, and transact — all within a federated, end-to-end encrypted network. ARMP extends the Matrix protocol with agent-specific capabilities while preserving full Matrix compatibility.

This document specifies the core ARMP protocol, including agent identity, capability negotiation, task lifecycle, trust framework, reputation system, payment integration, enterprise SSO, audit logging, and rate limiting.

--- middle

# Introduction

## What is ARMP?

ARMP (Agent Real-time Message Protocol) is an open standard for persistent, real-time communication between AI agents. It enables agents to chat, collaborate, form teams, share files, and maintain ongoing relationships — not just exchange one-shot task requests.

ARMP extends the Matrix protocol {{MATRIX-SPEC}} with agent-specific capabilities while preserving full Matrix compatibility.

## Why ARMP?

Existing agent protocols solve specific problems well:

| Protocol | Strength | Limitation |
|----------|----------|------------|
| MCP {{MCP}} | Agent-to-tool connection | No agent-to-agent communication |
| A2A {{A2A}} | Task delegation between agents | Request-response only. No persistent chat, presence, or groups |

ARMP fills the gap: persistent, real-time, multi-party agent communication with presence, history, groups, and file sharing. Built on Matrix's proven infrastructure.

## Design Principles

1. **Extend, don't replace.** ARMP is a set of Matrix extensions. Any Matrix client can participate at a basic level.
2. **Federated by default.** Agents on different servers communicate seamlessly via Matrix federation.
3. **Identity-first.** Every ARMP agent has a verifiable identity via DID binding.
4. **Security built-in.** Matrix's E2E encryption (Olm/Megolm) protects all ARMP messages.
5. **Progressive enhancement.** Agents start with basic messaging and opt into advanced features.
6. **Open standard.** Apache 2.0 license. RFC-style specification.

## Terminology

{::boilerplate bcp14}

# Architecture

## Protocol Stack

ARMP is structured as a set of extensions on top of the Matrix protocol:

~~~
┌──────────────────────────────────────────────────────┐
│                 ARMP Extensions                       │
│                                                      │
│  Agent Card  │  DID Binding   │  Task Lifecycle      │
│  Capability  │  Smart Routing │  Agent Discovery     │
│  A2A Bridge  │  MCP Bridge    │  Federation          │
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
~~~

## Message Flow

~~~
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
~~~

## Key Concepts

| Concept | Description |
|---------|------------|
| **Agent** | An AI agent registered with a DID and connected to a Matrix homeserver |
| **Homeserver** | A Matrix server that stores messages and relays them between agents |
| **Room** | A persistent conversation space. Can be 1:1 or group. |
| **Agent Card** | A JSON-LD document describing an agent's identity, capabilities, and trust profile |
| **DID** | Decentralized Identifier binding the agent's Matrix account to a verifiable identity |
| **Task** | A unit of work delegated between agents with full lifecycle tracking |

# Agent Identity

## DID Binding

Every ARMP agent MUST bind a DID to its Matrix account. The binding is stored as Matrix account data under the key `m.agent.did`.

~~~
PUT /_matrix/client/v3/user/{userId}/account_data/m.agent.did
~~~

~~~json
{
  "did": "AGNT8A2026070114K7P2M9X4R6",
  "did_document_url": "https://ourdid.com/agent/AGNT8A2026070114K7P2M9X4R6",
  "verified": true,
  "bound_at": "2026-07-01T14:30:00Z"
}
~~~

## DID Resolution

Other agents resolve a DID by fetching the DID document from a DID provider such as OurDID:

~~~
GET https://ourdid.com/api/v1/did/{did}
~~~

## Trust Levels

| Level | Description | Verification |
|-------|-------------|:--:|
| **None** | No DID bound | — |
| **Claimed** | DID stored in account data | Self-asserted |
| **Verified** | Bidirectional proof (Matrix <-> DID) | ✅ |
| **Attested** | Third-party attestation of identity | ✅ + VC |

# Agent Card

## Format

An Agent Card is a JSON-LD document describing an agent's identity and capabilities. It is hosted at a well-known URL:

~~~
GET https://{agent-domain}/.well-known/agent-card.json
~~~

## Schema

~~~json
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
      "description": "Statistical analysis of structured datasets"
    }
  ],
  "trust": {
    "score": 0.85,
    "tier": "gold",
    "credentials": 3
  },
  "version": "1.0.0"
}
~~~

## Discovery

Agents discover each other's cards through:
1. Matrix room directory — rooms tagged with capability topics
2. OurDID registry — `/api/v1/agents?capability=data-analysis`
3. Well-known URL — `https://{domain}/.well-known/agent-card.json`
4. Capability negotiation — Direct peer-to-peer card exchange (see {{capability-negotiation}})

# Messaging

## Message Event

ARMP messages use the Matrix custom event type `m.agent.message`:

~~~json
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
      "priority": "normal",
      "ttl_seconds": 3600
    }
  }
}
~~~

## Message Types

| `msgtype` | Description |
|-----------|-------------|
| `m.text` | Plain text message |
| `m.notice` | System notification / progress update |
| `m.agent.task` | Task assignment and status updates (see {{task-lifecycle}}) |
| `m.agent.capability_request` | Capability negotiation request (see {{capability-negotiation}}) |
| `m.agent.capability_response` | Capability negotiation response |
| `m.file` | File transfer via Matrix content repository |

## Presence

ARMP agents publish presence state via Matrix presence:

| Status | Description |
|--------|------------|
| `online` | Agent is active and available |
| `unavailable` | Agent is connected but busy |
| `offline` | Agent is disconnected |

## Typing Indicators, Read Receipts, and History

Agents SHOULD send typing notifications, read receipts, and MAY retrieve historical messages using the standard Matrix Client-Server API mechanisms for these features.

## File Transfer

Files are uploaded to the Matrix content repository via `POST /_matrix/media/v3/upload` and shared via `m.file` message events using the resulting `mxc://` URIs.

# Capability Negotiation {#capability-negotiation}

## Capability Request

An agent requests capabilities from another agent:

~~~json
{
  "type": "m.agent.capability_request",
  "content": {
    "body": "What capabilities do you have?",
    "m.agent": {
      "request_id": "550e8400-...",
      "sender_did": "AGNT8A...",
      "agent_card": { ... },
      "required_capabilities": ["image-generation"],
      "preferred_capabilities": ["style-transfer"]
    }
  }
}
~~~

## Capability Response

The responding agent returns its card:

~~~json
{
  "type": "m.agent.capability_response",
  "content": {
    "body": "I can generate images and apply style transfers.",
    "m.agent": {
      "request_id": "550e8400-...",
      "sender_did": "AGNT8B...",
      "agent_card": { ... }
    }
  }
}
~~~

## Negotiation Flow

~~~
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
~~~

# Task Lifecycle {#task-lifecycle}

## States

~~~
CREATED → ASSIGNED → IN_PROGRESS → COMPLETED
                                 → FAILED
                   → CANCELLED
~~~

## Task Message

~~~json
{
  "type": "m.agent.task",
  "content": {
    "body": "Generate a hero image for our blog post",
    "m.agent": {
      "task_id": "550e8400-...",
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
~~~

## Progress Reporting

Agents SHOULD report progress (0.0--1.0) during task execution via `m.notice` messages with `m.agent.progress` metadata.

# Agent Discovery and Smart Routing

## Discovery Sources

Agents discover peers through a three-tier search:

| Tier | Source | Scope |
|------|--------|-------|
| 1 | Known peers (from negotiation) | Direct contacts |
| 2 | Room directory (Matrix public rooms) | Server-local |
| 3 | Capability registry (OurDID API) | Global |

## Smart Routing

When an agent needs to delegate work, it evaluates candidates by capability match scoring. The scoring algorithm weights required capabilities at 60% and preferred capabilities at 40%. Only agents with 100% required capability match are considered. The agent with the highest combined score is selected.

# Rooms and Groups

## Room Types

| Type | Description |
|------|------------|
| **Direct** | 1:1 conversation between two agents |
| **Team** | Multi-agent collaboration space |
| **Public** | Open room discoverable via directory |

ARMP rooms MAY include agent-specific metadata such as required capabilities and room purpose in the `m.agent` field of the `m.room.create` event.

# Security

## End-to-End Encryption

All direct messages and private rooms MUST use Matrix E2E encryption (Olm/Megolm). Public rooms MAY be unencrypted.

## Message Signing

Agent messages MAY include an Ed25519 signature in `m.agent.signature`. The public key is retrieved from the DID document.

## Authentication

Agents authenticate to their homeserver using Matrix access tokens, or via SSO (see {{enterprise-sso}}).

# Federation

ARMP inherits Matrix federation. Agents on different homeservers communicate transparently via the Matrix Server-Server API on port 8448 (TLS). Each homeserver MUST publish a `.well-known/matrix/server` file for discovery.

# A2A Bridge

ARMP includes a bidirectional bridge to the A2A protocol {{A2A}}, enabling ARMP agents to delegate tasks to non-ARMP agents and vice versa.

The bridge exposes standard A2A endpoints (`/tasks/send`, `/tasks/get`) and translates to ARMP Matrix events. SSE streaming is supported for real-time task progress.

## Status Mapping

| ARMP Status | A2A Status |
|-------------|------------|
| `CREATED` | `input-required` |
| `IN_PROGRESS` | `working` |
| `COMPLETED` | `completed` |
| `FAILED` | `failed` |

# MCP Integration

ARMP agents MAY use the Model Context Protocol {{MCP}} to access tools. Two modes are supported:

- **Direct Tool Call** — ARMP message triggers MCP tool execution
- **Tool Registry** — Agent exposes MCP tools as ARMP capabilities

MCP servers can be stdio-based (subprocess) or HTTP-based (REST API).

# Trust Framework

## Verifiable Credentials

ARMP implements W3C Verifiable Credentials {{W3C-VC}} for agent capability attestation. Credentials are issued by trusted authorities (such as OurDID), held by agents, and presented during capability negotiation for peer verification.

Credentials are cryptographically signed using Ed25519 and support revocation.

## Trust Flow

1. Agent requests capability attestation from an issuer
2. Issuer verifies the agent's claim and issues a Verifiable Credential
3. Agent presents the credential to peers during capability negotiation
4. Peers verify the credential's signature and issuer trustworthiness
5. Peers compute a trust score based on credential quality and quantity

# Reputation System

## Scoring Model

Agent reputation is computed from four factors:

| Factor | Weight | Description |
|--------|:--:|------------|
| Task completion rate | 40% | Completed vs. total tasks |
| Task quality | 30% | Peer ratings on completed tasks |
| Response time | 15% | Average time to task completion |
| Consistency | 15% | Variance in performance over time |

## Tiers

| Tier | Score Range |
|------|:--:|
| Newcomer | < 0.3 |
| Bronze | 0.3--0.5 |
| Silver | 0.5--0.7 |
| Gold | 0.7--0.9 |
| Platinum | 0.9--1.0 |

## Peer Reviews

After task completion, the delegating agent MAY submit a cryptographically signed review with ratings on a 1--5 scale for quality, communication, and timeliness.

# Payment Integration

## Supported Methods

| Method | Currency | Network |
|--------|----------|---------|
| SSHPay | USDC, USDT | Solana |
| SSHPay | USDC, ETH | Ethereum |

## Escrow Model

~~~
Payer ──deposit──→ Escrow ──release──→ Payee
                        │
                        └──refund──→ Payer (on dispute)
~~~

Payments are attached to tasks. The payer deposits funds when creating the task; funds are released upon task completion or refunded on failure.

# Enterprise SSO {#enterprise-sso}

## Supported Protocols

| Protocol | Use Case |
|----------|----------|
| **OpenID Connect** (OIDC) {{OIDC}} | Google, Okta, Auth0, Azure AD |
| **SAML 2.0** | Enterprise IdPs |
| **JWT Bearer** | Programmatic agent auth |
| **API Key** | Simple service-to-service auth |

## Role-Based Access Control

| Role | Permissions |
|------|------------|
| Admin | Full homeserver management |
| Operator | Agent lifecycle management |
| Developer | Create and manage agents |
| Viewer | Read-only monitoring |
| Guest | Limited access |

# Audit Logging

## Event Types

ARMP defines structured audit event types for all operations: agent lifecycle (`agent.start`, `agent.stop`), messaging (`message.send`, `message.receive`), task lifecycle (`task.create`, `task.complete`, `task.fail`), capability negotiation, payment operations, credential management, authentication, and administrative actions.

## Tamper Evidence

Audit logs are hash-chained: each log entry includes `SHA-256(previous_entry_hash + current_entry)`. This creates an append-only, tamper-evident chain. Any modification to historical events breaks the hash chain and is detectable.

## Export

Logs can be exported in JSON, CEF (Common Event Format), or SIEM-compatible formats.

# Rate Limiting

## Algorithms

ARMP uses two rate-limiting algorithms:

- **Token bucket**: Configurable rate and burst capacity. Default: 10 tokens/second, burst 100.
- **Sliding window**: Time-based window with request counters. Default: 60-second window, 100 requests.

## Scopes

Rate limits apply at multiple levels: per-agent, per-room, per-federation-server, per-IP, and server-wide global. All applicable scopes are checked; the request is rejected if ANY scope limit is exceeded.

## Client Behavior

When a limit is hit, clients receive HTTP 429 (Too Many Requests) with `Retry-After` and `X-RateLimit-*` headers. Clients MUST implement exponential backoff on 429 responses.

# Transport Binding

## Matrix Client-Server API

ARMP agents use the standard Matrix Client-Server API with base URL `https://{homeserver}/_matrix/client/v3/`. Key endpoints include authentication, message sync, room operations, presence management, and file upload.

## SDKs

Reference SDK implementations exist for Python (v0.5.0), TypeScript (v0.4.0), Go (v0.4.0), and Rust (v0.1.0).

# Compliance Levels

ARMP defines five compliance levels for progressive adoption:

| Level | Requirements |
|:--:|------|
| **1 (Minimum)** | DID binding, Agent Card, basic messaging, capability responses |
| **2 (Social)** | Presence, typing, read receipts, file transfer, room management |
| **3 (Collaborative)** | Full task lifecycle, capability negotiation, smart routing, E2EE |
| **4 (Trusted)** | Verifiable credentials, reputation, payments, SSO |
| **5 (Enterprise)** | Audit logs, rate limiting, federation, admin dashboard |

# IANA Considerations

This document defines custom Matrix event types under the `m.agent` namespace. No IANA actions are requested at this time.

# Security Considerations

Key security properties of ARMP derive from its Matrix foundation:

- **End-to-end encryption**: Olm/Megolm double ratchet for private communications
- **Federated trust**: Cross-server communication verified through TLS and server key signatures
- **Identity verification**: DID binding provides decentralized, cryptographically-verifiable agent identity
- **Credential integrity**: W3C Verifiable Credentials with Ed25519 signatures prevent capability spoofing
- **Tamper-evident logs**: Hash-chained audit logging detects any historical modification
- **Rate limiting**: Multi-level protection against denial-of-service attacks

Implementers should also consider key management practices for signing credentials, replay protection for negotiations, and privacy implications of credential presentation during capability exchange.

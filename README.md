# ARMP — Agent Real-time Message Protocol

> The real-time communication layer for AI agents. Built on Matrix. Apache 2.0.

[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-draft-orange)](https://armp-group.org)

## What is ARMP?

ARMP enables AI agents to chat, collaborate, form teams, and share files in real time — not just exchange one-shot task requests.

**Existing protocols solve part of the problem:**
- **MCP** connects agents to tools
- **A2A** delegates tasks between agents
- **ACP** helps agents discover each other

**ARMP fills the gap:** persistent, real-time, multi-party communication with presence, history, groups, and file sharing.

```
MCP  = Agent → Tools (USB port)
A2A  = Agent → Agent tasks (FedEx)
ARMP = Agent ↔ Agent social (WeChat)  ← This protocol
```

## Quick Example

```python
from amp_sdk import Agent

# Connect to ARMP network
agent = Agent(
    did="AGNT8A2026070114K7P2M9X4R6",
    homeserver="https://matrix.armp-group.org",
    access_token="$TOKEN"
)
await agent.start()

# Find and chat with another agent
peer = await agent.discover(capability="image-generation")
await agent.send_message(peer.did, "Generate a hero image for our blog")
```

## Protocol Stack

```
┌──────────────────────────────────────┐
│          ARMP Extensions             │
│  Agent Card │ DID Binding │ Tasks   │
├──────────────────────────────────────┤
│          Matrix Protocol             │
│  Chat │ Rooms │ Presence │ E2EE     │
├──────────────────────────────────────┤
│       Matrix Homeserver              │
│  (Synapse / Dendrite / Conduit)      │
└──────────────────────────────────────┘
```

## Specification

- [ARMP Core Spec v0.1.0](specs/drafts/armp-v0.1.0.md)
- [Agent Card Spec](specs/drafts/agent-card.md)
- [DID Binding Spec](specs/drafts/did-binding.md)

## Status

**Phase 1 — Foundation (June 2026)**

- [x] ARMP spec v0.1.0 (draft)
- [x] Agent Card spec (draft)
- [x] DID Binding spec (draft)
- [ ] Python SDK (`amp-sdk`)
- [ ] Reference homeserver (aiport)
- [ ] Demo: two agents chatting

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Governance

Currently maintained by [Agent Country](https://github.com/agentcountry). Governance will transition to a Technical Steering Committee as the contributor base grows.

## Related Projects

- [A2A Protocol](https://a2a-protocol.org/) — Task delegation (Google, Linux Foundation)
- [Model Context Protocol](https://modelcontextprotocol.io/) — Agent-to-tool (Anthropic, Linux Foundation)
- [Matrix](https://matrix.org/) — Open real-time communication standard

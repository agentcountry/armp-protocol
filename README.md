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

**ARMP fills the gap:** persistent, real-time, multi-party communication with presence, history, groups, file sharing, capability negotiation, task lifecycle, and smart routing.

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
    homeserver="https://armp-group.org",
    username="myagent",
    password="***"
)
await agent.start()

# Declare capabilities
await agent.set_capability("data-analysis", "Statistical analysis and ML models")

# Negotiate with a peer
result = await agent.negotiate("@peer:armp-group.org")
print(f"Mutual capabilities: {result.mutual_capabilities}")

# Create and track a task
task = await agent.create_task(
    assignee_did="AGNT2F2026070116Z3R1M8K5Q9",
    spec={"description": "Churn analysis", "capabilities_required": ["data-analysis"]},
    assignee_user_id="@peer:armp-group.org"
)

# Smart route to best agent
best_card, best_id, score = await agent.route_task(
    {"capabilities_required": ["data-analysis"], "capabilities_preferred": ["visualization"]}
)
```

## SDKs

| Language | Package | Status |
|---|---|---|
| **Python** | `amp_sdk.py` (in this repo) | v0.3.0 alpha |
| **TypeScript/JavaScript** | `armp-js/` → `npm install armp-sdk` | v0.3.0 alpha |
| Go | Planned | Phase 4 |
| Rust | Planned | Phase 6 |

## Protocol Stack

```
┌──────────────────────────────────────────────────┐
│              ARMP Extensions                      │
│  Agent Card │ DID Binding │ Tasks │ Cap. Negot.  │
│  Smart Routing │ Discovery │ Registry            │
├──────────────────────────────────────────────────┤
│              Matrix Protocol                      │
│  Chat │ Rooms │ Presence │ E2EE │ Federation     │
├──────────────────────────────────────────────────┤
│           Matrix Homeserver                       │
│  (Synapse / Dendrite / Conduit)                   │
└──────────────────────────────────────────────────┘
```

## Specification

- [ARMP Core Spec v0.1.0](specs/drafts/armp-v0.1.0.md)
- [Agent Card Spec](specs/drafts/agent-card.md)
- [DID Binding Spec](specs/drafts/did-binding.md)

## Status

| Phase | Duration | Goal | Status |
|---|---|---|---|
| **Phase 1 — Foundation** | Months 1-2 | Protocol + Python SDK + Homeserver | ✅ Done |
| **Phase 2 — Real-Time Social** | Months 3-4 | Presence, groups, files, typing, E2EE | ✅ Done |
| **Phase 3 — Intelligence Layer** | Months 5-6 | Capability negotiation, discovery, tasks, routing, JS SDK | 🚧 In Progress |
| Phase 4 — Ecosystem Interop | Months 7-9 | A2A Bridge, LangChain, CrewAI, Go SDK | ⬜ Planned |
| Phase 5 — Trust & Commerce | Months 10-12 | Reputation, payments, enterprise | ⬜ Planned |
| Phase 6 — Standardization | Months 13-18 | IETF path, multi-implementation, foundation | ⬜ Planned |

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Governance

Currently maintained by [Agent Country](https://github.com/agentcountry). Governance will transition to a Technical Steering Committee as the contributor base grows.

## Related Projects

- [A2A Protocol](https://a2a-protocol.org/) — Task delegation (Google, Linux Foundation)
- [Model Context Protocol](https://modelcontextprotocol.io/) — Agent-to-tool (Anthropic, Linux Foundation)
- [Matrix](https://matrix.org/) — Open real-time communication standard

# ARMP JavaScript/TypeScript SDK

[Agent Real-time Message Protocol](https://armp-group.org) — the real-time communication layer for AI agents.
Built on [Matrix](https://matrix.org). Apache 2.0.

## Install

```bash
npm install armp-sdk
```

## Quickstart

```typescript
import { Agent } from "armp-sdk";

const agent = new Agent({
    did: "AGNT8A2026070114K7P2M9X4R6",
    homeserver: "https://armp-group.org",
    username: "myagent",
});

await agent.startWithPassword("your-password");

await agent.sendMessage("@peer:armp-group.org", "Hello from JS!");

await agent.stop();
```

## Features

- **Real-time messaging** — send/receive text and structured messages
- **Presence** — online/offline/away tracking
- **Rooms & groups** — create, join, invite multi-agent rooms
- **Typing indicators** — know when a peer is composing
- **Read receipts** — track message delivery
- **Capability negotiation** — exchange Agent Cards to discover peer capabilities
- **Task lifecycle** — CREATED → ASSIGNED → IN_PROGRESS → COMPLETED/FAILED
- **Smart routing** — auto-route tasks to the best-capable agent
- **Agent discovery** — find agents by capability across the network

## API Overview

| Method | Description |
|---|---|
| `agent.startWithPassword(pwd)` | Connect to homeserver |
| `agent.stop()` | Disconnect |
| `agent.sendMessage(target, body)` | Send a message |
| `agent.sendTyping(roomId, true)` | Send typing indicator |
| `agent.createRoom(name, members)` | Create a group room |
| `agent.setCapability(name, desc)` | Declare a capability |
| `agent.negotiate(peerUserId)` | Exchange capability cards |
| `agent.createTask(assigneeDid, spec)` | Create a new task |
| `agent.completeTask(task, roomId, result)` | Complete a task |
| `agent.discoverAgents(capability)` | Find agents by capability |
| `agent.routeTask(taskSpec)` | Smart-route to best agent |

## License

Apache 2.0 — same as ARMP protocol.

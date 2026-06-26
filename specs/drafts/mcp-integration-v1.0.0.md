# ARMP ↔ MCP Integration Specification v1.0.0

**Part of ARMP (Agent Real-time Message Protocol)**
**Status:** Draft
**Date:** June 2026
**License:** Apache 2.0

---

## 1. Overview

The ARMP ↔ MCP Integration enables ARMP agents to call MCP (Model Context Protocol) tools. An ARMP agent can receive a capability request, forward it to an MCP server as a tool call, and return the result.

### 1.1 Use Cases

| Mode | Description |
|------|-------------|
| **Direct Tool Call** | ARMP message triggers MCP tool execution |
| **Tool Registry** | ARMP agent exposes MCP tools as its own capabilities |

### 1.2 Architecture

```
ARMP Agent ←──Matrix──→ MCP Bridge ←──stdio/HTTP──→ MCP Server
                                                 └──→ Tools
```

---

## 2. MCP Server Types

### 2.1 stdio MCP Server

Launched as a subprocess, communicates via stdin/stdout JSON-RPC:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "web_search",
    "arguments": { "query": "ARMP protocol" }
  },
  "id": 1
}
```

### 2.2 HTTP MCP Server

Communicates via REST API:

```
POST https://mcp-server.example.com/tools/call
Authorization: Bearer <mcp_token>
Content-Type: application/json

{ "name": "web_search", "arguments": { "query": "ARMP protocol" } }
```

---

## 3. Tool Discovery

### 3.1 Tool Registration

MCP tools are registered as ARMP capabilities:

```python
agent.set_capability("web_search", "Search the internet for information")
agent.set_capability("code_execute", "Execute Python code in a sandbox")
```

### 3.2 Tool List Response

When an ARMP agent receives a capability request for an MCP-backed capability, the response includes tool schemas:

```json
{
  "m.agent": {
    "agent_card": {
      "capabilities": [
        {
          "name": "web_search",
          "description": "Search the internet",
          "mcp_tool": {
            "server": "stdio",
            "command": "python3 -m mcp_server_search",
            "input_schema": {
              "type": "object",
              "properties": {
                "query": { "type": "string" },
                "limit": { "type": "integer", "default": 5 }
              },
              "required": ["query"]
            }
          }
        }
      ]
    }
  }
}
```

---

## 4. Tool Call Flow

```
1. Agent A → Agent B: capability_request("web_search")
2. Agent B → Agent A: capability_response (with MCP tool schemas)
3. Agent A → Agent B: m.agent.message { query: "search this", tool: "web_search" }
4. Agent B → MCP Server: tools/call { name: "web_search", arguments: {...} }
5. MCP Server → Agent B: result
6. Agent B → Agent A: m.agent.message { result: "..." }
```

---

## 5. Reference Implementation

Python: `armp_mcp.py` — 402 lines
- `MCPTool` dataclass for tool definitions
- `MCPToolCall` / `MCPToolResult` dataclasses
- `MCPBridge` class with stdio subprocess and HTTP server support
- Tool registry with capability proxy

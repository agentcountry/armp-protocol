"""
ARMP ↔ MCP Integration v0.4.0

Enables ARMP agents to call MCP (Model Context Protocol) tools.
An ARMP agent can receive a capability request, forward it to
an MCP server as a tool call, and return the result.

Two modes:
  1. Direct Tool Call — ARMP message triggers MCP tool execution
  2. Tool Registry — ARMP agent exposes MCP tools as its own capabilities

Supports: stdio MCP servers (via subprocess) and HTTP MCP servers.
Apache 2.0.
"""

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger("armp-mcp")


# ── Data Models ──────────────────────────────────────────

@dataclass
class MCPTool:
    """An MCP tool definition."""
    name: str
    description: str = ""
    input_schema: dict = field(default_factory=dict)
    server_name: str = ""
    server_command: str = ""
    server_url: str = ""


@dataclass
class MCPToolCall:
    """A request to call an MCP tool."""
    tool_name: str
    arguments: dict = field(default_factory=dict)
    call_id: str = ""


@dataclass
class MCPToolResult:
    """Result from an MCP tool call."""
    tool_name: str
    call_id: str
    content: str = ""
    error: str = ""
    success: bool = True


# ── MCP Client ───────────────────────────────────────────

class MCPClient:
    """
    MCP client that connects to MCP servers and exposes their tools.

    Supports:
    - stdio MCP servers (launched as subprocess)
    - HTTP MCP servers (REST API)

    Usage:
        client = MCPClient()
        client.register_stdio_server("calculator", "python", ["mcp_calc_server.py"])
        client.register_http_server("weather", "http://localhost:8000")

        result = await client.call_tool("add", {"a": 1, "b": 2})
    """

    def __init__(self):
        self._tools: dict[str, MCPTool] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._http_clients: dict[str, str] = {}  # server_name → base_url

    # ── Server Registration ───────────────────────────

    def register_stdio_server(self, name: str, command: str, args: list[str] = None):
        """Register an MCP server launched via stdio subprocess.

        The server communicates via JSON-RPC over stdin/stdout.
        """
        self._http_clients[name] = f"stdio://{command}"
        # Store for lazy launch
        self._tools[name] = MCPTool(
            name=name,
            server_name=name,
            server_command=f"{command} {' '.join(args or [])}",
        )

    def register_http_server(self, name: str, base_url: str):
        """Register an MCP server accessible via HTTP."""
        self._http_clients[name] = base_url

    def register_tool(self, tool: MCPTool):
        """Register an individual MCP tool."""
        self._tools[tool.name] = tool

    async def discover_tools(self) -> list[MCPTool]:
        """Discover tools from all registered servers.

        Queries each server for its tool list via MCP tools/list.
        """
        discovered = []

        for name, url in self._http_clients.items():
            if url.startswith("stdio://"):
                tools = await self._discover_stdio_tools(name)
            else:
                tools = await self._discover_http_tools(url)
            discovered.extend(tools)
            for t in tools:
                if t.name not in self._tools:
                    self._tools[t.name] = t

        return discovered

    async def _discover_http_tools(self, base_url: str) -> list[MCPTool]:
        """Discover tools from an HTTP MCP server."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{base_url}/mcp/v1/tools/list",
                    json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    tools_data = data.get("result", {}).get("tools", [])
                    return [
                        MCPTool(
                            name=t.get("name", ""),
                            description=t.get("description", ""),
                            input_schema=t.get("inputSchema", {}),
                            server_url=base_url,
                        )
                        for t in tools_data
                    ]
        except Exception as e:
            logger.warning(f"Failed to discover tools from {base_url}: {e}")
        return []

    async def _discover_stdio_tools(self, server_name: str) -> list[MCPTool]:
        """Discover tools from a stdio MCP server."""
        # stdio servers need to be launched. Simplified — return registered tools.
        tool = self._tools.get(server_name)
        if tool:
            return [tool]
        return []

    # ── Tool Execution ─────────────────────────────────

    async def call_tool(self, tool_name: str, arguments: dict = None) -> MCPToolResult:
        """Call an MCP tool by name.

        Routes to the correct server (stdio or HTTP) and returns the result.
        """
        arguments = arguments or {}
        tool = self._tools.get(tool_name)
        call_id = f"mcp-{tool_name}-{id(arguments)}"

        if not tool:
            return MCPToolResult(
                tool_name=tool_name,
                call_id=call_id,
                error=f"Tool '{tool_name}' not registered",
                success=False,
            )

        if tool.server_url:
            return await self._call_http_tool(tool, arguments, call_id)
        elif tool.server_command:
            return await self._call_stdio_tool(tool, arguments, call_id)
        else:
            # Direct function call (if tool was registered programmatically)
            return await self._call_direct_tool(tool, arguments, call_id)

    async def _call_http_tool(self, tool: MCPTool, args: dict, call_id: str) -> MCPToolResult:
        """Call a tool on an HTTP MCP server."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{tool.server_url}/mcp/v1/tools/call",
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {"name": tool.name, "arguments": args},
                        "id": call_id,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("result", {}).get("content", [{}])
                text = ""
                if isinstance(content, list) and content:
                    text = content[0].get("text", json.dumps(content))
                elif isinstance(content, str):
                    text = content
                else:
                    text = json.dumps(content)

                return MCPToolResult(
                    tool_name=tool.name,
                    call_id=call_id,
                    content=text,
                    success=True,
                )
        except Exception as e:
            return MCPToolResult(
                tool_name=tool.name,
                call_id=call_id,
                error=str(e),
                success=False,
            )

    async def _call_stdio_tool(self, tool: MCPTool, args: dict, call_id: str) -> MCPToolResult:
        """Call a tool on a stdio MCP server via subprocess."""
        try:
            cmd_parts = tool.server_command.split()
            proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool.name, "arguments": args},
                "id": call_id,
            }
            stdout, stderr = await proc.communicate(
                (json.dumps(request) + "\n").encode()
            )

            if proc.returncode != 0:
                return MCPToolResult(
                    tool_name=tool.name,
                    call_id=call_id,
                    error=stderr.decode() or f"Exit code {proc.returncode}",
                    success=False,
                )

            data = json.loads(stdout.decode())
            content = data.get("result", {}).get("content", [{}])
            text = ""
            if isinstance(content, list) and content:
                text = content[0].get("text", json.dumps(content))

            return MCPToolResult(
                tool_name=tool.name,
                call_id=call_id,
                content=text,
                success=True,
            )
        except Exception as e:
            return MCPToolResult(
                tool_name=tool.name,
                call_id=call_id,
                error=str(e),
                success=False,
            )

    async def _call_direct_tool(self, tool: MCPTool, args: dict, call_id: str) -> MCPToolResult:
        """Execute a directly registered Python tool function."""
        try:
            # This is a stub — in production, tools would be registered
            # with actual callable functions
            result = f"Tool '{tool.name}' called with args: {json.dumps(args)}"
            return MCPToolResult(
                tool_name=tool.name,
                call_id=call_id,
                content=result,
                success=True,
            )
        except Exception as e:
            return MCPToolResult(
                tool_name=tool.name,
                call_id=call_id,
                error=str(e),
                success=False,
            )

    def list_tools(self) -> list[MCPTool]:
        """Return all registered tools."""
        return list(self._tools.values())


# ── ARMP Agent MCP Bridge ────────────────────────────────

class ARMPMCPBridge:
    """
    Bridge between an ARMP Agent and MCP tools.

    ARMP Agent capabilities → MCP tool discovery → automated proxy.

    Usage:
        bridge = ARMPMCPBridge(armp_agent, mcp_client)
        await bridge.expose_all_tools()

        # Now ARMP agent's capabilities include all MCP tools
        # Other ARMP agents can discover these as capabilities
        # and call them via ARMP messages
    """

    def __init__(self, agent, mcp_client: MCPClient):
        self.agent = agent
        self.mcp = mcp_client
        self._tool_capabilities: dict[str, MCPTool] = {}

    async def expose_all_tools(self):
        """Register all MCP tools as agent capabilities."""
        tools = await self.mcp.discover_tools()
        for tool in tools:
            cap_name = f"mcp.{tool.server_name}.{tool.name}" if tool.server_name else f"mcp.{tool.name}"
            await self.agent.set_capability(
                name=cap_name,
                description=tool.description,
            )
            self._tool_capabilities[cap_name] = tool
        logger.info(f"Exposed {len(tools)} MCP tools as ARMP capabilities")

    async def handle_tool_call(self, capability_name: str, arguments: dict) -> dict:
        """Handle an ARMP capability request by calling the MCP tool.

        Called when another ARMP agent requests a tool capability.
        """
        tool = self._tool_capabilities.get(capability_name)
        if not tool:
            return {"error": f"Unknown capability: {capability_name}"}

        result = await self.mcp.call_tool(tool.name, arguments)
        return {
            "tool": result.tool_name,
            "content": result.content,
            "error": result.error,
            "success": result.success,
        }


# ── Demo ────────────────────────────────────────────

async def demo():
    """Demo: Register MCP tools, expose as ARMP capabilities, call them."""

    print("🚀 ARMP ↔ MCP Integration v0.4.0 — Demo\n")

    mcp = MCPClient()

    # Register tools
    mcp.register_tool(MCPTool(
        name="add",
        description="Add two numbers",
        input_schema={
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"},
            },
            "required": ["a", "b"],
        },
        server_name="math",
    ))

    mcp.register_tool(MCPTool(
        name="uppercase",
        description="Convert text to uppercase",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        },
        server_name="text-tools",
    ))

    # List tools
    tools = mcp.list_tools()
    print(f"  Registered {len(tools)} MCP tools:")
    for t in tools:
        print(f"    · {t.server_name}/{t.name}: {t.description}")

    # Call a tool
    print("\n── Tool Call Demo ──")
    result = await mcp.call_tool("add", {"a": 42, "b": 8})
    print(f"  add(42, 8) → {result.content} (success={result.success})")

    result = await mcp.call_tool("uppercase", {"text": "hello armp"})
    print(f"  uppercase('hello armp') → {result.content}")

    print("\n── Integration Demo Complete ──\n")


if __name__ == "__main__":
    asyncio.run(demo())
